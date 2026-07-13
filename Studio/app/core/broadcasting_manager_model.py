"""Broadcasting Software Manager — read-only monitoring and confirmed controls."""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from app.core.advertising_model import normalize_bundle as normalize_advertising
from app.core.advertising_storage import load_advertising_bundle
from app.core.automation_model import MODULE_DEFINITIONS, _collect_activity_log, _module_log_path
from app.core.dashboard_model import build_dashboard_snapshot
from app.core.health_constants import HEALTH_ERROR, HEALTH_OK, HEALTH_WARN
from app.core.integration_settings import news_live_paths, normalize_integration_settings
from app.core.news_content_storage import load_news_content_bundle
from app.core.operations_manager_model import safety_summary
from app.core.personality_model import display_label, normalize_personalities_data
from app.core.platform_manager import platform_path, test_platform_path
from app.core.programming_model import load_programming_bundle, normalize_bundle as normalize_programming
from app.core.schedule_model import DAYS, normalize_schedule_data, time_to_minutes
from app.core.hidden_process import path_is_accessible

logger = logging.getLogger("moplace.studio.broadcasting")

AUDIO_MONITOR_KEYS = (
    ("audio_generated", "Generated Voice"),
    ("audio_news", "News Audio"),
    ("audio_requests", "Request Audio"),
    ("audio_commercials", "Commercials"),
    ("audio_promos", "Promos"),
    ("audio_sweepers", "Sweepers"),
    ("assets_voices", "Shared Voice Files"),
)

RADIODJ_TEXT_CANDIDATES = (
    "nowplaying.txt",
    "NowPlaying.txt",
    "queue.txt",
    "Queue.txt",
    "playlist.txt",
    "history.txt",
    "History.txt",
    "recent.txt",
)

AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".ogg", ".flac"}
AUDIO_SCAN_TIMEOUT_SECONDS = 3.0
AUDIO_SCAN_FILE_LIMIT = 400


@dataclass
class BroadcastHealthLight:
    name: str
    status: str
    detail: str


@dataclass
class AudioFolderSummary:
    key: str
    label: str
    path: str
    status: str
    file_count: int
    newest_files: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)


@dataclass
class RadioDJSnapshot:
    running: bool
    status: str
    detail: str
    executable: str
    folder: str
    current_artist: str
    current_song: str
    now_playing: str
    queue_lines: list[str] = field(default_factory=list)
    upcoming_lines: list[str] = field(default_factory=list)
    history_lines: list[str] = field(default_factory=list)


@dataclass
class BroadcastScheduleLine:
    time: str
    label: str
    category: str


@dataclass
class BroadcastingSnapshot:
    on_air_status: str
    current_song: str
    current_artist: str
    current_host: str
    current_show: str
    current_format: str
    next_event: str
    queue_overview: list[str]
    recent_activity: list[str]
    health_lights: list[BroadcastHealthLight]
    alerts: list[str]
    radiodj: RadioDJSnapshot
    audio_folders: list[AudioFolderSummary]
    today_schedule: list[BroadcastScheduleLine]
    website_scheduler_status: str
    website_scheduler_detail: str
    safety_lines: list[str]
    last_refreshed: str


def _now_parts() -> tuple[str, int]:
    now = datetime.now()
    return DAYS[now.weekday()], now.hour * 60 + now.minute


def _parse_now_playing(text: str) -> tuple[str, str, str]:
    cleaned = text.strip()
    if not cleaned or cleaned == "—":
        return "—", "—", "—"
    first_line = cleaned.splitlines()[0].strip()
    for separator in (" - ", " – ", " — ", " | "):
        if separator in first_line:
            artist, song = first_line.split(separator, 1)
            return first_line, artist.strip(), song.strip()
    return first_line, "—", first_line


def _read_text_candidates(folder: Path, names: tuple[str, ...], *, limit: int = 12) -> list[str]:
    if str(folder).startswith("\\\\") or not path_is_accessible(folder):
        return []
    lines: list[str] = []
    for name in names:
        path = folder / name
        if not path.exists() or not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for line in content:
            text = line.strip()
            if text:
                lines.append(text[:120])
        if lines:
            break
    return lines[:limit]


def _scan_audio_folder(key: str, label: str, config_manager) -> AudioFolderSummary:
    folder = platform_path(key, config_manager)
    path_text = str(folder)
    if str(folder).startswith("\\\\"):
        return AudioFolderSummary(
            key,
            label,
            path_text,
            HEALTH_WARN,
            0,
            [],
            ["Network folder scan skipped to avoid blocking Studio."],
        )
    if not path_is_accessible(folder):
        return AudioFolderSummary(key, label, path_text, HEALTH_WARN, 0, [], ["Folder not found"])

    files: list[Path] = []
    issues: list[str] = []
    scan_started = time.monotonic()
    try:
        for root, _dirs, filenames in os.walk(folder):
            if time.monotonic() - scan_started > AUDIO_SCAN_TIMEOUT_SECONDS:
                issues.append("Scan stopped early because the folder is slow or very large.")
                break
            for name in filenames:
                path = Path(root) / name
                if path.suffix.lower() in AUDIO_EXTENSIONS:
                    files.append(path)
                if len(files) >= AUDIO_SCAN_FILE_LIMIT:
                    break
            if len(files) >= AUDIO_SCAN_FILE_LIMIT:
                break
    except OSError as exc:
        return AudioFolderSummary(key, label, path_text, HEALTH_ERROR, 0, [], [str(exc)])

    blank = [path for path in files if path.stat().st_size == 0]
    if blank:
        issues.append(f"{len(blank)} blank audio file(s)")

    files.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    newest: list[str] = []
    now = datetime.now().timestamp()
    for path in files[:5]:
        stat = path.stat()
        age_hours = max(0.0, (now - stat.st_mtime) / 3600)
        size_kb = stat.st_size / 1024
        newest.append(f"{path.name} · {size_kb:.1f} KB · {age_hours:.1f}h ago")

    status = HEALTH_OK
    if blank:
        status = HEALTH_ERROR
    elif not files:
        status = HEALTH_WARN
        issues.append("No audio files found")

    path_test = test_platform_path(key, path_text)
    if path_test["status"] == HEALTH_ERROR:
        status = HEALTH_ERROR
        issues.append(path_test["message"])

    return AudioFolderSummary(key, label, path_text, status, len(files), newest, issues)


def _detect_schedule_conflicts(slots: list[dict[str, Any]]) -> list[str]:
    conflicts: list[str] = []
    by_day: dict[str, list[dict[str, Any]]] = {}
    for slot in slots:
        if not slot.get("enabled", True):
            continue
        day = slot.get("day", "").lower()
        if day in DAYS:
            by_day.setdefault(day, []).append(slot)

    for day, day_slots in by_day.items():
        ordered = sorted(day_slots, key=lambda item: time_to_minutes(item.get("start_time", "00:00")))
        for index in range(len(ordered) - 1):
            current = ordered[index]
            nxt = ordered[index + 1]
            try:
                current_end = time_to_minutes(current.get("end_time", "00:00"))
                next_start = time_to_minutes(nxt.get("start_time", "00:00"))
            except ValueError:
                continue
            if current_end > next_start:
                conflicts.append(
                    f"{day.title()}: {current.get('show_name', 'Show')} overlaps {nxt.get('show_name', 'Show')}"
                )
    return conflicts


def _news_stale_message(settings: dict[str, Any]) -> str | None:
    integration = normalize_integration_settings(settings)
    news_paths = news_live_paths(integration)
    config_path = news_paths["config"]
    if not config_path.exists():
        return "News configuration not found on live path"
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "News configuration could not be read"
    last_run = data.get("last_successful_run", "")
    if not last_run or last_run in {"Not recorded", "Never"}:
        return "News has not recorded a successful run yet"
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%m/%d/%Y %I:%M %p"):
        try:
            parsed = datetime.strptime(last_run, fmt)
            if datetime.now() - parsed > timedelta(hours=24):
                return f"News last run is stale ({last_run})"
            return None
        except ValueError:
            continue
    if "day" in last_run.lower() or "ago" in last_run.lower():
        return None
    return f"News last run may be stale ({last_run})"


def _build_today_schedule(config_manager) -> list[BroadcastScheduleLine]:
    day, minutes = _now_parts()
    lines: list[tuple[int, BroadcastScheduleLine]] = []

    personalities_data = normalize_personalities_data(config_manager.load("personalities", {"personalities": []}))
    personalities = {item["id"]: item for item in personalities_data.get("personalities", [])}
    schedule_data = normalize_schedule_data(
        config_manager.load("schedule", {"slots": []}),
        list(personalities.keys()),
    )
    for slot in schedule_data.get("slots", []):
        if slot.get("day", "").lower() != day or not slot.get("enabled", True):
            continue
        personality = personalities.get(slot.get("personality_id", ""), {})
        host = display_label(personality) if personality else slot.get("personality_id", "—")
        requests = "Requests on" if slot.get("requests_enabled", True) else "Requests off"
        try:
            sort_key = time_to_minutes(slot.get("start_time", "00:00"))
        except ValueError:
            sort_key = 0
        lines.append(
            (
                sort_key,
                BroadcastScheduleLine(
                    f"{slot.get('start_time', '')}–{slot.get('end_time', '')}",
                    f"{slot.get('show_name', 'Show')} · {host} · {slot.get('music_format', '—')} · {requests}",
                    "show",
                ),
            )
        )

    try:
        news_bundle = load_news_content_bundle(config_manager)
        for slot in news_bundle.get("schedule", {}).get("slots", []):
            if not slot.get("enabled", True):
                continue
            lines.append(
                (
                    time_to_minutes(slot.get("time", "00:00")),
                    BroadcastScheduleLine(slot.get("time", ""), slot.get("name", "News"), "news"),
                )
            )
    except Exception:
        pass

    try:
        programming = normalize_programming(load_programming_bundle(config_manager))
        for event in programming["events"]["events"]:
            if event.get("day", "").lower() != day or not event.get("enabled", True):
                continue
            category = "specialty" if event.get("category") == "specialty" else "programming"
            try:
                sort_key = time_to_minutes(event.get("start_time", "00:00"))
            except ValueError:
                sort_key = 0
            lines.append(
                (
                    sort_key,
                    BroadcastScheduleLine(
                        f"{event.get('start_time', '')}–{event.get('end_time', '')}",
                        event.get("show_name", "Programming Event"),
                        category,
                    ),
                )
            )
    except Exception:
        pass

    advertising = normalize_advertising(load_advertising_bundle(config_manager))
    for campaign in advertising.get("campaigns", {}).get("campaigns", []):
        if not campaign.get("enabled", True):
            continue
        slot_time = campaign.get("time", campaign.get("start_time", ""))
        if slot_time:
            try:
                sort_key = time_to_minutes(slot_time)
            except ValueError:
                sort_key = 9999
            lines.append(
                (
                    sort_key,
                    BroadcastScheduleLine(slot_time, campaign.get("name", "Advertising"), "advertising"),
                )
            )

    for sponsor in advertising.get("sponsors", {}).get("sponsors", []):
        if sponsor.get("enabled") and sponsor.get("notes"):
            lines.append((9998, BroadcastScheduleLine("—", f"Sponsor: {sponsor.get('name', 'Sponsor')}", "advertising")))

    lines.sort(key=lambda item: item[0])
    return [line for _, line in lines]


def _website_scheduler_status(config_manager) -> tuple[str, str]:
    folder = platform_path("automation_website", config_manager)
    if not folder.exists():
        return HEALTH_WARN, "Website scheduler folder not found"
    markers = ("running.lock", "engine.pid", ".running")
    running = any((folder / marker).exists() for marker in markers)
    script_count = len(list(folder.glob("*.bat"))) + len(list(folder.glob("*.ps1")))
    if running:
        return HEALTH_OK, f"Scheduler active · {script_count} script(s) in folder"
    if script_count:
        return HEALTH_WARN, f"Scheduler idle · {script_count} script(s) ready"
    return HEALTH_WARN, "Website scheduler folder has no start scripts yet"


def _build_radiodj_snapshot(settings: dict[str, Any], config_manager, dashboard) -> RadioDJSnapshot:
    integration = normalize_integration_settings(settings)
    live = build_live_system_status(settings)
    service = service_lookup(live, "RadioDJ")
    folder = platform_path("radiodj", config_manager)
    executable = integration.get("radiodj_executable", "").strip() or str(folder / "RadioDJ.exe")

    now_playing, artist, song = _parse_now_playing(dashboard.now_playing)
    queue_lines = _read_text_candidates(folder, ("queue.txt", "Queue.txt", "playlist.txt"))
    history_lines = _read_text_candidates(folder, ("history.txt", "History.txt", "recent.txt"))

    upcoming_lines: list[str] = []
    for event in dashboard.upcoming_events[:8]:
        upcoming_lines.append(
            f"{event.day} {event.start_time}–{event.end_time} · {event.show_name} · {event.personality}"
        )
    if not queue_lines and upcoming_lines:
        queue_lines = ["Queue view uses Studio schedule (read-only — no RadioDJ database access yet)."]
        queue_lines.extend(upcoming_lines[:6])

    if not history_lines:
        history_lines = dashboard.activity_log[:8] or ["No recent RadioDJ history file found."]

    return RadioDJSnapshot(
        running=bool(service and service.running),
        status=service.status if service else HEALTH_WARN,
        detail=service.detail if service else "RadioDJ status unavailable",
        executable=executable,
        folder=str(folder),
        current_artist=artist,
        current_song=song,
        now_playing=now_playing,
        queue_lines=queue_lines,
        upcoming_lines=upcoming_lines,
        history_lines=history_lines,
    )


def _build_alerts(
    config_manager,
    settings: dict[str, Any],
    live_status,
    audio_folders: list[AudioFolderSummary],
    schedule_conflicts: list[str],
) -> list[str]:
    alerts: list[str] = []

    radiodj = service_lookup(live_status, "RadioDJ")
    if radiodj and not radiodj.running:
        alerts.append(f"RadioDJ stopped — {radiodj.detail}")

    voicebox = service_lookup(live_status, "Voicebox")
    if voicebox and voicebox.status == HEALTH_ERROR:
        alerts.append(f"Voicebox disconnected — {voicebox.detail}")
    elif voicebox and not voicebox.running:
        alerts.append(f"Voicebox not responding — {voicebox.detail}")

    for service_name, label in (("LiveDJ Watcher", "LiveDJ watcher"), ("Request Watcher", "Request watcher")):
        service = service_lookup(live_status, service_name)
        if service and not service.running:
            alerts.append(f"{label} stopped — {service.detail}")

    for folder in audio_folders:
        if folder.status == HEALTH_ERROR:
            alerts.append(f"Audio issue in {folder.label}: {'; '.join(folder.issues)}")
        elif folder.status == HEALTH_WARN and folder.issues:
            alerts.append(f"{folder.label}: {'; '.join(folder.issues)}")

    alerts.extend(schedule_conflicts)

    stale_news = _news_stale_message(settings)
    if stale_news:
        alerts.append(stale_news)

    requests = service_lookup(live_status, "Request Watcher")
    if requests and not requests.running:
        alerts.append("Request system unavailable — watcher is not running")

    if not alerts:
        alerts.append("No active broadcast alerts. All monitored systems look ready.")
    return alerts


def build_broadcasting_snapshot(config_manager) -> BroadcastingSnapshot:
    if os.environ.get("STUDIO_VERIFY") == "1":
        return BroadcastingSnapshot(
            on_air_status="Verify Mode",
            current_song="—",
            current_artist="—",
            current_host="—",
            current_show="—",
            current_format="—",
            next_event="—",
            queue_overview=["Verify mode — background scans skipped."],
            recent_activity=["Verify mode active."],
            health_lights=[BroadcastHealthLight("RadioDJ", HEALTH_OK, "Verify mode")],
            alerts=["Verify mode — no live scans run."],
            radiodj=RadioDJSnapshot(
                running=False,
                status=HEALTH_OK,
                detail="Verify mode",
                executable="",
                folder="",
                current_artist="—",
                current_song="—",
                now_playing="—",
            ),
            website_scheduler_status=HEALTH_OK,
            website_scheduler_detail="Verify mode",
            safety_lines=["Verify mode"],
            last_refreshed=datetime.now().strftime("%I:%M:%S %p"),
        )

    settings = config_manager.load("settings", {})
    dashboard = build_dashboard_snapshot(config_manager)
    live_status = build_live_system_status(settings)

    now_playing, artist, song = _parse_now_playing(dashboard.now_playing)
    on_air = "On Air" if dashboard.current_event.show_name != "—" else "Off Air"

    health_lights = [
        BroadcastHealthLight(light.name, light.status, light.detail)
        for light in dashboard.station_lights
        if light.name in {"RadioDJ", "Voicebox", "LiveDJ", "News", "Requests", "Now Playing"}
    ]

    website_status, website_detail = _website_scheduler_status(config_manager)
    health_lights.append(BroadcastHealthLight("Website Scheduler", website_status, website_detail))

    audio_folders = [_scan_audio_folder(key, label, config_manager) for key, label in AUDIO_MONITOR_KEYS]

    schedule_data = normalize_schedule_data(config_manager.load("schedule", {"slots": []}), [])
    schedule_conflicts = _detect_schedule_conflicts(schedule_data.get("slots", []))

    radiodj = _build_radiodj_snapshot(settings, config_manager, dashboard)
    today_schedule = _build_today_schedule(config_manager)
    alerts = _build_alerts(config_manager, settings, live_status, audio_folders, schedule_conflicts)

    next_event = "—"
    if dashboard.upcoming_events:
        event = dashboard.upcoming_events[0]
        next_event = (
            f"{event.show_name} · {event.personality} · {event.day} "
            f"{event.start_time}–{event.end_time}"
        )

    queue_overview = radiodj.queue_lines[:8] or ["No queue information available yet."]

    activity = _collect_activity_log(limit=20)
    if not activity:
        for definition in MODULE_DEFINITIONS:
            log_path = _module_log_path(definition)
            if log_path.exists():
                try:
                    lines = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
                    activity.extend(line.strip() for line in reversed(lines) if line.strip())
                except OSError:
                    continue
            if len(activity) >= 12:
                break
        activity = activity[:12]

    safety = safety_summary(settings)
    safety_lines = [
        f"Operation mode: {safety['mode']}",
        "Live publishing and production changes remain disabled in Development Mode.",
        "RadioDJ database editing: disabled",
        "Task Scheduler changes: disabled",
        "Automatic production changes: disabled",
        "File deletion: disabled",
    ]

    return BroadcastingSnapshot(
        on_air_status=on_air,
        current_song=song,
        current_artist=artist,
        current_host=dashboard.on_air_personality,
        current_show=dashboard.current_event.show_name,
        current_format=dashboard.music_format,
        next_event=next_event,
        queue_overview=queue_overview,
        recent_activity=activity,
        health_lights=health_lights,
        alerts=alerts,
        radiodj=radiodj,
        audio_folders=audio_folders,
        today_schedule=today_schedule,
        website_scheduler_status=website_status,
        website_scheduler_detail=website_detail,
        safety_lines=safety_lines,
        last_refreshed=datetime.now().strftime("%I:%M:%S %p"),
    )


def resolve_radiodj_executable(settings: dict[str, Any], config_manager) -> Path | None:
    integration = normalize_integration_settings(settings)
    configured = integration.get("radiodj_executable", "").strip()
    if configured:
        path = Path(configured)
        if path.exists():
            return path
    folder = platform_path("radiodj", config_manager)
    if not folder.exists():
        return None
    for candidate in (folder / "RadioDJ.exe",):
        if candidate.exists():
            return candidate
    matches = sorted(folder.glob("RadioDJ.exe"))
    return matches[0] if matches else None

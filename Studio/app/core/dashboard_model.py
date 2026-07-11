"""Read-only dashboard data aggregation."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.paths import config_dir, logs_dir, studio_root
from app.core.personality_model import display_label as personality_label, normalize_personalities_data
from app.core.requests_model import normalize_requests_data, request_mode_label
from app.core.schedule_model import DAYS, normalize_schedule_data, time_to_minutes
from app.core.voice_model import display_label as voice_label, normalize_voice_library_data

logger = logging.getLogger("moplace.studio.dashboard")

HEALTH_OK = "ok"
HEALTH_WARN = "warn"
HEALTH_ERROR = "error"


@dataclass
class ScheduleEventView:
    show_name: str = "—"
    personality: str = "—"
    music_format: str = "—"
    day: str = ""
    start_time: str = ""
    end_time: str = ""
    requests_enabled: bool = True


@dataclass
class HealthIndicator:
    name: str
    status: str
    detail: str


@dataclass
class DashboardSnapshot:
    clock: str = ""
    clock_date: str = ""
    on_air_personality: str = "—"
    music_format: str = "—"
    current_event: ScheduleEventView = field(default_factory=ScheduleEventView)
    next_event: ScheduleEventView = field(default_factory=ScheduleEventView)
    request_mode: str = "Requests by Schedule"
    queue_status: str = "—"
    news_status: str = "—"
    livedj_status: str = "—"
    voicebox_status: str = "—"
    last_livedj_run: str = "Not monitored"
    last_news_run: str = "Not monitored"
    last_requests_run: str = "Not monitored"
    last_studio_run: str = "—"
    health_indicators: list[HealthIndicator] = field(default_factory=list)
    activity_log: list[str] = field(default_factory=list)


def _now_parts() -> tuple[str, str, str, int]:
    now = datetime.now()
    weekday = DAYS[now.weekday()]
    clock = now.strftime("%I:%M:%S %p")
    clock_date = now.strftime("%A, %B %d, %Y")
    minutes = now.hour * 60 + now.minute
    return weekday, clock, clock_date, minutes


def _slot_matches_now(slot: dict[str, Any], day: str, minutes: int) -> bool:
    if slot.get("day", "").lower() != day:
        return False
    try:
        start = time_to_minutes(slot.get("start_time", "00:00"))
        end = time_to_minutes(slot.get("end_time", "00:00"))
    except ValueError:
        return False
    return start <= minutes < end


def _slot_sort_key(slot: dict[str, Any]) -> tuple[int, int]:
    day_index = DAYS.index(slot.get("day", "monday").lower()) if slot.get("day", "").lower() in DAYS else 0
    try:
        start = time_to_minutes(slot.get("start_time", "00:00"))
    except ValueError:
        start = 0
    return day_index, start


def _event_view(slot: dict[str, Any] | None, personalities: dict[str, dict[str, Any]]) -> ScheduleEventView:
    if not slot:
        return ScheduleEventView()
    personality_id = slot.get("personality_id", "")
    personality = personalities.get(personality_id, {})
    return ScheduleEventView(
        show_name=slot.get("show_name", "—"),
        personality=personality_label(personality) if personality else personality_id or "—",
        music_format=slot.get("music_format", "—"),
        day=slot.get("day", "").title(),
        start_time=slot.get("start_time", ""),
        end_time=slot.get("end_time", ""),
        requests_enabled=slot.get("requests_enabled", True),
    )


def _find_current_and_next_slots(
    slots: list[dict[str, Any]], day: str, minutes: int
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    current = next((slot for slot in slots if _slot_matches_now(slot, day, minutes)), None)

    upcoming: list[tuple[int, dict[str, Any]]] = []
    day_index = DAYS.index(day)
    for slot in slots:
        try:
            start = time_to_minutes(slot.get("start_time", "00:00"))
        except ValueError:
            continue
        slot_day = slot.get("day", "").lower()
        if slot_day not in DAYS:
            continue
        slot_day_index = DAYS.index(slot_day)
        offset = (slot_day_index - day_index) % 7
        if offset == 0 and start <= minutes:
            if current and slot.get("id") == current.get("id"):
                continue
            if start <= minutes:
                continue
        absolute_minutes = offset * 24 * 60 + start
        upcoming.append((absolute_minutes, slot))

    upcoming.sort(key=lambda item: item[0])
    next_slot = upcoming[0][1] if upcoming else None
    return current, next_slot


def _config_health(name: str) -> HealthIndicator:
    path = config_dir() / f"{name}.json"
    if not path.exists():
        return HealthIndicator(name, HEALTH_ERROR, "Missing configuration file")
    try:
        with path.open("r", encoding="utf-8") as handle:
            json.load(handle)
        modified = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %I:%M %p")
        return HealthIndicator(name, HEALTH_OK, f"OK · updated {modified}")
    except (OSError, json.JSONDecodeError) as exc:
        return HealthIndicator(name, HEALTH_ERROR, f"Invalid JSON: {exc}")


def _automation_folder_status(folder_name: str) -> tuple[str, str]:
    folder = studio_root().parent / "Automation" / folder_name
    if not folder.exists():
        return "External (folder missing)", HEALTH_WARN
    if any(folder.iterdir()):
        return "External engine present", HEALTH_OK
    return "External (not controlled by Studio)", HEALTH_WARN


def _last_log_timestamp(log_path: Path) -> str:
    if not log_path.exists():
        return "Not monitored"
    try:
        lines = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        for line in reversed(lines):
            if line.strip():
                return line[:19] if len(line) >= 19 else line
    except OSError:
        return "Not monitored"
    return "Not monitored"


def _recent_activity(limit: int = 8) -> list[str]:
    log_file = logs_dir() / "studio.log"
    if not log_file.exists():
        return ["No Studio activity logged yet."]
    try:
        lines = log_file.read_text(encoding="utf-8", errors="ignore").splitlines()
        recent = [line for line in lines if line.strip()][-limit:]
        return recent or ["No Studio activity logged yet."]
    except OSError:
        return ["Unable to read Studio activity log."]


def build_dashboard_snapshot(config_manager) -> DashboardSnapshot:
    day, clock, clock_date, minutes = _now_parts()

    personalities_data = normalize_personalities_data(config_manager.load("personalities", {"personalities": []}))
    personalities = {item["id"]: item for item in personalities_data.get("personalities", [])}
    personality_ids = list(personalities.keys())

    schedule_data = normalize_schedule_data(config_manager.load("schedule", {"slots": []}), personality_ids)
    slots = schedule_data.get("slots", [])

    requests_data = normalize_requests_data(config_manager.load("requests", {}))
    voices_data = normalize_voice_library_data(config_manager.load("voice_library", {"voices": []}))
    voices = voices_data.get("voices", [])

    current_slot, next_slot = _find_current_and_next_slots(slots, day, minutes)
    current_event = _event_view(current_slot, personalities)
    next_event = _event_view(next_slot, personalities)

    active_voices = [voice for voice in voices if voice.get("active", True) and voice.get("voicebox_id")]
    request_mode = request_mode_label(requests_data.get("request_mode", "by_schedule"))
    max_queue = requests_data.get("max_active_queue", 0)
    if requests_data.get("request_mode") == "disabled":
        queue_status = "Requests disabled"
        queue_health = HEALTH_WARN
    else:
        queue_status = f"Configured max queue: {max_queue}"
        queue_health = HEALTH_OK

    news_text, news_health = _automation_folder_status("News")
    livedj_text, livedj_health = _automation_folder_status("LiveDJ")
    requests_text, requests_health = _automation_folder_status("Requests")

    if active_voices:
        voicebox_status = f"{len(active_voices)} active Voicebox voice(s)"
        voicebox_health = HEALTH_OK
    elif voices:
        voicebox_status = "No active Voicebox voices"
        voicebox_health = HEALTH_WARN
    else:
        voicebox_status = "No voices configured"
        voicebox_health = HEALTH_ERROR

    health = [
        _config_health("personalities"),
        _config_health("voice_library"),
        _config_health("schedule"),
        _config_health("requests"),
        _config_health("settings"),
        HealthIndicator("News", news_health, news_text),
        HealthIndicator("LiveDJ", livedj_health, livedj_text),
        HealthIndicator("Requests Engine", requests_health, requests_text),
        HealthIndicator("Voicebox", voicebox_health, voicebox_status),
        HealthIndicator("Queue", queue_health, queue_status),
    ]

    on_air = current_event.personality if current_slot else "Off air / no scheduled block"
    music_format = current_event.music_format if current_slot else "—"

    return DashboardSnapshot(
        clock=clock,
        clock_date=clock_date,
        on_air_personality=on_air,
        music_format=music_format,
        current_event=current_event,
        next_event=next_event,
        request_mode=request_mode,
        queue_status=queue_status,
        news_status=news_text,
        livedj_status=livedj_text,
        voicebox_status=voicebox_status,
        last_livedj_run=_last_log_timestamp(studio_root().parent / "Automation" / "LiveDJ" / "studio.log"),
        last_news_run=_last_log_timestamp(studio_root().parent / "Automation" / "News" / "studio.log"),
        last_requests_run=_last_log_timestamp(studio_root().parent / "Automation" / "Requests" / "studio.log"),
        last_studio_run=_last_log_timestamp(logs_dir() / "studio.log"),
        health_indicators=health,
        activity_log=_recent_activity(),
    )

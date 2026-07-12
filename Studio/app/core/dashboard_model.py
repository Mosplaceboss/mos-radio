"""Read-only dashboard data aggregation."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.automation_model import MODULE_DEFINITIONS, _collect_activity_log
from app.core.health_constants import HEALTH_ERROR, HEALTH_OK, HEALTH_WARN
from app.core.live_connector import now_playing_path
from app.core.platform_manager import automation_module_dir
from app.core.paths import automation_logs_dir, logs_dir, studio_root
from app.core.personality_model import display_label as personality_label, normalize_personalities_data
from app.core.requests_model import normalize_requests_data, request_mode_label
from app.core.schedule_model import DAYS, normalize_schedule_data, time_to_minutes
from app.core.system_status import build_live_system_status, service_lookup
from app.core.voice_model import normalize_voice_library_data

logger = logging.getLogger("moplace.studio.dashboard")


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
class StatusLight:
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
    request_mode: str = "Requests by Schedule"
    now_playing: str = "—"
    station_lights: list[StatusLight] = field(default_factory=list)
    upcoming_events: list[ScheduleEventView] = field(default_factory=list)
    last_news_run: str = "Not monitored"
    last_livedj_run: str = "Not monitored"
    last_request_run: str = "Not monitored"
    last_voice_generation: str = "Not monitored"
    last_rss_update: str = "Not monitored"
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


def _find_current_slot(slots: list[dict[str, Any]], day: str, minutes: int) -> dict[str, Any] | None:
    return next((slot for slot in slots if _slot_matches_now(slot, day, minutes)), None)


def _find_upcoming_slots(
    slots: list[dict[str, Any]], day: str, minutes: int, limit: int = 5
) -> list[dict[str, Any]]:
    day_index = DAYS.index(day)
    upcoming: list[tuple[int, dict[str, Any]]] = []

    for slot in slots:
        slot_day = slot.get("day", "").lower()
        if slot_day not in DAYS:
            continue
        try:
            start = time_to_minutes(slot.get("start_time", "00:00"))
        except ValueError:
            continue
        slot_day_index = DAYS.index(slot_day)
        offset = (slot_day_index - day_index) % 7
        if offset == 0 and start <= minutes:
            continue
        absolute_minutes = offset * 24 * 60 + start
        upcoming.append((absolute_minutes, slot))

    upcoming.sort(key=lambda item: item[0])
    return [slot for _, slot in upcoming[:limit]]


def _module_log_path(folder_name: str, log_name: str) -> Path:
    studio_log = automation_logs_dir() / log_name
    if studio_log.exists():
        return studio_log
    engine_log = automation_module_dir(folder_name) / log_name
    if engine_log.exists():
        return engine_log
    return studio_log


def _last_log_timestamp(log_path: Path) -> str:
    if not log_path.exists():
        return "Not monitored"
    try:
        lines = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        for line in reversed(lines):
            if line.strip():
                return line[:80] if len(line) > 80 else line
    except OSError:
        return "Not monitored"
    return "Not monitored"


def _last_matching_log(keywords: tuple[str, ...], sources: list[Path]) -> str:
    pattern = re.compile("|".join(re.escape(keyword) for keyword in keywords), re.IGNORECASE)
    matches: list[str] = []

    for source in sources:
        if not source.exists():
            continue
        try:
            lines = source.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for line in reversed(lines):
            text = line.strip()
            if text and pattern.search(text):
                matches.append(text[:100])

    if not matches:
        return "Not monitored"
    return matches[0]


def _read_now_playing(settings: dict[str, Any] | None = None) -> str:
    candidates: list[Path] = []
    if settings:
        configured = now_playing_path(settings)
        if configured:
            candidates.append(configured)
    candidates.extend(
        (
            studio_root().parent / "nowplaying-live.txt",
            studio_root() / "nowplaying-live.txt",
            logs_dir() / "nowplaying.txt",
        )
    )
    for path in candidates:
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore").strip()
            if text:
                return text.splitlines()[0][:120]
        except OSError:
            continue
    return "—"


def _system_health_lookup(system_health: list[Any], name: str) -> tuple[str, str]:
    for item in system_health:
        if item.name == name:
            return item.status, item.detail
    return HEALTH_WARN, "Not monitored"


def _service_light(live_status, service_name: str, display_name: str) -> StatusLight:
    service = service_lookup(live_status, service_name)
    if not service:
        return StatusLight(display_name, HEALTH_WARN, "Not monitored")
    return StatusLight(display_name, service.status, service.detail)


def build_dashboard_snapshot(config_manager) -> DashboardSnapshot:
    day, clock, clock_date, minutes = _now_parts()

    personalities_data = normalize_personalities_data(config_manager.load("personalities", {"personalities": []}))
    personalities = {item["id"]: item for item in personalities_data.get("personalities", [])}
    personality_ids = list(personalities.keys())

    schedule_data = normalize_schedule_data(config_manager.load("schedule", {"slots": []}), personality_ids)
    slots = schedule_data.get("slots", [])

    requests_data = normalize_requests_data(config_manager.load("requests", {}))
    request_mode = request_mode_label(requests_data.get("request_mode", "by_schedule"))

    current_slot = _find_current_slot(slots, day, minutes)
    current_event = _event_view(current_slot, personalities)
    upcoming_slots = _find_upcoming_slots(slots, day, minutes, limit=5)
    upcoming_events = [_event_view(slot, personalities) for slot in upcoming_slots]

    settings = config_manager.load("settings", {})
    live_status = build_live_system_status(settings)

    now_playing = _read_now_playing(settings)
    if now_playing == "—" and current_slot:
        now_playing = f"{current_event.show_name} · {current_event.personality}"

    if current_slot:
        now_playing_status = HEALTH_OK
        now_playing_detail = now_playing if now_playing != "—" else current_event.show_name
    else:
        now_playing_status = HEALTH_WARN
        now_playing_detail = "No scheduled event on air"

    station_lights = [
        _service_light(live_status, "LiveDJ Watcher", "LiveDJ"),
        _service_light(live_status, "News Tasks", "News"),
        _service_light(live_status, "Request Watcher", "Requests"),
        _service_light(live_status, "Voicebox", "Voicebox"),
        _service_light(live_status, "RadioDJ", "RadioDJ"),
        _service_light(live_status, "Internet", "Internet"),
        StatusLight("Now Playing", now_playing_status, now_playing_detail),
    ]

    log_sources = [logs_dir() / "studio.log", automation_logs_dir() / "automation.log"]
    for definition in MODULE_DEFINITIONS:
        log_sources.append(_module_log_path(definition["folder"], definition["log_name"]))

    on_air = current_event.personality if current_slot else "Off air / no scheduled block"
    music_format = current_event.music_format if current_slot else "—"

    return DashboardSnapshot(
        clock=clock,
        clock_date=clock_date,
        on_air_personality=on_air,
        music_format=music_format,
        current_event=current_event,
        request_mode=request_mode,
        now_playing=now_playing,
        station_lights=station_lights,
        upcoming_events=upcoming_events,
        last_news_run=_last_log_timestamp(_module_log_path("News", "news.log")),
        last_livedj_run=_last_log_timestamp(_module_log_path("LiveDJ", "livedj.log")),
        last_request_run=_last_log_timestamp(_module_log_path("Requests", "requests.log")),
        last_voice_generation=_last_matching_log(
            ("voice", "voicebox", "generated", "greeting", "break", "dj mo"),
            log_sources,
        ),
        last_rss_update=_last_matching_log(("rss", "feed", "news update", "headline"), log_sources),
        activity_log=_collect_activity_log(limit=16),
    )

"""Programming Manager data models, validation, and dashboard aggregation."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4

from app.core.personality_model import display_label, normalize_personalities_data
from app.core.programming_storage import (
    events_path,
    load_programming_bundle,
    save_programming_bundle,
    shows_path,
)
from app.core.schedule_model import DAYS, time_to_minutes
from app.core.voice_model import normalize_voice_library_data

SHOW_CATEGORIES = (
    ("morning", "Morning Show"),
    ("midday", "Midday"),
    ("afternoons", "Afternoons"),
    ("evenings", "Evenings"),
    ("weekends", "Weekends"),
    ("specialty", "Specialty Shows"),
)

DEFAULT_SHOWS = (
    {"name": "Morning Show", "category": "morning"},
    {"name": "Midday", "category": "midday"},
    {"name": "Afternoons", "category": "afternoons"},
    {"name": "Evenings", "category": "evenings"},
    {"name": "Weekend Brunch", "category": "weekends"},
    {"name": "Sunday Morning Blues", "category": "specialty"},
)

DEFAULT_FORMATS = (
    "Classic Rock",
    "Daily Mix",
    "Trop Rock",
    "Blues",
    "Casey",
    "Future Formats",
)

DEFAULT_CLOCKS = (
    ("music", "Music"),
    ("sweepers", "Sweepers"),
    ("news", "News"),
    ("commercials", "Commercials"),
    ("requests", "Requests"),
    ("voice_tracks", "Voice Tracks"),
)


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


def default_shows() -> list[dict[str, Any]]:
    return [
        {
            "id": _new_id("show"),
            "name": item["name"],
            "category": item["category"],
            "description": "",
            "enabled": True,
            "default_format_id": "",
            "primary_personality_id": "",
            "backup_personality_id": "",
            "voice_id": "",
        }
        for item in DEFAULT_SHOWS
    ]


def default_formats() -> list[dict[str, Any]]:
    return [
        {
            "id": _new_id("fmt"),
            "name": name,
            "enabled": name != "Future Formats",
            "description": "",
        }
        for name in DEFAULT_FORMATS
    ]


def default_clocks() -> list[dict[str, Any]]:
    return [
        {
            "id": _new_id("clock"),
            "name": label,
            "segment_type": segment,
            "enabled": True,
            "duration_minutes": 0,
            "notes": "",
        }
        for segment, label in DEFAULT_CLOCKS
    ]


def normalize_shows(data: dict[str, Any] | None) -> dict[str, Any]:
    shows = data.get("shows", []) if data else []
    if not shows:
        shows = default_shows()
    normalized = []
    for item in shows:
        record = deepcopy(item)
        record.setdefault("id", _new_id("show"))
        record.setdefault("name", "Untitled Show")
        record.setdefault("category", "specialty")
        record.setdefault("description", "")
        record.setdefault("enabled", True)
        record.setdefault("default_format_id", "")
        record.setdefault("primary_personality_id", "")
        record.setdefault("backup_personality_id", "")
        record.setdefault("voice_id", "")
        normalized.append(record)
    return {"shows": normalized}


def normalize_formats(data: dict[str, Any] | None) -> dict[str, Any]:
    formats = data.get("formats", []) if data else []
    if not formats:
        formats = default_formats()
    normalized = []
    for item in formats:
        record = deepcopy(item)
        record.setdefault("id", _new_id("fmt"))
        record.setdefault("name", "Format")
        record.setdefault("enabled", True)
        record.setdefault("description", "")
        normalized.append(record)
    return {"formats": normalized}


def normalize_clocks(data: dict[str, Any] | None) -> dict[str, Any]:
    clocks = data.get("clocks", []) if data else []
    if not clocks:
        clocks = default_clocks()
    normalized = []
    for item in clocks:
        record = deepcopy(item)
        record.setdefault("id", _new_id("clock"))
        record.setdefault("name", "Segment")
        record.setdefault("segment_type", "music")
        record.setdefault("enabled", True)
        record.setdefault("duration_minutes", 0)
        record.setdefault("notes", "")
        normalized.append(record)
    return {"clocks": normalized}


def normalize_events(data: dict[str, Any] | None) -> dict[str, Any]:
    events = data.get("events", []) if data else []
    normalized = []
    for item in events:
        record = deepcopy(item)
        record.setdefault("id", _new_id("evt"))
        record.setdefault("show_id", "")
        record.setdefault("day", "monday")
        record.setdefault("start_time", "06:00")
        record.setdefault("end_time", "07:00")
        record.setdefault("format_id", "")
        record.setdefault("personality_id", "")
        record.setdefault("show_name", "")
        record.setdefault("music_format", "")
        record.setdefault("enabled", True)
        record.setdefault("notes", "")
        normalized.append(record)
    return {
        "timezone": data.get("timezone", "America/New_York") if data else "America/New_York",
        "events": normalized,
    }


def normalize_assignments(data: dict[str, Any] | None) -> dict[str, Any]:
    assignments = data.get("assignments", []) if data else []
    normalized = []
    for item in assignments:
        record = deepcopy(item)
        record.setdefault("id", _new_id("asg"))
        record.setdefault("show_id", "")
        record.setdefault("primary_personality_id", "")
        record.setdefault("backup_personality_id", "")
        record.setdefault("voice_id", "")
        normalized.append(record)
    return {"assignments": normalized}


def normalize_overrides(data: dict[str, Any] | None) -> dict[str, Any]:
    overrides = data.get("overrides", []) if data else []
    normalized = []
    for item in overrides:
        record = deepcopy(item)
        record.setdefault("id", _new_id("ovr"))
        record.setdefault("override_type", "temporary")
        record.setdefault("label", "")
        record.setdefault("date", "")
        record.setdefault("day", "")
        record.setdefault("enabled", True)
        record.setdefault("notes", "")
        record.setdefault("events", [])
        normalized.append(record)
    return {"overrides": normalized}


def normalize_bundle(raw: dict[str, Any] | None) -> dict[str, Any]:
    raw = raw or {}
    return {
        "shows": normalize_shows(raw.get("shows")),
        "formats": normalize_formats(raw.get("formats")),
        "clocks": normalize_clocks(raw.get("clocks")),
        "events": normalize_events(raw.get("events")),
        "assignments": normalize_assignments(raw.get("assignments")),
        "overrides": normalize_overrides(raw.get("overrides")),
        "state": raw.get("state") or {"last_validated": "", "version": 1},
    }


def ensure_programming_data(config_manager=None) -> None:
    if not shows_path(config_manager).exists():
        normalized = normalize_bundle({})
        save_programming_bundle(normalized, config_manager)
        return

    bundle = normalize_bundle(load_programming_bundle(config_manager))
    if not bundle["events"]["events"] and config_manager is not None:
        schedule = config_manager.load("schedule", {"slots": []})
        bundle["events"]["events"] = seed_events_from_studio_schedule(schedule, bundle["shows"]["shows"])
        bundle["events"]["timezone"] = schedule.get("timezone", "America/New_York")
        save_programming_bundle(bundle, config_manager)


def _slot_overlaps(a: dict[str, Any], b: dict[str, Any]) -> bool:
    if a.get("day", "").lower() != b.get("day", "").lower():
        return False
    if not a.get("enabled", True) or not b.get("enabled", True):
        return False
    try:
        a_start = time_to_minutes(a.get("start_time", "00:00"))
        a_end = time_to_minutes(a.get("end_time", "00:00"))
        b_start = time_to_minutes(b.get("start_time", "00:00"))
        b_end = time_to_minutes(b.get("end_time", "00:00"))
    except ValueError:
        return False
    return a_start < b_end and b_start < a_end


def validate_programming(
    bundle: dict[str, Any],
    personalities: list[dict[str, Any]] | None = None,
    voices: list[dict[str, Any]] | None = None,
) -> list[str]:
    warnings: list[str] = []
    shows = {item["id"]: item for item in bundle["shows"]["shows"]}
    formats = {item["id"]: item for item in bundle["formats"]["formats"]}
    events = [event for event in bundle["events"]["events"] if event.get("enabled", True)]
    personality_ids = {item["id"] for item in (personalities or [])}
    voice_ids = {item["id"] for item in (voices or [])}

    for show in bundle["shows"]["shows"]:
        if not show.get("enabled", True):
            continue
        if not show.get("primary_personality_id"):
            warnings.append(f"Show '{show['name']}' is missing a primary host.")
        elif show["primary_personality_id"] not in personality_ids:
            warnings.append(f"Show '{show['name']}' primary host is not in Personalities.")
        if show.get("voice_id") and show["voice_id"] not in voice_ids:
            warnings.append(f"Show '{show['name']}' voice is not in Voice Library.")

    enabled_clocks = [clock for clock in bundle["clocks"]["clocks"] if clock.get("enabled", True)]
    if not enabled_clocks:
        warnings.append("No clock segments are enabled.")

    for index, event in enumerate(events):
        label = event.get("show_name") or event.get("id", f"Event {index + 1}")
        if not event.get("personality_id"):
            warnings.append(f"Event '{label}' is missing a personality.")
        if not event.get("format_id") and not event.get("music_format"):
            warnings.append(f"Event '{label}' is missing a format.")
        for other in events[index + 1 :]:
            if _slot_overlaps(event, other):
                warnings.append(
                    f"Schedule conflict on {event.get('day', '').title()}: "
                    f"{event.get('start_time')} overlaps {other.get('start_time')}."
                )

    for fmt in bundle["formats"]["formats"]:
        if fmt["name"] == "Future Formats" and fmt.get("enabled"):
            warnings.append("Future Formats is enabled but not yet configured.")

    if not warnings:
        warnings.append("No validation issues found.")
    return warnings


@dataclass
class ProgrammingDashboard:
    current_show: str = "—"
    next_show: str = "—"
    current_format: str = "—"
    upcoming_changes: list[str] = field(default_factory=list)
    validation_warnings: list[str] = field(default_factory=list)
    current_programming: list[str] = field(default_factory=list)
    upcoming_programming: list[str] = field(default_factory=list)


def _event_matches_now(event: dict[str, Any], day: str, minutes: int) -> bool:
    if event.get("day", "").lower() != day or not event.get("enabled", True):
        return False
    try:
        start = time_to_minutes(event.get("start_time", "00:00"))
        end = time_to_minutes(event.get("end_time", "00:00"))
    except ValueError:
        return False
    return start <= minutes < end


def _upcoming_events(events: list[dict[str, Any]], day: str, minutes: int, limit: int = 5) -> list[dict[str, Any]]:
    day_index = DAYS.index(day)
    ranked: list[tuple[int, dict[str, Any]]] = []
    for event in events:
        if not event.get("enabled", True):
            continue
        event_day = event.get("day", "").lower()
        if event_day not in DAYS:
            continue
        try:
            start = time_to_minutes(event.get("start_time", "00:00"))
        except ValueError:
            continue
        event_day_index = DAYS.index(event_day)
        offset = (event_day_index - day_index) % 7
        if offset == 0 and start <= minutes:
            continue
        ranked.append((offset * 24 * 60 + start, event))
    ranked.sort(key=lambda item: item[0])
    return [event for _, event in ranked[:limit]]


def build_programming_dashboard(bundle: dict[str, Any], warnings: list[str]) -> ProgrammingDashboard:
    now = datetime.now()
    day = DAYS[now.weekday()]
    minutes = now.hour * 60 + now.minute
    events = bundle["events"]["events"]
    formats = {item["id"]: item["name"] for item in bundle["formats"]["formats"]}

    current = next((event for event in events if _event_matches_now(event, day, minutes)), None)
    upcoming = _upcoming_events(events, day, minutes, limit=5)

    if current:
        current_show = current.get("show_name") or "Scheduled Event"
        fmt = formats.get(current.get("format_id", ""), current.get("music_format", "—"))
        current_format = fmt or "—"
        current_programming = [
            f"{current.get('day', '').title()} {current.get('start_time')}–{current.get('end_time')} · {current_show}"
        ]
    else:
        current_show = "No show scheduled"
        current_format = "—"
        current_programming = ["Nothing scheduled for right now."]

    if upcoming:
        next_event = upcoming[0]
        next_show = (
            f"{next_event.get('show_name', 'Event')} · {next_event.get('day', '').title()} "
            f"{next_event.get('start_time')}–{next_event.get('end_time')}"
        )
        upcoming_programming = [
            f"{event.get('show_name', 'Event')} · {event.get('day', '').title()} "
            f"{event.get('start_time')}–{event.get('end_time')}"
            for event in upcoming
        ]
    else:
        next_show = "No upcoming events"
        upcoming_programming = ["No upcoming programming scheduled."]

    upcoming_changes = [
        f"{override.get('label') or override.get('override_type', 'Override')} · {override.get('date') or override.get('day', '')}"
        for override in bundle["overrides"]["overrides"]
        if override.get("enabled", True)
    ]
    if not upcoming_changes:
        upcoming_changes = ["No holiday or temporary overrides scheduled."]

    return ProgrammingDashboard(
        current_show=current_show,
        next_show=next_show,
        current_format=current_format,
        upcoming_changes=upcoming_changes,
        validation_warnings=warnings[:8],
        current_programming=current_programming,
        upcoming_programming=upcoming_programming,
    )


def copy_day_events(events: list[dict[str, Any]], source_day: str, target_day: str) -> list[dict[str, Any]]:
    source = source_day.lower()
    target = target_day.lower()
    copied = deepcopy(events)
    for event in events:
        if event.get("day", "").lower() != source:
            continue
        clone = deepcopy(event)
        clone["id"] = _new_id("evt")
        clone["day"] = target
        copied.append(clone)
    return copied


def copy_week_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    copied = deepcopy(events)
    for event in events:
        clone = deepcopy(event)
        clone["id"] = _new_id("evt")
        clone["notes"] = (clone.get("notes", "") + " (week copy)").strip()
        copied.append(clone)
    return copied


def seed_events_from_studio_schedule(schedule_data: dict[str, Any], shows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    show_by_name = {show["name"].lower(): show["id"] for show in shows}
    events = []
    for slot in schedule_data.get("slots", []):
        show_name = slot.get("show_name", "")
        events.append(
            {
                "id": _new_id("evt"),
                "show_id": show_by_name.get(show_name.lower(), ""),
                "day": slot.get("day", "monday"),
                "start_time": slot.get("start_time", "06:00"),
                "end_time": slot.get("end_time", "07:00"),
                "format_id": "",
                "personality_id": slot.get("personality_id", ""),
                "show_name": show_name,
                "music_format": slot.get("music_format", ""),
                "enabled": True,
                "notes": slot.get("notes", ""),
            }
        )
    return events

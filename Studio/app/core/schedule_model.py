"""Schedule slot schema, time utilities, and validation."""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import uuid4

DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")

PERSONALITY_COLORS = (
    "#2d6a9f",
    "#5b3a8c",
    "#2a9d8f",
    "#e76f51",
    "#f4a261",
    "#264653",
    "#8338ec",
    "#fb5607",
    "#3a86ff",
    "#ff006e",
)

TIME_OPTIONS = tuple(
    f"{hour:02d}:{minute:02d}"
    for hour in range(24)
    for minute in (0, 30)
)

DEFAULT_SLOT_DURATION_MINUTES = 60


def new_slot_id() -> str:
    return f"slot-{uuid4().hex[:8]}"


def time_to_minutes(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def minutes_to_time(total_minutes: int) -> str:
    total_minutes = max(0, min(total_minutes, 24 * 60))
    hour, minute = divmod(total_minutes, 60)
    return f"{hour:02d}:{minute:02d}"


def time_to_index(value: str) -> int:
    minutes = time_to_minutes(value)
    if minutes % 30 != 0:
        raise ValueError(f"Time '{value}' is not aligned to 30-minute increments.")
    return minutes // 30


def index_to_time(index: int) -> str:
    return minutes_to_time(index * 30)


def slot_rowspan(start_time: str, end_time: str) -> int:
    span = time_to_index(end_time) - time_to_index(start_time)
    return max(span, 1)


def color_for_personality(personality_id: str, personality_ids: list[str]) -> str:
    if not personality_id:
        return PERSONALITY_COLORS[0]
    if personality_id in personality_ids:
        return PERSONALITY_COLORS[personality_ids.index(personality_id) % len(PERSONALITY_COLORS)]
    return PERSONALITY_COLORS[hash(personality_id) % len(PERSONALITY_COLORS)]


def normalize_slot(raw: dict[str, Any], personality_ids: list[str] | None = None) -> dict[str, Any]:
    record = deepcopy(raw)
    record.setdefault("id", new_slot_id())
    record.setdefault("day", "monday")
    record.setdefault("start_time", "06:00")
    record.setdefault("end_time", minutes_to_time(time_to_minutes("06:00") + DEFAULT_SLOT_DURATION_MINUTES))
    record.setdefault("personality_id", "")
    record.setdefault("show_name", "")
    record.setdefault("music_format", "")
    record.setdefault("requests_enabled", True)
    record.setdefault("notes", "")

    ids = personality_ids or []
    record["color"] = color_for_personality(record.get("personality_id", ""), ids)
    return record


def normalize_schedule_data(data: dict[str, Any], personality_ids: list[str] | None = None) -> dict[str, Any]:
    ids = personality_ids or []
    slots = [normalize_slot(item, ids) for item in data.get("slots", [])]
    return {
        "timezone": data.get("timezone", "America/New_York"),
        "slots": slots,
    }


def validate_slot(slot: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not slot.get("personality_id"):
        errors.append("Personality is required.")
    if not slot.get("show_name", "").strip():
        errors.append("Show name is required.")
    try:
        start_index = time_to_index(slot.get("start_time", "00:00"))
        end_index = time_to_index(slot.get("end_time", "00:30"))
    except ValueError as exc:
        errors.append(str(exc))
        return errors
    if end_index <= start_index:
        errors.append("End time must be after start time.")
    if slot.get("day", "").lower() not in DAYS:
        errors.append("Day must be a valid weekday.")
    return errors


def default_end_time(start_time: str, duration_minutes: int = DEFAULT_SLOT_DURATION_MINUTES) -> str:
    return minutes_to_time(time_to_minutes(start_time) + duration_minutes)

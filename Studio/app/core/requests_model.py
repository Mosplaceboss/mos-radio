"""Request settings schema, normalization, and validation."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

COOLDOWN_PRESETS = (
    ("1", "1 hour", 1),
    ("2", "2 hours", 2),
    ("3", "3 hours", 3),
    ("4", "4 hours", 4),
    ("6", "6 hours", 6),
    ("8", "8 hours", 8),
    ("12", "12 hours", 12),
    ("24", "24 hours", 24),
    ("custom", "Custom", None),
)

DEFAULT_LIMIT_MESSAGE = "You've reached your request limit. Please try again later."
DEFAULT_NOT_FOUND_EMAIL = "requests@mosplaceradio.com"

REQUEST_MODES = (
    ("24_7", "24/7 Requests"),
    ("by_schedule", "Requests by Schedule"),
    ("disabled", "Requests Disabled"),
)

REQUEST_MODE_LABELS = {mode_id: label for mode_id, label in REQUEST_MODES}


def request_mode_label(mode: str) -> str:
    return REQUEST_MODE_LABELS.get(mode, "Requests by Schedule")


def is_requests_active(data: dict[str, Any]) -> bool:
    return data.get("request_mode", "by_schedule") != "disabled"


def normalize_requests_data(data: dict[str, Any]) -> dict[str, Any]:
    record = deepcopy(data)

    if "requests_per_listener" not in record and "per_user_limit" in record:
        record["requests_per_listener"] = record.pop("per_user_limit")

    if "max_active_queue" not in record and "max_queue_length" in record:
        record["max_active_queue"] = record.pop("max_queue_length")

    if "intro_announcement_enabled" not in record and "announce_requests" in record:
        record["intro_announcement_enabled"] = record.pop("announce_requests")

    if "cooldown_hours" not in record:
        seconds = record.pop("cooldown_seconds", 7200)
        record["cooldown_hours"] = max(1, int(seconds / 3600)) if seconds else 2

    record.pop("cooldown_seconds", None)
    record.pop("per_user_period_hours", None)
    record.pop("duplicate_track_cooldown_minutes", None)

    record.setdefault("enabled", True)
    record.setdefault("request_mode", _resolve_request_mode(record))
    record["enabled"] = is_requests_active(record)
    record.setdefault("requests_per_listener", 3)
    record.setdefault("cooldown_preset", _preset_for_hours(record.get("cooldown_hours", 2)))
    record.setdefault("cooldown_custom_hours", 2)
    record.setdefault("opening_time", "06:00")
    record.setdefault("closing_time", "23:00")
    record.setdefault("max_active_queue", 50)
    record.setdefault("allowed_formats", [])
    record.setdefault("disable_during_specialty_shows", True)
    record.setdefault("intro_announcement_enabled", True)
    record.setdefault("song_not_found_email", DEFAULT_NOT_FOUND_EMAIL)
    record.setdefault("limit_reached_message", DEFAULT_LIMIT_MESSAGE)

    formats = record.get("allowed_formats", [])
    if isinstance(formats, str):
        record["allowed_formats"] = [item.strip() for item in formats.split(",") if item.strip()]
    elif not isinstance(formats, list):
        record["allowed_formats"] = []

    record["cooldown_hours"] = effective_cooldown_hours(record)
    return record


def _resolve_request_mode(record: dict[str, Any]) -> str:
    mode = record.get("request_mode")
    if mode in REQUEST_MODE_LABELS:
        return mode
    if not record.get("enabled", True):
        return "disabled"
    return "by_schedule"


def _preset_for_hours(hours: int | float) -> str:
    hour_value = int(hours)
    for preset_id, _label, preset_hours in COOLDOWN_PRESETS:
        if preset_hours == hour_value:
            return preset_id
    return "custom"


def effective_cooldown_hours(data: dict[str, Any]) -> int:
    preset = data.get("cooldown_preset", "2")
    if preset == "custom":
        return max(1, int(data.get("cooldown_custom_hours", 1)))
    for preset_id, _label, preset_hours in COOLDOWN_PRESETS:
        if preset_id == preset and preset_hours is not None:
            return preset_hours
    return 2


def collect_available_formats(personalities: list[dict[str, Any]], schedule_slots: list[dict[str, Any]]) -> list[str]:
    formats: set[str] = set()
    for personality in personalities:
        for fmt in personality.get("music_formats", []):
            if fmt:
                formats.add(fmt)
    for slot in schedule_slots:
        fmt = slot.get("music_format", "")
        if fmt:
            formats.add(fmt)
    return sorted(formats)


def specialty_shows_from_schedule(schedule_slots: list[dict[str, Any]]) -> list[dict[str, str]]:
    blocked = []
    for slot in schedule_slots:
        if slot.get("requests_enabled", True):
            continue
        blocked.append(
            {
                "id": slot.get("id", ""),
                "show_name": slot.get("show_name", "Specialty Show"),
                "day": slot.get("day", ""),
                "start_time": slot.get("start_time", ""),
                "end_time": slot.get("end_time", ""),
            }
        )
    return blocked


def validate_requests_settings(data: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if data.get("requests_per_listener", 0) < 1:
        errors.append("Requests per listener must be at least 1.")

    if effective_cooldown_hours(data) < 1:
        errors.append("Cooldown must be at least 1 hour.")

    if data.get("max_active_queue", 0) < 1:
        errors.append("Maximum active requests in queue must be at least 1.")

    opening = data.get("opening_time", "00:00")
    closing = data.get("closing_time", "00:00")
    mode = data.get("request_mode", "by_schedule")
    if mode == "by_schedule" and opening == closing:
        warnings.append("Opening and closing times are the same.")

    email = data.get("song_not_found_email", "").strip()
    if email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        errors.append("Song not found email address is invalid.")

    if not data.get("limit_reached_message", "").strip():
        errors.append("Request limit reached message cannot be empty.")

    if is_requests_active(data) and not data.get("allowed_formats"):
        warnings.append("No music formats are enabled for requests.")

    if data.get("request_mode") == "by_schedule" and data.get("disable_during_specialty_shows", True):
        warnings.append("Requests will be disabled during schedule blocks marked Requests Off.")

    if data.get("request_mode") == "24_7":
        warnings.append("24/7 mode ignores daily opening and closing times.")

    return errors, warnings

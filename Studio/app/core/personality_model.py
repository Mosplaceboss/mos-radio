"""Personality record schema, normalization, and validation."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any
from uuid import uuid4

PERSONALITY_FIELDS = (
    "display_name",
    "show_name",
    "voicebox_voice_id",
    "radiodj_cart_id",
    "wav_output_path",
    "prompt_file",
    "air_staff_folder",
    "bio",
    "personality_description",
    "voice_description",
    "music_formats",
    "picture",
    "active",
)


def new_personality_id() -> str:
    return f"personality-{uuid4().hex[:8]}"


def normalize_personality(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize legacy records and ensure all expected fields exist."""
    record = deepcopy(raw)

    if not record.get("display_name"):
        record["display_name"] = record.pop("name", "")

    if not record.get("voicebox_voice_id"):
        record["voicebox_voice_id"] = record.pop("voice_id", "")

    if not record.get("personality_description"):
        record["personality_description"] = record.pop("description", "")

    record.setdefault("id", new_personality_id())
    record.setdefault("show_name", "")
    record.setdefault("radiodj_cart_id", "")
    record.setdefault("wav_output_path", "")
    record.setdefault("prompt_file", "")
    record.setdefault("air_staff_folder", "")
    record.setdefault("bio", "")
    record.setdefault("voice_description", "")
    record.setdefault("music_formats", [])
    record.setdefault("picture", "")
    record.setdefault("active", True)
    record.setdefault("created", datetime.now().isoformat(timespec="seconds"))
    record.setdefault("updated", record["created"])

    formats = record.get("music_formats", [])
    if isinstance(formats, str):
        record["music_formats"] = [item.strip() for item in formats.split(",") if item.strip()]
    elif not isinstance(formats, list):
        record["music_formats"] = []

    record.pop("name", None)
    record.pop("voice_id", None)
    record.pop("description", None)
    return record


def normalize_personalities_data(data: dict[str, Any]) -> dict[str, Any]:
    personalities = [normalize_personality(item) for item in data.get("personalities", [])]
    return {"personalities": personalities}


def display_label(personality: dict[str, Any]) -> str:
    return personality.get("display_name") or "Untitled Personality"


def validate_personality(personality: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not personality.get("display_name", "").strip():
        errors.append("Display Name is required.")
    if not personality.get("voicebox_voice_id", "").strip():
        errors.append("Voicebox Voice ID is required.")
    return errors


def formats_to_string(formats: list[str] | str) -> str:
    if isinstance(formats, list):
        return ", ".join(formats)
    return str(formats)


def formats_from_string(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]

"""Voice library record schema, normalization, and validation."""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import uuid4

VOICE_FIELDS = (
    "display_name",
    "voicebox_id",
    "personality_id",
    "voice_description",
    "portrait",
    "active",
    "default_greeting",
    "default_closing",
    "personality_prompt",
    "pronunciation_notes",
    "genre_specialties",
    "default_shift",
)


def new_voice_id() -> str:
    return f"vb-{uuid4().hex[:8]}"


def normalize_voice(raw: dict[str, Any]) -> dict[str, Any]:
    record = deepcopy(raw)

    if not record.get("display_name"):
        record["display_name"] = record.pop("name", "")

    if not record.get("voice_description"):
        record["voice_description"] = record.pop("description", "")

    if not record.get("genre_specialties") and record.get("tags"):
        record["genre_specialties"] = record.pop("tags", [])

    record.setdefault("id", new_voice_id())
    record.setdefault("voicebox_id", "")
    record.setdefault("personality_id", "")
    record.setdefault("portrait", "")
    record.setdefault("active", True)
    record.setdefault("default_greeting", "")
    record.setdefault("default_closing", "")
    record.setdefault("personality_prompt", "")
    record.setdefault("pronunciation_notes", "")
    record.setdefault("default_shift", "")

    specialties = record.get("genre_specialties", [])
    if isinstance(specialties, str):
        record["genre_specialties"] = [item.strip() for item in specialties.split(",") if item.strip()]
    elif not isinstance(specialties, list):
        record["genre_specialties"] = []

    record.pop("name", None)
    record.pop("description", None)
    record.pop("tags", None)
    record.pop("provider", None)
    return record


def normalize_voice_library_data(data: dict[str, Any]) -> dict[str, Any]:
    voices = [normalize_voice(item) for item in data.get("voices", [])]
    return {"voices": voices}


def display_label(voice: dict[str, Any]) -> str:
    return voice.get("display_name") or "Untitled Voice"


def specialties_to_string(specialties: list[str] | str) -> str:
    if isinstance(specialties, list):
        return ", ".join(specialties)
    return str(specialties)


def specialties_from_string(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def validate_voice(voice: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not voice.get("display_name", "").strip():
        errors.append("Display Name is required.")
    if not voice.get("voicebox_id", "").strip():
        errors.append("Voicebox ID is required.")
    return errors

"""LiveDJ configuration import, validation, and publish helpers."""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any

from app.core.integration_settings import livedj_live_paths, studio_config_path
from app.core.personality_model import normalize_personalities_data, validate_personality
from app.core.schedule_model import DAYS, normalize_schedule_data, time_to_index, validate_slot
from app.core.voice_model import normalize_voice_library_data

logger = logging.getLogger("moplace.studio.livedj")


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")


def import_livedj_from_live(integration: dict[str, Any]) -> tuple[bool, str, list[str]]:
    """Import live LiveDJ configuration into Studio development config."""
    live = livedj_live_paths(integration)
    imported: list[str] = []
    missing: list[str] = []

    mapping = {
        "personalities": studio_config_path("personalities"),
        "schedule": studio_config_path("schedule"),
        "voice_library": studio_config_path("voice_library"),
    }

    for key, destination in mapping.items():
        source = live[key]
        if not source.exists():
            missing.append(str(source))
            continue
        shutil.copy2(source, destination)
        imported.append(key)

    if not imported:
        return False, "No live LiveDJ configuration files were found to import.", missing
    return True, f"Imported {len(imported)} file(s) into Studio development config.", imported


def validate_livedj_bundle(config_manager) -> list[str]:
    """Validate personalities, schedule, and voice references for LiveDJ publish."""
    personalities_data = normalize_personalities_data(config_manager.load("personalities", {"personalities": []}))
    voices_data = normalize_voice_library_data(config_manager.load("voice_library", {"voices": []}))
    personality_ids = [item["id"] for item in personalities_data.get("personalities", [])]
    schedule_data = normalize_schedule_data(config_manager.load("schedule", {"slots": []}), personality_ids)

    personalities = personalities_data.get("personalities", [])
    voices = voices_data.get("voices", [])
    voice_ids = {voice.get("voicebox_id", "").strip() for voice in voices if voice.get("voicebox_id")}
    slots = schedule_data.get("slots", [])

    errors: list[str] = []

    for personality in personalities:
        label = personality.get("display_name") or personality.get("id")
        errors.extend(f"{label}: {item}" for item in validate_personality(personality))
        if personality.get("active", True):
            voice_id = personality.get("voicebox_voice_id", "").strip()
            if voice_id and voice_id not in voice_ids:
                errors.append(f"{label}: Voicebox ID '{voice_id}' not found in voice library.")
            if not personality.get("radiodj_cart_id", "").strip():
                errors.append(f"{label}: RadioDJ Cart ID is missing.")
            wav_path = personality.get("wav_output_path", "").strip()
            if wav_path and not Path(wav_path).exists():
                errors.append(f"{label}: WAV path does not exist ({wav_path}).")

    for slot in slots:
        show = slot.get("show_name") or slot.get("id")
        errors.extend(f"{show}: {item}" for item in validate_slot(slot))

    overlaps = _schedule_overlaps(slots)
    errors.extend(overlaps)
    return errors


def _schedule_overlaps(slots: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    by_day: dict[str, list[dict[str, Any]]] = {day: [] for day in DAYS}
    for slot in slots:
        day = slot.get("day", "").lower()
        if day in by_day:
            by_day[day].append(slot)

    for day, day_slots in by_day.items():
        normalized: list[tuple[int, int, str]] = []
        for slot in day_slots:
            try:
                start = time_to_index(slot.get("start_time", "00:00"))
                end = time_to_index(slot.get("end_time", "00:30"))
            except ValueError:
                continue
            normalized.append((start, end, slot.get("show_name", slot.get("id", "slot"))))
        normalized.sort()
        for index in range(1, len(normalized)):
            prev_start, prev_end, prev_name = normalized[index - 1]
            start, end, name = normalized[index]
            if start < prev_end:
                errors.append(f"Schedule conflict on {day.title()}: '{prev_name}' overlaps '{name}'.")
    return errors


def livedj_publish_files(integration: dict[str, Any]) -> dict[str, tuple[Path, Path]]:
    """Map publish keys to (studio source, live destination)."""
    live = livedj_live_paths(integration)
    return {
        "personalities": (studio_config_path("personalities"), live["personalities"]),
        "schedule": (studio_config_path("schedule"), live["schedule"]),
        "voice_library": (studio_config_path("voice_library"), live["voice_library"]),
    }

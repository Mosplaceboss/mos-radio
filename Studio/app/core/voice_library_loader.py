"""Background-safe Voice Library data loading and portrait warm-up."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.personality_model import normalize_personalities_data
from app.core.voice_model import normalize_voice_library_data
from app.core.voice_portrait_cache import resolve_voice_portrait_path, warm_thumbnail

logger = logging.getLogger("moplace.studio.voice_library_loader")

DEFAULT_FILE_TIMEOUT = 5.0
DEFAULT_PORTRAIT_TIMEOUT = 8.0


@dataclass
class VoiceLibraryLoadResult:
    personalities: list[dict[str, Any]] = field(default_factory=list)
    voices_data: dict[str, Any] = field(default_factory=lambda: {"voices": []})
    portrait_errors: dict[str, str] = field(default_factory=dict)
    load_errors: list[str] = field(default_factory=list)
    elapsed_ms: float = 0.0


def _read_json_file(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else default


def read_json_with_timeout(
    path: Path,
    default: dict[str, Any],
    *,
    timeout: float = DEFAULT_FILE_TIMEOUT,
) -> tuple[dict[str, Any], str | None]:
    if not path.exists():
        return default, None

    started = time.perf_counter()
    try:
        data = _read_json_file(path, default)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to read %s: %s", path, exc)
        return default, f"Could not read {path.name}: {exc}"
    except Exception as exc:
        logger.warning("Unexpected error reading %s: %s", path, exc)
        return default, f"Could not read {path.name}: {exc}"

    elapsed = time.perf_counter() - started
    if elapsed > timeout:
        return default, f"Timed out reading {path.name} after {timeout:.0f}s"
    return data, None


def warm_portraits(
    voices: list[dict[str, Any]],
    *,
    timeout: float = DEFAULT_PORTRAIT_TIMEOUT,
) -> dict[str, str]:
    errors: dict[str, str] = {}
    deadline = time.perf_counter() + timeout
    for voice in voices:
        if time.perf_counter() > deadline:
            portrait = voice.get("portrait", "")
            if portrait:
                errors[portrait] = "Portrait loading timed out"
            continue
        portrait = voice.get("portrait", "")
        if not portrait:
            continue
        path = resolve_voice_portrait_path(portrait)
        if path is None or not path.exists():
            continue
        ok, message = warm_thumbnail(path)
        if not ok and message:
            errors[portrait] = message
    return errors


def load_voice_library_page_data(
    personalities_path: Path,
    voice_library_path: Path,
    *,
    file_timeout: float = DEFAULT_FILE_TIMEOUT,
    portrait_timeout: float = DEFAULT_PORTRAIT_TIMEOUT,
) -> VoiceLibraryLoadResult:
    started = time.perf_counter()
    result = VoiceLibraryLoadResult()

    personalities_raw, personalities_error = read_json_with_timeout(
        personalities_path,
        {"personalities": []},
        timeout=file_timeout,
    )
    voices_raw, voices_error = read_json_with_timeout(
        voice_library_path,
        {"voices": []},
        timeout=file_timeout,
    )

    if personalities_error:
        result.load_errors.append(personalities_error)
    if voices_error:
        result.load_errors.append(voices_error)

    personalities_data = normalize_personalities_data(personalities_raw)
    result.personalities = personalities_data.get("personalities", [])
    result.voices_data = normalize_voice_library_data(voices_raw)
    result.portrait_errors = warm_portraits(
        result.voices_data.get("voices", []),
        timeout=portrait_timeout,
    )

    result.elapsed_ms = (time.perf_counter() - started) * 1000
    logger.info(
        "Voice Library load finished in %.0f ms (%d voices, %d errors)",
        result.elapsed_ms,
        len(result.voices_data.get("voices", [])),
        len(result.load_errors) + len(result.portrait_errors),
    )
    return result

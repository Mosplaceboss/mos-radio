"""Background-safe Personalities page data loading and picture warm-up."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.personality_model import normalize_personalities_data
from app.core.personality_picture_cache import resolve_personality_picture_path, warm_thumbnail
from app.core.voice_library_loader import read_json_with_timeout

logger = logging.getLogger("moplace.studio.personalities_loader")

DEFAULT_FILE_TIMEOUT = 5.0
DEFAULT_PICTURE_TIMEOUT = 8.0


@dataclass
class PersonalitiesLoadResult:
    personalities_data: dict[str, Any] = field(default_factory=lambda: {"personalities": []})
    picture_errors: dict[str, str] = field(default_factory=dict)
    load_errors: list[str] = field(default_factory=list)
    elapsed_ms: float = 0.0


def warm_pictures(
    personalities: list[dict[str, Any]],
    *,
    timeout: float = DEFAULT_PICTURE_TIMEOUT,
) -> dict[str, str]:
    errors: dict[str, str] = {}
    deadline = time.perf_counter() + timeout
    for personality in personalities:
        if time.perf_counter() > deadline:
            picture = personality.get("picture", "")
            if picture:
                errors[picture] = "Picture loading timed out"
            continue
        picture = personality.get("picture", "")
        if not picture:
            continue
        path = resolve_personality_picture_path(picture)
        if path is None or not path.exists():
            continue
        ok, message = warm_thumbnail(path)
        if not ok and message:
            errors[picture] = message
    return errors


def load_personalities_page_data(
    personalities_path: Path,
    *,
    file_timeout: float = DEFAULT_FILE_TIMEOUT,
    picture_timeout: float = DEFAULT_PICTURE_TIMEOUT,
) -> PersonalitiesLoadResult:
    started = time.perf_counter()
    result = PersonalitiesLoadResult()

    personalities_raw, personalities_error = read_json_with_timeout(
        personalities_path,
        {"personalities": []},
        timeout=file_timeout,
    )
    if personalities_error:
        result.load_errors.append(personalities_error)

    result.personalities_data = normalize_personalities_data(personalities_raw)
    result.picture_errors = warm_pictures(
        result.personalities_data.get("personalities", []),
        timeout=picture_timeout,
    )

    result.elapsed_ms = (time.perf_counter() - started) * 1000
    logger.info(
        "Personalities load finished in %.0f ms (%d personalities, %d errors)",
        result.elapsed_ms,
        len(result.personalities_data.get("personalities", [])),
        len(result.load_errors) + len(result.picture_errors),
    )
    return result

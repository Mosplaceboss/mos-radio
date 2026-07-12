"""Background-safe Schedule page data loading."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.config_io import read_json
from app.core.personality_model import normalize_personalities_data
from app.core.schedule_model import normalize_schedule_data
from app.core.voice_library_loader import read_json_with_timeout

DEFAULT_FILE_TIMEOUT = 5.0


@dataclass
class ScheduleLoadResult:
    personalities: list[dict[str, Any]] = field(default_factory=list)
    schedule_data: dict[str, Any] = field(default_factory=lambda: {"timezone": "America/New_York", "slots": []})
    load_errors: list[str] = field(default_factory=list)
    elapsed_ms: float = 0.0


def load_schedule_page_data(
    personalities_path: Path,
    schedule_path: Path,
    *,
    file_timeout: float = DEFAULT_FILE_TIMEOUT,
) -> ScheduleLoadResult:
    started = time.perf_counter()
    result = ScheduleLoadResult()

    personalities_raw, personalities_error = read_json_with_timeout(
        personalities_path,
        {"personalities": []},
        timeout=file_timeout,
    )
    schedule_raw, schedule_error = read_json_with_timeout(
        schedule_path,
        {"timezone": "America/New_York", "slots": []},
        timeout=file_timeout,
    )

    if personalities_error:
        result.load_errors.append(personalities_error)
    if schedule_error:
        result.load_errors.append(schedule_error)

    personalities_data = normalize_personalities_data(personalities_raw)
    result.personalities = personalities_data.get("personalities", [])
    personality_ids = [item["id"] for item in result.personalities]
    result.schedule_data = normalize_schedule_data(schedule_raw, personality_ids)

    result.elapsed_ms = (time.perf_counter() - started) * 1000
    return result

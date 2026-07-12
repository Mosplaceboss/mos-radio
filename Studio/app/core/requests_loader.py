"""Background-safe Requests page data loading."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.personality_model import normalize_personalities_data
from app.core.requests_model import normalize_requests_data
from app.core.schedule_model import normalize_schedule_data
from app.core.voice_library_loader import read_json_with_timeout

DEFAULT_FILE_TIMEOUT = 5.0


@dataclass
class RequestsLoadResult:
    requests_data: dict[str, Any] = field(default_factory=dict)
    personalities: list[dict[str, Any]] = field(default_factory=list)
    schedule_slots: list[dict[str, Any]] = field(default_factory=list)
    load_errors: list[str] = field(default_factory=list)
    elapsed_ms: float = 0.0


def load_requests_page_data(
    requests_path: Path,
    personalities_path: Path,
    schedule_path: Path,
    *,
    file_timeout: float = DEFAULT_FILE_TIMEOUT,
) -> RequestsLoadResult:
    started = time.perf_counter()
    result = RequestsLoadResult()

    requests_raw, requests_error = read_json_with_timeout(
        requests_path,
        {},
        timeout=file_timeout,
    )
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

    for error in (requests_error, personalities_error, schedule_error):
        if error:
            result.load_errors.append(error)

    personalities_data = normalize_personalities_data(personalities_raw)
    result.personalities = personalities_data.get("personalities", [])
    personality_ids = [item["id"] for item in result.personalities]
    schedule_data = normalize_schedule_data(schedule_raw, personality_ids)
    result.schedule_slots = schedule_data.get("slots", [])
    result.requests_data = normalize_requests_data(requests_raw)

    result.elapsed_ms = (time.perf_counter() - started) * 1000
    return result

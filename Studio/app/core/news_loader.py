"""Background-safe News page data loading."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.news_model import normalize_news_data
from app.core.voice_library_loader import read_json_with_timeout

DEFAULT_FILE_TIMEOUT = 5.0


@dataclass
class NewsLoadResult:
    news_data: dict[str, Any] = field(default_factory=dict)
    load_errors: list[str] = field(default_factory=list)
    elapsed_ms: float = 0.0


def load_news_page_data(
    news_path: Path,
    *,
    file_timeout: float = DEFAULT_FILE_TIMEOUT,
) -> NewsLoadResult:
    started = time.perf_counter()
    result = NewsLoadResult()

    news_raw, news_error = read_json_with_timeout(news_path, {}, timeout=file_timeout)
    if news_error:
        result.load_errors.append(news_error)

    result.news_data = normalize_news_data(news_raw)
    result.elapsed_ms = (time.perf_counter() - started) * 1000
    return result

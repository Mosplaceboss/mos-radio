"""News automation configuration schema and validation."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any
from uuid import uuid4


def new_feed_id() -> str:
    return f"feed-{uuid4().hex[:8]}"


def new_task_id() -> str:
    return f"task-{uuid4().hex[:8]}"


def normalize_feed(raw: dict[str, Any]) -> dict[str, Any]:
    record = deepcopy(raw)
    record.setdefault("id", new_feed_id())
    record.setdefault("name", "")
    record.setdefault("url", "")
    record.setdefault("enabled", True)
    return record


def normalize_task(raw: dict[str, Any]) -> dict[str, Any]:
    record = deepcopy(raw)
    record.setdefault("id", new_task_id())
    record.setdefault("name", "")
    record.setdefault("schedule", "")
    record.setdefault("enabled", True)
    return record


def normalize_news_data(data: dict[str, Any]) -> dict[str, Any]:
    feeds = [normalize_feed(item) for item in data.get("rss_feeds", [])]
    tasks = [normalize_task(item) for item in data.get("tasks", [])]
    return {
        "enabled": data.get("enabled", True),
        "rss_feeds": feeds,
        "tasks": tasks,
        "last_successful_run": data.get("last_successful_run", ""),
        "updated": data.get("updated", datetime.now().isoformat(timespec="seconds")),
    }


def validate_news_data(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    feeds = data.get("rss_feeds", [])
    if not feeds:
        errors.append("At least one RSS feed is required.")
    for index, feed in enumerate(feeds, start=1):
        if not feed.get("name", "").strip():
            errors.append(f"Feed {index}: name is required.")
        url = feed.get("url", "").strip()
        if not url:
            errors.append(f"Feed {index}: URL is required.")
        elif not url.lower().startswith(("http://", "https://")):
            errors.append(f"Feed {index}: URL must start with http:// or https://")
    return errors

"""Website & Audience Manager storage under platform StationData."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.config_io import read_json, write_json
from app.core.station_data import station_data_dir


def website_data_dir(config_manager=None) -> Path:
    path = station_data_dir(config_manager) / "WebsiteAudience"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _path(name: str, config_manager=None) -> Path:
    return website_data_dir(config_manager) / name


def content_path(config_manager=None) -> Path:
    return _path("content.json", config_manager)


def audience_path(config_manager=None) -> Path:
    return _path("audience.json", config_manager)


def schedule_path(config_manager=None) -> Path:
    return _path("schedule.json", config_manager)


def website_state_path(config_manager=None) -> Path:
    return _path("website_state.json", config_manager)


def load_json_file(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if path.exists():
        try:
            return read_json(path, default)
        except OSError:
            pass
    return default


def save_json_file(path: Path, data: dict[str, Any]) -> None:
    write_json(path, data)


def load_website_bundle(config_manager=None) -> dict[str, Any]:
    return {
        "content": load_json_file(content_path(config_manager), {"pages": [], "posts": []}),
        "audience": load_json_file(
            audience_path(config_manager),
            {"segments": [], "newsletter_enabled": False, "social_links": {}},
        ),
        "schedule": load_json_file(
            schedule_path(config_manager),
            {"publish_slots": [], "timezone": "America/New_York"},
        ),
        "state": load_json_file(website_state_path(config_manager), {"last_validated": "", "version": 1}),
    }


def save_website_bundle(bundle: dict[str, Any], config_manager=None) -> None:
    save_json_file(content_path(config_manager), bundle["content"])
    save_json_file(audience_path(config_manager), bundle["audience"])
    save_json_file(schedule_path(config_manager), bundle["schedule"])
    save_json_file(website_state_path(config_manager), bundle["state"])

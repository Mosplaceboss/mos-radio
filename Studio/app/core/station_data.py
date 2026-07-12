"""Station data paths and persistence under the platform StationData folder."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.config_io import read_json, write_json
from app.core.platform_manager import platform_documentation_dir, platform_path


def station_data_dir(config_manager=None) -> Path:
    path = platform_path("station_data", config_manager)
    path.mkdir(parents=True, exist_ok=True)
    return path


def station_info_path(config_manager=None) -> Path:
    return station_data_dir(config_manager) / "station_info.json"


def station_logos_dir(config_manager=None) -> Path:
    path = station_data_dir(config_manager) / "logos"
    path.mkdir(parents=True, exist_ok=True)
    return path


def inventory_reports_dir(config_manager=None) -> Path:
    docs = platform_documentation_dir(config_manager)
    reports = docs / "InventoryReports"
    if reports.exists():
        return reports
    return platform_path("reports", config_manager)


def ensure_station_data(config_manager=None) -> Path:
    station_data_dir(config_manager)
    station_logos_dir(config_manager)
    info_path = station_info_path(config_manager)
    if not info_path.exists():
        write_json(info_path, default_station_info())
    return info_path


def default_station_info() -> dict[str, Any]:
    return {
        "station_name": "Mo's Place Radio",
        "slogan": "",
        "website": "",
        "facebook": "",
        "instagram": "",
        "youtube": "",
        "email": "",
        "phone": "",
        "address": "",
        "timezone": "America/New_York",
        "logo_path": "",
        "default_station_voice": "",
        "default_news_voice": "",
        "default_weather_voice": "",
        "default_request_voice": "",
        "default_ai_personality": "",
    }


def normalize_station_info(data: dict[str, Any] | None, settings: dict[str, Any] | None = None) -> dict[str, Any]:
    base = default_station_info()
    if settings:
        base["station_name"] = settings.get("station_name", base["station_name"])
        base["timezone"] = settings.get("timezone", base["timezone"])
    if not data:
        return base

    for key in base:
        value = data.get(key, base[key])
        base[key] = value.strip() if isinstance(value, str) else value
    return base


def load_station_info(config_manager=None, settings: dict[str, Any] | None = None) -> dict[str, Any]:
    path = station_info_path(config_manager)
    if path.exists():
        try:
            data = read_json(path, default_station_info())
            return normalize_station_info(data, settings)
        except OSError:
            pass
    return normalize_station_info(None, settings)


def save_station_info(data: dict[str, Any], config_manager=None, settings: dict[str, Any] | None = None) -> dict[str, Any]:
    normalized = normalize_station_info(data, settings)
    write_json(station_info_path(config_manager), normalized)
    return normalized

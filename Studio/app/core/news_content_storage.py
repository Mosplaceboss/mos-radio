"""News & Content Manager storage under platform StationData and Reports."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.config_io import read_json, write_json
from app.core.platform_manager import platform_path
from app.core.station_data import station_data_dir


def news_data_dir(config_manager=None) -> Path:
    path = station_data_dir(config_manager) / "News"
    path.mkdir(parents=True, exist_ok=True)
    return path


def news_reports_dir(config_manager=None) -> Path:
    reports_root = platform_path("reports", config_manager)
    path = reports_root / "News"
    path.mkdir(parents=True, exist_ok=True)
    return path


def news_dev_output_dir(config_manager=None) -> Path:
    path = news_data_dir(config_manager) / "dev_output"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _data_path(name: str, config_manager=None) -> Path:
    return news_data_dir(config_manager) / name


def personalities_path(config_manager=None) -> Path:
    return _data_path("personalities.json", config_manager)


def categories_path(config_manager=None) -> Path:
    return _data_path("categories.json", config_manager)


def rss_sources_path(config_manager=None) -> Path:
    return _data_path("rss_sources.json", config_manager)


def schedule_path(config_manager=None) -> Path:
    return _data_path("schedule.json", config_manager)


def script_rules_path(config_manager=None) -> Path:
    return _data_path("script_rules.json", config_manager)


def voice_settings_path(config_manager=None) -> Path:
    return _data_path("voice_settings.json", config_manager)


def overview_state_path(config_manager=None) -> Path:
    return _data_path("overview_state.json", config_manager)


def news_content_state_path(config_manager=None) -> Path:
    return _data_path("news_content_state.json", config_manager)


def run_history_path(config_manager=None) -> Path:
    return news_reports_dir(config_manager) / "run_history.json"


def feed_reliability_path(config_manager=None) -> Path:
    return news_reports_dir(config_manager) / "feed_reliability.json"


def load_json_file(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if path.exists():
        try:
            return read_json(path, default)
        except OSError:
            pass
    return default


def save_json_file(path: Path, data: dict[str, Any]) -> None:
    write_json(path, data)


def load_news_content_bundle(config_manager=None) -> dict[str, Any]:
    return {
        "personalities": load_json_file(personalities_path(config_manager), {"personalities": []}),
        "categories": load_json_file(categories_path(config_manager), {"categories": []}),
        "rss_sources": load_json_file(rss_sources_path(config_manager), {"sources": []}),
        "schedule": load_json_file(
            schedule_path(config_manager),
            {"slots": [], "overrides": [], "timezone": "America/New_York"},
        ),
        "script_rules": load_json_file(script_rules_path(config_manager), {}),
        "voice_settings": load_json_file(voice_settings_path(config_manager), {}),
        "overview": load_json_file(
            overview_state_path(config_manager),
            {
                "morning_status": "Not run",
                "midday_status": "Not run",
                "afternoon_status": "Not run",
                "last_successful_run": "",
                "next_scheduled_run": "",
                "current_output_files": [],
                "errors_warnings": [],
            },
        ),
        "state": load_json_file(news_content_state_path(config_manager), {"last_validated": "", "version": 1}),
        "run_history": load_json_file(run_history_path(config_manager), {"runs": []}),
        "feed_reliability": load_json_file(feed_reliability_path(config_manager), {"feeds": {}}),
    }


def save_news_content_bundle(bundle: dict[str, Any], config_manager=None) -> None:
    save_json_file(personalities_path(config_manager), bundle["personalities"])
    save_json_file(categories_path(config_manager), bundle["categories"])
    save_json_file(rss_sources_path(config_manager), bundle["rss_sources"])
    save_json_file(schedule_path(config_manager), bundle["schedule"])
    save_json_file(script_rules_path(config_manager), bundle["script_rules"])
    save_json_file(voice_settings_path(config_manager), bundle["voice_settings"])
    save_json_file(overview_state_path(config_manager), bundle["overview"])
    save_json_file(news_content_state_path(config_manager), bundle["state"])
    save_json_file(run_history_path(config_manager), bundle["run_history"])
    save_json_file(feed_reliability_path(config_manager), bundle["feed_reliability"])

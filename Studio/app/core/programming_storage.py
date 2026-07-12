"""Programming Manager storage under platform StationData."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.config_io import read_json, write_json
from app.core.station_data import station_data_dir


def programming_dir(config_manager=None) -> Path:
    path = station_data_dir(config_manager) / "Programming"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _path(name: str, config_manager=None) -> Path:
    return programming_dir(config_manager) / name


def shows_path(config_manager=None) -> Path:
    return _path("shows.json", config_manager)


def formats_path(config_manager=None) -> Path:
    return _path("formats.json", config_manager)


def clocks_path(config_manager=None) -> Path:
    return _path("clocks.json", config_manager)


def events_path(config_manager=None) -> Path:
    return _path("events.json", config_manager)


def assignments_path(config_manager=None) -> Path:
    return _path("assignments.json", config_manager)


def overrides_path(config_manager=None) -> Path:
    return _path("overrides.json", config_manager)


def programming_state_path(config_manager=None) -> Path:
    return _path("programming_state.json", config_manager)


def load_json_file(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if path.exists():
        try:
            return read_json(path, default)
        except OSError:
            pass
    return default


def save_json_file(path: Path, data: dict[str, Any]) -> None:
    write_json(path, data)


def load_programming_bundle(config_manager=None) -> dict[str, Any]:
    return {
        "shows": load_json_file(shows_path(config_manager), {"shows": []}),
        "formats": load_json_file(formats_path(config_manager), {"formats": []}),
        "clocks": load_json_file(clocks_path(config_manager), {"clocks": []}),
        "events": load_json_file(events_path(config_manager), {"timezone": "America/New_York", "events": []}),
        "assignments": load_json_file(assignments_path(config_manager), {"assignments": []}),
        "overrides": load_json_file(overrides_path(config_manager), {"overrides": []}),
        "state": load_json_file(programming_state_path(config_manager), {"last_validated": "", "version": 1}),
    }


def save_programming_bundle(bundle: dict[str, Any], config_manager=None) -> None:
    save_json_file(shows_path(config_manager), bundle["shows"])
    save_json_file(formats_path(config_manager), bundle["formats"])
    save_json_file(clocks_path(config_manager), bundle["clocks"])
    save_json_file(events_path(config_manager), bundle["events"])
    save_json_file(assignments_path(config_manager), bundle["assignments"])
    save_json_file(overrides_path(config_manager), bundle["overrides"])
    save_json_file(programming_state_path(config_manager), bundle["state"])

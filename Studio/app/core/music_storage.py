"""Music Manager storage under platform StationData."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.config_io import read_json, write_json
from app.core.station_data import station_data_dir


def music_dir(config_manager=None) -> Path:
    path = station_data_dir(config_manager) / "Music"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _path(name: str, config_manager=None) -> Path:
    return music_dir(config_manager) / name


def settings_path(config_manager=None) -> Path:
    return _path("settings.json", config_manager)


def catalog_path(config_manager=None) -> Path:
    return _path("catalog.json", config_manager)


def formats_path(config_manager=None) -> Path:
    return _path("formats.json", config_manager)


def playlists_path(config_manager=None) -> Path:
    return _path("playlists.json", config_manager)


def categories_path(config_manager=None) -> Path:
    return _path("categories.json", config_manager)


def resources_path(config_manager=None) -> Path:
    return _path("resources.json", config_manager)


def music_state_path(config_manager=None) -> Path:
    return _path("music_state.json", config_manager)


def load_json_file(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if path.exists():
        try:
            return read_json(path, default)
        except OSError:
            pass
    return default


def save_json_file(path: Path, data: dict[str, Any]) -> None:
    write_json(path, data)


def load_music_bundle(config_manager=None) -> dict[str, Any]:
    return {
        "settings": load_json_file(settings_path(config_manager), {"music_root": r"W:\Music", "last_scan_at": ""}),
        "catalog": load_json_file(catalog_path(config_manager), {"songs": [], "last_scan_at": ""}),
        "formats": load_json_file(formats_path(config_manager), {"formats": []}),
        "playlists": load_json_file(playlists_path(config_manager), {"playlists": []}),
        "categories": load_json_file(categories_path(config_manager), {"categories": []}),
        "resources": load_json_file(resources_path(config_manager), {"resources": {}}),
        "state": load_json_file(music_state_path(config_manager), {"last_validated": "", "version": 1}),
    }


def save_music_bundle(bundle: dict[str, Any], config_manager=None) -> None:
    save_json_file(settings_path(config_manager), bundle["settings"])
    save_json_file(catalog_path(config_manager), bundle["catalog"])
    save_json_file(formats_path(config_manager), bundle["formats"])
    save_json_file(playlists_path(config_manager), bundle["playlists"])
    save_json_file(categories_path(config_manager), bundle["categories"])
    save_json_file(resources_path(config_manager), bundle["resources"])
    save_json_file(music_state_path(config_manager), bundle["state"])

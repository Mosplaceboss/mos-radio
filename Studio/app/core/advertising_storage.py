"""Advertising Manager storage under platform StationData."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.config_io import read_json, write_json
from app.core.station_data import station_data_dir


def advertising_data_dir(config_manager=None) -> Path:
    path = station_data_dir(config_manager) / "Advertising"
    path.mkdir(parents=True, exist_ok=True)
    return path


def sponsors_path(config_manager=None) -> Path:
    return advertising_data_dir(config_manager) / "sponsors.json"


def campaigns_path(config_manager=None) -> Path:
    return advertising_data_dir(config_manager) / "campaigns.json"


def advertising_state_path(config_manager=None) -> Path:
    return advertising_data_dir(config_manager) / "advertising_state.json"


def load_json_file(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if path.exists():
        try:
            return read_json(path, default)
        except OSError:
            pass
    return default


def save_json_file(path: Path, data: dict[str, Any]) -> None:
    write_json(path, data)


def load_advertising_bundle(config_manager=None) -> dict[str, Any]:
    return {
        "sponsors": load_json_file(sponsors_path(config_manager), {"sponsors": []}),
        "campaigns": load_json_file(campaigns_path(config_manager), {"campaigns": []}),
        "state": load_json_file(advertising_state_path(config_manager), {"last_validated": "", "version": 1}),
    }


def save_advertising_bundle(bundle: dict[str, Any], config_manager=None) -> None:
    save_json_file(sponsors_path(config_manager), bundle["sponsors"])
    save_json_file(campaigns_path(config_manager), bundle["campaigns"])
    save_json_file(advertising_state_path(config_manager), bundle["state"])

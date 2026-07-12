"""Operations Manager storage under platform StationData."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.config_io import read_json, write_json
from app.core.station_data import station_data_dir


def operations_data_dir(config_manager=None) -> Path:
    path = station_data_dir(config_manager) / "Operations"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _path(name: str, config_manager=None) -> Path:
    return operations_data_dir(config_manager) / name


def deployment_path(config_manager=None) -> Path:
    return _path("deployment.json", config_manager)


def migration_path(config_manager=None) -> Path:
    return _path("migration.json", config_manager)


def operations_log_path(config_manager=None) -> Path:
    return _path("operations_log.json", config_manager)


def operations_state_path(config_manager=None) -> Path:
    return _path("operations_state.json", config_manager)


def load_json_file(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if path.exists():
        try:
            return read_json(path, default)
        except OSError:
            pass
    return default


def save_json_file(path: Path, data: dict[str, Any]) -> None:
    write_json(path, data)


def load_operations_bundle(config_manager=None) -> dict[str, Any]:
    return {
        "deployment": load_json_file(
            deployment_path(config_manager),
            {
                "development_version": "2.0.0-dev",
                "production_version": "1.0.0",
                "build_date": "",
                "release_notes": "",
                "last_deployed": "",
                "last_rollback": "",
            },
        ),
        "migration": load_json_file(migration_path(config_manager), {"modules": []}),
        "log": load_json_file(
            operations_log_path(config_manager),
            {
                "operations": [],
                "backups": [],
                "deployments": [],
                "migrations": [],
                "errors": [],
                "warnings": [],
            },
        ),
        "state": load_json_file(operations_state_path(config_manager), {"last_validated": "", "version": 1}),
    }


def save_operations_bundle(bundle: dict[str, Any], config_manager=None) -> None:
    save_json_file(deployment_path(config_manager), bundle["deployment"])
    save_json_file(migration_path(config_manager), bundle["migration"])
    save_json_file(operations_log_path(config_manager), bundle["log"])
    save_json_file(operations_state_path(config_manager), bundle["state"])

"""Studio update packages — backup, apply, and rollback."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from app.core.paths import config_dir, studio_root
from app.core.platform_manager import platform_backups_dir
from app.core.studio_info import APP_VERSION, APP_VERSION_LABEL


@dataclass
class UpdateRecord:
    version: str
    label: str
    backup_path: str
    applied_at: str
    package_path: str


def updates_dir() -> Path:
    path = platform_backups_dir() / "Updates"
    path.mkdir(parents=True, exist_ok=True)
    return path


def update_history_path() -> Path:
    return updates_dir() / "update_history.json"


def load_update_history() -> list[dict[str, Any]]:
    path = update_history_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def save_update_history(records: list[dict[str, Any]]) -> None:
    update_history_path().write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")


def installed_version_info() -> dict[str, str]:
    return {
        "version": APP_VERSION,
        "label": APP_VERSION_LABEL,
        "studio_root": str(studio_root()),
    }


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def create_pre_update_backup() -> Path:
    backup_root = updates_dir() / f"pre-update-{_timestamp()}"
    backup_root.mkdir(parents=True, exist_ok=True)
    root = studio_root()
    for name in ("config", "assets", "data", "logs"):
        source = root / name
        if source.exists():
            shutil.copytree(source, backup_root / name, dirs_exist_ok=True)
    manifest = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "version": APP_VERSION,
        "label": APP_VERSION_LABEL,
        "studio_root": str(root),
    }
    (backup_root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return backup_root


def _extract_package(package_path: Path, destination: Path) -> None:
    with ZipFile(package_path, "r") as archive:
        archive.extractall(destination)


def apply_update_package(package_path: Path) -> tuple[bool, str]:
    if not package_path.exists():
        return False, f"Update package not found: {package_path}"
    backup = create_pre_update_backup()
    temp_root = updates_dir() / f"extract-{_timestamp()}"
    temp_root.mkdir(parents=True, exist_ok=True)
    try:
        _extract_package(package_path, temp_root)
        candidates = list(temp_root.rglob("MoPlaceStudio.exe")) + list(temp_root.rglob("Studio.exe"))
        if not candidates:
            return False, "Update package does not contain Studio.exe or MoPlaceStudio.exe."
        package_root = candidates[0].parent
        target = studio_root()
        preserve = {"config", "assets", "data", "logs", "backups"}
        for item in package_root.iterdir():
            if item.name in preserve and (target / item.name).exists():
                continue
            destination = target / item.name
            if item.is_dir():
                shutil.copytree(item, destination, dirs_exist_ok=True)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, destination)

        manifest_path = package_root / "update_manifest.json"
        version = APP_VERSION
        label = APP_VERSION_LABEL
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            version = manifest.get("version", version)
            label = manifest.get("label", label)

        records = load_update_history()
        records.insert(
            0,
            {
                "version": version,
                "label": label,
                "backup_path": str(backup),
                "applied_at": datetime.now().strftime("%Y-%m-%d %I:%M %p"),
                "package_path": str(package_path),
            },
        )
        save_update_history(records[:10])
        return True, f"Update applied successfully. Backup saved to {backup.name}."
    except (OSError, json.JSONDecodeError, shutil.Error) as exc:
        return False, f"Update failed: {exc}"
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def rollback_last_update() -> tuple[bool, str]:
    records = load_update_history()
    if not records:
        return False, "No update history found to roll back."
    latest = records[0]
    backup_path = Path(latest.get("backup_path", ""))
    if not backup_path.exists():
        return False, "Previous backup folder was not found."
    target = studio_root()
    for name in ("config", "assets", "data", "logs"):
        source = backup_path / name
        if not source.exists():
            continue
        destination = target / name
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(source, destination)
    return True, f"Rolled back to backup from {latest.get('applied_at', 'previous update')}."

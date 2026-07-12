"""Timestamped configuration backup and restore."""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.paths import backups_dir

logger = logging.getLogger("moplace.studio.backup")

LAST_BACKUP_FILE = "last_backup.json"


def _manifest_path() -> Path:
    return backups_dir() / LAST_BACKUP_FILE


def _load_manifest() -> dict[str, Any]:
    path = _manifest_path()
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}


def _save_manifest(data: dict[str, Any]) -> None:
    path = _manifest_path()
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")


def _timestamp_label() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def create_backup(label: str, source_files: dict[str, Path]) -> Path:
    """Copy source files into a timestamped backup folder."""
    backup_root = backups_dir() / label / _timestamp_label()
    backup_root.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    for name, source in source_files.items():
        if not source.exists():
            continue
        destination = backup_root / f"{name}{source.suffix}"
        shutil.copy2(source, destination)
        copied.append(str(destination))

    manifest = _load_manifest()
    manifest[label] = {
        "path": str(backup_root),
        "created": datetime.now().isoformat(timespec="seconds"),
        "files": copied,
    }
    _save_manifest(manifest)
    logger.info("Created backup '%s' at %s", label, backup_root)
    return backup_root


def last_backup_path(label: str) -> Path | None:
    manifest = _load_manifest()
    entry = manifest.get(label)
    if not entry:
        return None
    path = Path(entry.get("path", ""))
    return path if path.exists() else None


def restore_last_backup(label: str, destinations: dict[str, Path]) -> tuple[bool, str]:
    """Restore files from the last backup for a label into destination paths."""
    backup_path = last_backup_path(label)
    if not backup_path:
        return False, f"No backup found for '{label}'."

    restored = 0
    for name, destination in destinations.items():
        source = backup_path / f"{name}{destination.suffix}"
        if not source.exists():
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        restored += 1

    if restored == 0:
        return False, f"Backup folder exists but no matching files were restored for '{label}'."
    return True, f"Restored {restored} file(s) from {backup_path.name}."


def list_backups(label: str) -> list[Path]:
    folder = backups_dir() / label
    if not folder.exists():
        return []
    return sorted((path for path in folder.iterdir() if path.is_dir()), reverse=True)

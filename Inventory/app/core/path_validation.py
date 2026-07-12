"""Validate local and UNC paths for inventory scans."""

from __future__ import annotations

import os
from pathlib import Path

from app.core.paths_util import is_admin_share, sanitize_folder_path
from app.core.safety import validate_output_write
from app.core.settings_store import (
    DEFAULT_OUTPUT_FOLDER,
    OFFICE_PLATFORM_PHYSICAL,
    RADIO_OUTPUT_FOLDER,
    RADIO_PLATFORM_MAPPED,
    is_office_pc,
    is_radio_pc,
    sanitize_folder_list,
)


def _normalize_drive_path(path: str) -> str:
    return path.rstrip("\\/").lower()


def validate_scan_path(path: str, *, label: str) -> tuple[bool, str, bool]:
    """Return ok, message, and whether the message is a warning."""
    raw = sanitize_folder_path(path)
    if not raw:
        if path.strip() and is_admin_share(path):
            return False, "Administrative shares (C$, D$, etc.) are not allowed.", False
        return False, f"{label} is required. Browse to or enter a folder path.", False

    normalized = _normalize_drive_path(raw)

    if label == "Platform folder" and is_office_pc():
        if normalized in {_normalize_drive_path(RADIO_PLATFORM_MAPPED), "v:"}:
            return (
                False,
                "On the Office PC, use D:\\MosPlaceRadioPlatform for the platform folder, not V:\\.",
                False,
            )

    if label == "Platform folder" and is_radio_pc():
        if normalized == _normalize_drive_path(OFFICE_PLATFORM_PHYSICAL):
            return (
                False,
                "On the Radio PC, use the mapped platform drive V:\\ instead of D:\\MosPlaceRadioPlatform.",
                False,
            )

    try:
        candidate = Path(raw)
        if not candidate.exists():
            if raw.startswith("\\\\"):
                return True, "Share not reachable now. Scan will record the error and continue.", True
            return True, "Folder not found now. Scan will record the error and continue.", True

        if not candidate.is_dir():
            return False, f"{label} must be a folder, not a file: {raw}", False

        if not os.access(candidate, os.R_OK):
            return True, "Folder is not readable now. Scan will record the error and continue.", True
    except (OSError, PermissionError) as exc:
        return True, f"Access check failed ({exc}). Scan will record the error and continue.", True

    return True, "Ready to scan.", False


def validate_folder_list(
    folders: list[str] | str | None,
    *,
    label: str,
    required: bool = True,
) -> tuple[bool, str, bool]:
    cleaned = sanitize_folder_list(folders)
    if not cleaned:
        if required:
            return False, f"Add at least one {label}.", False
        return True, "No folders selected.", False

    warnings: list[str] = []
    for folder in cleaned:
        ok, message, warning = validate_scan_path(folder, label=label)
        if not ok:
            return False, message, False
        if warning:
            warnings.append(folder)

    if warnings:
        return True, f"{len(cleaned)} folder(s) selected. Some are not reachable and will be recorded in the report.", True
    return True, f"{len(cleaned)} folder(s) ready to scan.", False


def validate_output_path(path: str) -> tuple[bool, str, bool]:
    raw = path.strip() or DEFAULT_OUTPUT_FOLDER
    try:
        target = validate_output_write(Path(raw))
    except OSError as exc:
        return False, f"Output folder cannot be created or used: {raw} ({exc})", False

    if not os.access(target, os.W_OK):
        return False, f"Output folder is not writable: {target}", False

    return True, "Reports will be saved here.", False


def ensure_default_output_folder() -> str:
    for candidate in (DEFAULT_OUTPUT_FOLDER, RADIO_OUTPUT_FOLDER):
        ok, _message, _warning = validate_output_path(candidate)
        if ok:
            return candidate
    fallback = Path.cwd() / "InventoryReports"
    validate_output_write(fallback)
    return str(fallback)


def all_scan_paths_valid(settings: dict) -> tuple[bool, list[str]]:
    checks = [
        validate_folder_list(settings.get("office_pc_folders"), label="Office PC folder", required=True),
        validate_folder_list(settings.get("radio_pc_folders"), label="Radio PC folder", required=False),
        validate_output_path(settings.get("output_folder", "")),
    ]
    messages = [message for ok, message, _warning in checks if not ok]
    return not messages, messages

"""Validate local and UNC paths for inventory scans."""

from __future__ import annotations

import os
from pathlib import Path

from app.core.paths_util import is_computer_name, resolve_computer_root
from app.core.safety import validate_output_write
from app.core.settings_store import (
    DEFAULT_OUTPUT_FOLDER,
    OFFICE_PLATFORM_PHYSICAL,
    RADIO_OUTPUT_FOLDER,
    RADIO_PLATFORM_MAPPED,
    is_office_pc,
    is_radio_pc,
)


def _normalize_drive_path(path: str) -> str:
    return path.rstrip("\\/").lower()


def validate_scan_path(path: str, *, label: str) -> tuple[bool, str]:
    raw = path.strip()
    if not raw:
        return False, f"{label} is required."

    label_lower = label.lower()
    if is_computer_name(raw):
        if "office" in label_lower:
            return True, f"Will scan {raw} locally on this Office PC."
        if "radio" in label_lower:
            _name, roots, errors = resolve_computer_root(raw)
            if roots:
                return True, f"Remote scan ready ({len(roots)} reachable paths on {raw})."
            return True, f"Will attempt remote scan of {raw}. {errors[0] if errors else ''}"
        return True, f"Will scan {raw}."

    normalized = _normalize_drive_path(raw)

    if label == "Platform folder" and is_office_pc():
        if normalized in {_normalize_drive_path(RADIO_PLATFORM_MAPPED), "v:"}:
            return (
                False,
                "On the Office PC, use D:\\MosPlaceRadioPlatform for the platform folder, not V:\\.",
            )

    if label == "Platform folder" and is_radio_pc():
        if normalized == _normalize_drive_path(OFFICE_PLATFORM_PHYSICAL):
            return (
                False,
                "On the Radio PC, use the mapped platform drive V:\\ instead of D:\\MosPlaceRadioPlatform.",
            )

    candidate = Path(raw)
    if not candidate.exists():
        if raw.startswith("\\\\"):
            return False, f"{label} cannot be reached. Check the network path and permissions: {raw}"
        return False, f"{label} does not exist: {raw}"

    if not candidate.is_dir():
        return False, f"{label} must be a folder, not a file: {raw}"

    if not os.access(candidate, os.R_OK):
        return False, f"{label} is not readable. Check permissions: {raw}"

    return True, "Ready to scan."


def validate_output_path(path: str) -> tuple[bool, str]:
    raw = path.strip() or DEFAULT_OUTPUT_FOLDER
    try:
        target = validate_output_write(Path(raw))
    except OSError as exc:
        return False, f"Output folder cannot be created or used: {raw} ({exc})"

    if not os.access(target, os.W_OK):
        return False, f"Output folder is not writable: {target}"

    return True, "Reports will be saved here."


def ensure_default_output_folder() -> str:
    for candidate in (DEFAULT_OUTPUT_FOLDER, RADIO_OUTPUT_FOLDER):
        ok, _message = validate_output_path(candidate)
        if ok:
            return candidate
    fallback = Path.cwd() / "InventoryReports"
    validate_output_write(fallback)
    return str(fallback)


def all_scan_paths_valid(settings: dict[str, str]) -> tuple[bool, list[str]]:
    checks = [
        validate_scan_path(settings.get("office_pc_path", ""), label="Local Office PC"),
        validate_scan_path(settings.get("radio_pc_path", ""), label="Radio PC"),
        validate_scan_path(settings.get("platform_folder", ""), label="Platform folder"),
        validate_output_path(settings.get("output_folder", "")),
    ]
    messages = [message for ok, message in checks if not ok]
    return not messages, messages

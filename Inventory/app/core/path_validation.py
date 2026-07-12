"""Validate local and UNC paths for inventory scans."""

from __future__ import annotations

import os
from pathlib import Path

from app.core.safety import validate_output_write
from app.core.settings_store import (
    DEFAULT_OUTPUT_FOLDER,
    OFFICE_PLATFORM_PHYSICAL,
    RADIO_PLATFORM_MAPPED,
    mapped_platform_available,
)


def validate_scan_path(path: str, *, label: str) -> tuple[bool, str]:
    raw = path.strip()
    if not raw:
        return False, f"{label} is required. Click Browse or enter a folder path."

    normalized = raw.rstrip("\\/")
    if (
        label == "Platform folder"
        and mapped_platform_available()
        and normalized.lower() == OFFICE_PLATFORM_PHYSICAL.rstrip("\\").lower()
    ):
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

    if label == "Platform folder" and mapped_platform_available() and normalized.lower().startswith("d:\\"):
        return False, "On the Radio PC, browse to V:\\ for the shared platform folder."

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
    ok, _message = validate_output_path(DEFAULT_OUTPUT_FOLDER)
    if ok:
        return DEFAULT_OUTPUT_FOLDER
    if mapped_platform_available():
        fallback = Path(RADIO_PLATFORM_MAPPED) / "InventoryReports"
    else:
        fallback = Path.cwd() / "InventoryReports"
    validate_output_write(fallback)
    return str(fallback)

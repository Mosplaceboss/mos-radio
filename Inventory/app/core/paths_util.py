"""Resolve user-selected folder paths for inventory scans."""

from __future__ import annotations

import os
import re
import string
from pathlib import Path

ADMIN_SHARE_PATTERN = re.compile(r"\\\\[^\\]+\\[A-Za-z]\$$", re.IGNORECASE)


def is_admin_share(path: str) -> bool:
    raw = path.strip().replace("/", "\\")
    return bool(ADMIN_SHARE_PATTERN.search(raw))


def sanitize_folder_path(path: str) -> str | None:
    raw = path.strip()
    if not raw or is_admin_share(raw):
        return None
    return raw


def is_unc_path(path: str) -> bool:
    return path.strip().startswith("\\\\")


def is_local_folder(path: str) -> bool:
    raw = path.strip()
    return bool(raw) and not is_unc_path(raw)


def resolve_scan_folder(path: str, *, label: str) -> tuple[str, list[Path], list[str]]:
    """Return label, scan roots, and resolution errors for one selected folder."""
    raw = sanitize_folder_path(path)
    if not raw:
        if is_admin_share(path.strip()):
            return label, [], [
                "Administrative shares (C$, D$, etc.) are not supported. "
                "Browse to or enter a normal shared folder instead."
            ]
        return label, [], [f"{label} path is empty."]

    try:
        root = Path(raw)
    except (OSError, PermissionError, ValueError) as exc:
        return label, [], [str(exc)]

    try:
        if not root.exists():
            return label, [], [f"Path does not exist or is not reachable: {raw}"]
        if not root.is_dir():
            return label, [], [f"Path is not a folder: {raw}"]
        if not os.access(root, os.R_OK):
            return label, [], [f"Read access denied: {raw}"]
    except (OSError, PermissionError) as exc:
        return label, [], [str(exc)]

    return label, [root], []


def resolve_scan_folders(folders: list[str], *, label: str) -> tuple[str, list[Path], list[tuple[str, str]]]:
    """Resolve many folders, collecting per-folder errors without stopping."""
    roots: list[Path] = []
    errors: list[tuple[str, str]] = []
    seen: set[str] = set()

    for folder in folders:
        cleaned = sanitize_folder_path(folder)
        if not cleaned:
            if folder.strip():
                errors.append((folder, "Administrative shares are not supported."))
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)

        _label, folder_roots, folder_errors = resolve_scan_folder(cleaned, label=label)
        roots.extend(folder_roots)
        for error in folder_errors:
            errors.append((cleaned, error))

    return label, roots, errors


def list_local_drives() -> list[tuple[str, str, int, int]]:
    drives: list[tuple[str, str, int, int]] = []
    for letter in string.ascii_uppercase:
        root = f"{letter}:\\"
        if not os.path.exists(root):
            continue
        try:
            total, _used, free = _disk_usage_windows(root)
            drives.append((letter, letter, total, free))
        except (OSError, PermissionError):
            continue
    return drives


def list_drives_for_folder(folder_path: str) -> list[tuple[str, str, int, int]]:
    if is_unc_path(folder_path):
        return []
    return list_local_drives()


def _disk_usage_windows(path: str) -> tuple[int, int, int]:
    import ctypes

    free_bytes = ctypes.c_ulonglong(0)
    total_bytes = ctypes.c_ulonglong(0)
    ctypes.windll.kernel32.GetDiskFreeSpaceExW(
        ctypes.c_wchar_p(path),
        None,
        ctypes.pointer(total_bytes),
        ctypes.pointer(free_bytes),
    )
    total = int(total_bytes.value)
    free = int(free_bytes.value)
    used = max(total - free, 0)
    return total, used, free

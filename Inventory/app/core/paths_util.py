"""Resolve computer names and scan roots."""

from __future__ import annotations

import os
import string
from pathlib import Path

from app.core.settings_store import (
    DEFAULT_OFFICE_PC,
    DEFAULT_RADIO_PC,
    OFFICE_PLATFORM_PHYSICAL,
    current_machine_name,
    is_office_pc,
)

MOS_PLACE_LOCAL_CANDIDATES = (
    r"D:\MoPlaceStudio",
    r"D:\MoPlaceStudio\mos-radio",
    OFFICE_PLATFORM_PHYSICAL,
    r"D:\MoPlace",
)


def is_computer_name(name_or_path: str) -> bool:
    raw = name_or_path.strip()
    return bool(raw) and not any(sep in raw for sep in (":", "\\", "/"))


def is_local_target(name_or_path: str) -> bool:
    raw = name_or_path.strip()
    if not raw:
        return False
    if not is_computer_name(raw):
        return False
    local_name = current_machine_name().lower()
    target = raw.lower()
    if target == local_name:
        return True
    return target == DEFAULT_OFFICE_PC.lower() and is_office_pc()


def local_scan_roots() -> list[Path]:
    roots: list[Path] = []
    seen: set[str] = set()
    for letter in string.ascii_uppercase:
        drive = Path(f"{letter}:\\")
        if drive.exists():
            key = str(drive).lower()
            if key not in seen:
                seen.add(key)
                roots.append(drive)
    for candidate in MOS_PLACE_LOCAL_CANDIDATES:
        path = Path(candidate)
        if path.exists():
            key = str(path).lower()
            if key not in seen:
                seen.add(key)
                roots.append(path)
    return roots


def remote_scan_candidates(computer: str) -> list[Path]:
    return [
        Path(fr"\\{computer}\C$"),
        Path(fr"\\{computer}\D$"),
        Path(fr"\\{computer}\V$"),
        Path(fr"\\{computer}\D$\MosPlaceRadioPlatform"),
        Path(fr"\\{computer}\MoPlace"),
        Path(fr"\\{computer}\MoPlaceStudio"),
        Path(fr"\\{computer}\mos-radio"),
    ]


def resolve_computer_root(name_or_path: str) -> tuple[str, list[Path], list[str]]:
    """Return label, scan roots, and resolution errors."""
    raw = name_or_path.strip()
    errors: list[str] = []
    if not raw:
        return "", [], ["No computer name or path provided."]

    if is_computer_name(raw):
        if is_local_target(raw):
            roots = local_scan_roots()
            if not roots:
                errors.append(f"No local drives found for {raw}.")
            return raw, roots, errors

        candidates = remote_scan_candidates(raw)
        found = [path for path in candidates if path.exists()]
        if not found:
            errors.append(
                f"Could not reach {raw} via admin shares. "
                f"Expected paths like \\\\{raw}\\C$, \\\\{raw}\\D$, or \\\\{raw}\\V$."
            )
        return raw, found, errors

    root = Path(raw)
    if root.exists():
        return raw, [root], errors
    errors.append(f"Path does not exist: {raw}")
    return raw, [], errors


def list_local_drives() -> list[tuple[str, str, int, int]]:
    drives: list[tuple[str, str, int, int]] = []
    for letter in string.ascii_uppercase:
        root = f"{letter}:\\"
        if not os.path.exists(root):
            continue
        try:
            total, _used, free = _disk_usage_windows(root)
            drives.append((letter, letter, total, free))
        except OSError:
            continue
    return drives


def list_remote_drives(computer: str) -> list[tuple[str, str, int, int]]:
    import csv
    import io
    import subprocess

    command = [
        "wmic",
        fr"/node:{computer}",
        "logicaldisk",
        "get",
        "DeviceID,VolumeName,Size,FreeSpace",
        "/format:csv",
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired):
        return []

    output = result.stdout or ""
    if not output.strip():
        return []

    reader = csv.DictReader(io.StringIO(output))
    drives: list[tuple[str, str, int, int]] = []
    for row in reader:
        device = (row.get("DeviceID") or "").strip().rstrip(":")
        if not device:
            continue
        try:
            total = int((row.get("Size") or "0").strip() or 0)
            free = int((row.get("FreeSpace") or "0").strip() or 0)
        except ValueError:
            total = 0
            free = 0
        label = (row.get("VolumeName") or device).strip()
        drives.append((device, label, total, free))
    return drives


def list_drives_for_target(name_or_path: str) -> list[tuple[str, str, int, int]]:
    if is_local_target(name_or_path):
        return list_local_drives()
    if is_computer_name(name_or_path):
        return list_remote_drives(name_or_path)
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

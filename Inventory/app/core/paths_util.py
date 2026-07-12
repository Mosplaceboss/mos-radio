"""Resolve computer names and scan roots."""

from __future__ import annotations

import os
import string
from pathlib import Path


def resolve_computer_root(name_or_path: str) -> tuple[str, list[Path]]:
    raw = name_or_path.strip()
    if not raw:
        return "", []

    if any(sep in raw for sep in (":", "\\", "/")):
        root = Path(raw)
        if root.exists():
            return raw, [root]
        return raw, []

    candidates = [
        Path(fr"\\{raw}\C$"),
        Path(fr"\\{raw}\D$"),
        Path(fr"\\{raw}\MoPlace"),
        Path(fr"\\{raw}\MoPlaceStudio"),
        Path(fr"\\{raw}\mos-radio"),
    ]
    found = [path for path in candidates if path.exists()]
    return raw, found


def list_local_drives(computer_label: str) -> list[tuple[str, str, int, int]]:
    drives: list[tuple[str, str, int, int]] = []
    for letter in string.ascii_uppercase:
        root = f"{letter}:\\"
        if not os.path.exists(root):
            continue
        try:
            total, used, free = _disk_usage_windows(root)
            label = letter
            drives.append((letter, label, total, free))
        except OSError:
            continue
    return drives


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

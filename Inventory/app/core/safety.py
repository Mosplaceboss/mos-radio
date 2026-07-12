"""Read-only safety guards for Mo's Place Inventory."""

from __future__ import annotations

import os
from pathlib import Path

FORBIDDEN_WRITE_MODES = {"w", "a", "x", "r+", "w+", "a+", "x+"}


def assert_read_only_path(path: Path) -> None:
    if not path.exists():
        return
    if not os.access(path, os.R_OK):
        raise PermissionError(f"Read access denied: {path}")


def open_read_only(path: Path):
    assert_read_only_path(path)
    return path.open("r", encoding="utf-8", errors="replace")


def validate_output_write(path: Path) -> Path:
    """Output reports are the only allowed writes."""
    path.mkdir(parents=True, exist_ok=True)
    return path

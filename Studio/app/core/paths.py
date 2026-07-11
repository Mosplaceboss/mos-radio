"""Resolve filesystem paths for development and frozen executables."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


def studio_root() -> Path:
    """Return the Studio directory (parent of app/)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent.parent


def resource_root() -> Path:
    """Return read-only bundled resources (assets, default config)."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", studio_root()))
    return studio_root()


def config_dir() -> Path:
    """Return the writable configuration directory."""
    path = studio_root() / "config"
    path.mkdir(parents=True, exist_ok=True)
    return path


def assets_dir() -> Path:
    """Return the assets directory."""
    return resource_root() / "assets"


def writable_assets_dir() -> Path:
    """Return the writable assets directory beside the Studio root."""
    path = studio_root() / "assets"
    path.mkdir(parents=True, exist_ok=True)
    return path


def personality_images_dir() -> Path:
    """Return the directory for personality profile images."""
    path = writable_assets_dir() / "personalities"
    path.mkdir(parents=True, exist_ok=True)
    return path


def voice_portraits_dir() -> Path:
    """Return the directory for voice portrait images."""
    path = writable_assets_dir() / "voices"
    path.mkdir(parents=True, exist_ok=True)
    return path


def logs_dir() -> Path:
    """Return the writable logs directory."""
    path = studio_root() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_default_configs() -> None:
    """Copy bundled default JSON configs on first run of a frozen build."""
    bundled = resource_root() / "config"
    if not bundled.exists():
        return

    target = config_dir()
    for source in bundled.glob("*.json"):
        destination = target / source.name
        if not destination.exists():
            shutil.copy2(source, destination)

"""Shared helpers for headless Studio verification scripts."""

from __future__ import annotations

import os
from copy import deepcopy

from app.core.config_manager import ConfigManager
from app.core.user_modes import USER_MODE_ADVANCED

os.environ.setdefault("STUDIO_VERIFY", "1")


def prepare_verify_config(config_manager: ConfigManager) -> dict:
    """Use Advanced Mode in memory so every page opens without modal dialogs."""
    settings = config_manager.load("settings")
    settings["user_mode"] = USER_MODE_ADVANCED
    settings["setup_complete"] = True
    config_manager._cache["settings"] = deepcopy(settings)
    return settings

"""JSON configuration load/save manager."""

from __future__ import annotations

import json
import logging
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

from app.core.paths import config_dir, ensure_default_configs

logger = logging.getLogger("moplace.studio.config")


class ConfigManager:
    """Loads and persists named JSON configuration files."""

    def __init__(self) -> None:
        ensure_default_configs()
        self._cache: dict[str, dict[str, Any]] = {}
        self._listeners: dict[str, list[Callable[[str, dict[str, Any]], None]]] = {}

    def path_for(self, name: str) -> Path:
        return config_dir() / f"{name}.json"

    def load(self, name: str, default: dict[str, Any] | None = None) -> dict[str, Any]:
        file_path = self.path_for(name)
        if name in self._cache:
            return deepcopy(self._cache[name])

        if file_path.exists():
            try:
                with file_path.open("r", encoding="utf-8") as handle:
                    data = json.load(handle)
                self._cache[name] = data
                logger.debug("Loaded config '%s' from %s", name, file_path)
                return deepcopy(data)
            except (OSError, json.JSONDecodeError) as exc:
                logger.error("Failed to load config '%s': %s", name, exc)

        fallback = deepcopy(default or {})
        self._cache[name] = fallback
        return deepcopy(fallback)

    def save(self, name: str, data: dict[str, Any]) -> None:
        file_path = self.path_for(name)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with file_path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
            handle.write("\n")
        self._cache[name] = deepcopy(data)
        logger.info("Saved config '%s' to %s", name, file_path)
        self._notify(name, data)

    def subscribe(self, name: str, callback: Callable[[str, dict[str, Any]], None]) -> None:
        self._listeners.setdefault(name, []).append(callback)

    def _notify(self, name: str, data: dict[str, Any]) -> None:
        for callback in self._listeners.get(name, []):
            callback(name, deepcopy(data))

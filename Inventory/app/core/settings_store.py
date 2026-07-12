"""Persist Inventory UI settings per machine."""

from __future__ import annotations

import json
import os
import socket
import sys
from pathlib import Path

# Office PC physical location of the shared platform.
OFFICE_PLATFORM_PHYSICAL = r"D:\MosPlaceRadioPlatform"

# Radio PC mapped drive for the same shared platform.
RADIO_PLATFORM_MAPPED = r"V:\\"

DEFAULT_OUTPUT_FOLDER = r"V:\Documentation\InventoryReports"

SETTING_KEYS = (
    "office_pc_path",
    "radio_pc_path",
    "platform_folder",
    "output_folder",
)


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent.parent


def settings_path() -> Path:
    return app_root() / "inventory_settings.json"


def current_machine_name() -> str:
    return (os.environ.get("COMPUTERNAME") or socket.gethostname() or "unknown").strip()


def mapped_platform_available() -> bool:
    return Path(RADIO_PLATFORM_MAPPED).exists()


def office_platform_available() -> bool:
    return Path(OFFICE_PLATFORM_PHYSICAL).exists()


def machine_defaults() -> dict[str, str]:
    defaults = {
        "office_pc_path": "",
        "radio_pc_path": "",
        "platform_folder": "",
        "output_folder": DEFAULT_OUTPUT_FOLDER,
    }

    if mapped_platform_available():
        defaults["platform_folder"] = RADIO_PLATFORM_MAPPED
        defaults["output_folder"] = DEFAULT_OUTPUT_FOLDER
        defaults["radio_pc_path"] = RADIO_PLATFORM_MAPPED
    elif office_platform_available():
        defaults["platform_folder"] = OFFICE_PLATFORM_PHYSICAL
        defaults["office_pc_path"] = OFFICE_PLATFORM_PHYSICAL
        defaults["output_folder"] = str(Path(OFFICE_PLATFORM_PHYSICAL) / "Documentation" / "InventoryReports")

    return defaults


def _empty_settings() -> dict[str, str]:
    return {key: "" for key in SETTING_KEYS}


def _read_store() -> dict:
    path = settings_path()
    if not path.exists():
        return {"machines": {}}
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {"machines": {}}

    if isinstance(data, dict) and "machines" in data:
        return data

    # Migrate legacy flat settings into the current machine profile.
    if isinstance(data, dict):
        migrated = _empty_settings()
        for key in SETTING_KEYS:
            value = data.get(key, "")
            if isinstance(value, str):
                migrated[key] = value.strip()
        return {"machines": {current_machine_name(): migrated}}

    return {"machines": {}}


def _normalize_machine_settings(values: dict[str, str]) -> dict[str, str]:
    defaults = machine_defaults()
    merged = _empty_settings()
    for key in SETTING_KEYS:
        value = values.get(key, "").strip()
        merged[key] = value or defaults.get(key, "")
    if not merged["output_folder"]:
        merged["output_folder"] = defaults["output_folder"] or DEFAULT_OUTPUT_FOLDER
    return merged


def load_settings() -> dict[str, str]:
    store = _read_store()
    machine = current_machine_name()
    machines = store.get("machines", {})
    saved = machines.get(machine, {})
    if not isinstance(saved, dict):
        saved = {}
    return _normalize_machine_settings(saved)


def save_settings(values: dict[str, str]) -> None:
    store = _read_store()
    machine = current_machine_name()
    machines = store.setdefault("machines", {})
    machines[machine] = _normalize_machine_settings(values)
    settings_path().write_text(json.dumps(store, indent=2) + "\n", encoding="utf-8")

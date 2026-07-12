"""Persist Inventory UI settings per machine."""

from __future__ import annotations

import json
import os
import socket
import sys
from pathlib import Path

from app.core.paths_util import is_admin_share, sanitize_folder_path

# Office PC physical location of the shared platform.
OFFICE_PLATFORM_PHYSICAL = r"D:\MosPlaceRadioPlatform"

# Radio PC mapped drive for the same shared platform.
RADIO_PLATFORM_MAPPED = r"V:\\"

# Primary deployment default (Office PC).
DEFAULT_OUTPUT_FOLDER = r"D:\MosPlaceRadioPlatform\Documentation\InventoryReports"
RADIO_OUTPUT_FOLDER = r"V:\Documentation\InventoryReports"

DEFAULT_OFFICE_FOLDERS = (
    r"D:\MoPlaceStudio",
    OFFICE_PLATFORM_PHYSICAL,
    r"D:\MosNews",
)

SETTING_KEYS = (
    "office_pc_folders",
    "radio_pc_folders",
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


def is_office_pc() -> bool:
    return office_platform_available()


def is_radio_pc() -> bool:
    return mapped_platform_available() and not office_platform_available()


def sanitize_folder_list(folders: list[str] | str | None) -> list[str]:
    if isinstance(folders, str):
        folders = [folders]
    if not folders:
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in folders:
        path = sanitize_folder_path(str(item))
        if not path:
            continue
        key = path.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(path)
    return cleaned


def default_office_folders() -> list[str]:
    if is_office_pc():
        return list(DEFAULT_OFFICE_FOLDERS)
    return []


def machine_defaults() -> dict:
    defaults = {
        "office_pc_folders": default_office_folders(),
        "radio_pc_folders": [],
        "output_folder": DEFAULT_OUTPUT_FOLDER,
    }
    if is_radio_pc():
        defaults["output_folder"] = RADIO_OUTPUT_FOLDER
    return defaults


def _empty_settings() -> dict:
    return {
        "office_pc_folders": [],
        "radio_pc_folders": [],
        "output_folder": "",
    }


def _migrate_legacy_settings(data: dict) -> dict:
    office_folders: list[str] = []
    radio_folders: list[str] = []
    output_folder = str(data.get("output_folder", "")).strip()

    for key in ("office_pc_folders", "radio_pc_folders"):
        value = data.get(key)
        if isinstance(value, list):
            if key == "office_pc_folders":
                office_folders.extend(str(item) for item in value)
            else:
                radio_folders.extend(str(item) for item in value)

    for legacy_key, target in (
        ("office_pc_path", office_folders),
        ("platform_folder", office_folders),
        ("radio_pc_path", radio_folders),
    ):
        value = str(data.get(legacy_key, "")).strip()
        if value:
            target.append(value)

    return {
        "office_pc_folders": sanitize_folder_list(office_folders) or default_office_folders(),
        "radio_pc_folders": sanitize_folder_list(radio_folders),
        "output_folder": output_folder,
    }


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

    if isinstance(data, dict):
        return {"machines": {current_machine_name(): _migrate_legacy_settings(data)}}

    return {"machines": {}}


def _normalize_machine_settings(values: dict) -> dict:
    defaults = machine_defaults()
    migrated = _migrate_legacy_settings(values if isinstance(values, dict) else {})
    office_folders = sanitize_folder_list(migrated.get("office_pc_folders"))
    radio_folders = sanitize_folder_list(migrated.get("radio_pc_folders"))
    output_folder = str(migrated.get("output_folder", "")).strip()

    if not office_folders:
        office_folders = defaults["office_pc_folders"]
    if not output_folder:
        output_folder = defaults["output_folder"] or DEFAULT_OUTPUT_FOLDER

    return {
        "office_pc_folders": office_folders,
        "radio_pc_folders": radio_folders,
        "output_folder": output_folder,
    }


def load_settings() -> dict:
    store = _read_store()
    machine = current_machine_name()
    machines = store.get("machines", {})
    saved = machines.get(machine, {})
    if not isinstance(saved, dict):
        saved = {}
    return _normalize_machine_settings(saved)


def save_settings(values: dict) -> None:
    store = _read_store()
    machine = current_machine_name()
    machines = store.setdefault("machines", {})
    machines[machine] = _normalize_machine_settings(values)
    settings_path().write_text(json.dumps(store, indent=2) + "\n", encoding="utf-8")


def _existing_dir(path: str) -> str | None:
    try:
        candidate = Path(path.strip())
        if candidate.is_dir():
            return str(candidate)
        parent = candidate.parent
        parent_text = str(parent)
        if parent_text not in {"", "."} and parent.is_dir():
            return str(parent)
    except (OSError, PermissionError, ValueError):
        return None
    return None


def browse_initial_dir(key: str, current: str = "") -> str:
    """Pick a sensible starting folder for each Browse dialog."""
    if current.strip():
        existing = _existing_dir(current)
        if existing:
            return existing

    if key == "office_pc_folders":
        for candidate in (DEFAULT_OFFICE_FOLDERS[0], OFFICE_PLATFORM_PHYSICAL, "D:\\"):
            existing = _existing_dir(candidate)
            if existing:
                return existing

    if key == "radio_pc_folders":
        return r"\\"

    if key == "output_folder":
        for candidate in (
            DEFAULT_OUTPUT_FOLDER,
            RADIO_OUTPUT_FOLDER,
            str(Path(DEFAULT_OUTPUT_FOLDER).parent),
            OFFICE_PLATFORM_PHYSICAL,
        ):
            existing = _existing_dir(candidate)
            if existing:
                return existing

    return str(Path.home())

"""Operations Manager models — status, backup, deployment, migration, and safety."""

from __future__ import annotations

import shutil
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.health_constants import HEALTH_ERROR, HEALTH_OK, HEALTH_WARN
from app.core.operations_manager_storage import (
    deployment_path,
    load_operations_bundle,
    save_operations_bundle,
)
from app.core.paths import config_dir
from app.core.platform_manager import (
    PATH_DEFINITIONS,
    integration_paths_from_platform,
    load_platform_config,
    platform_backups_dir,
    platform_path,
    test_platform_path,
)
from app.core.publish_manager import integration_bundle
from app.core.studio_info import APP_VERSION, environment_mode
from app.core.system_status import build_live_system_status, service_lookup

OPERATION_MODULES = (
    "RadioDJ",
    "Voicebox",
    "LiveDJ",
    "News",
    "Request Watcher",
    "Website Scheduler",
)

MIGRATION_MODULE_IDS = (
    ("livedj", "LiveDJ"),
    ("news", "News"),
    ("requests", "Requests"),
    ("website", "Website"),
    ("studio", "Studio"),
    ("advertising", "Advertising"),
    ("shared_voice", "Shared voice files"),
)

MIGRATION_STATUSES = (
    "not_started",
    "copied",
    "testing",
    "ready",
    "production",
    "archived",
)

BACKUP_TYPES = (
    ("studio_settings", "Studio settings"),
    ("platform_configuration", "Platform configuration"),
    ("personalities", "Personalities"),
    ("voices", "Voices"),
    ("schedules", "Schedules"),
    ("advertising", "Advertising data"),
    ("website", "Website data"),
)

PRODUCTION_MAP_KEYS = (
    ("office_pc", "Office PC", "platform_root"),
    ("radio_pc", "Radio PC", "radiodj"),
    ("shared_platform", "Shared Platform", "platform_root"),
    ("radiodj", "RadioDJ", "radiodj"),
    ("music_library", "Music Library", "music_library"),
    ("voice_folders", "Voice folders", "assets_voices"),
    ("scheduled_tasks", "Scheduled tasks", "automation_news"),
)


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _plain_message(status: str, detail: str) -> str:
    if status == HEALTH_OK:
        return detail or "Everything looks good."
    if status == HEALTH_WARN:
        return detail or "Needs attention soon."
    return detail or "Needs help right away."


@dataclass
class StatusCard:
    name: str
    status: str
    detail: str
    plain_message: str = ""


def build_system_status_cards(config_manager) -> list[StatusCard]:
    settings = config_manager.load("settings", {})
    live = build_live_system_status(settings, force_refresh=True)
    cards: list[StatusCard] = []

    service_names = (
        "RadioDJ",
        "Voicebox",
        "LiveDJ Watcher",
        "News Tasks",
        "Request Watcher",
        "Internet",
    )
    display_names = {
        "LiveDJ Watcher": "LiveDJ",
        "News Tasks": "News",
        "Request Watcher": "Requests",
    }
    for service_name in service_names:
        service = service_lookup(live, service_name)
        label = display_names.get(service_name, service_name)
        if service:
            cards.append(
                StatusCard(
                    label,
                    service.status,
                    service.detail,
                    _plain_message(service.status, service.detail),
                )
            )
        else:
            cards.append(
                StatusCard(label, HEALTH_WARN, "Not monitored", "This service is not being monitored yet.")
            )

    website_path = platform_path("automation_website", config_manager)
    if website_path.exists():
        cards.append(
            StatusCard(
                "Website",
                HEALTH_OK,
                f"Folder ready ({len(list(website_path.glob('*')))} item(s))",
                "Website automation folder is available.",
            )
        )
    else:
        cards.append(
            StatusCard("Website", HEALTH_WARN, "Folder not found", "Website folder was not found on this computer.")
        )

    platform_root = platform_path("platform_root", config_manager)
    platform_test = test_platform_path("platform_root", str(platform_root))
    cards.append(
        StatusCard(
            "Platform folder",
            platform_test["status"],
            platform_test["message"],
            _plain_message(platform_test["status"], platform_test["message"]),
        )
    )

    voices_path = platform_path("assets_voices", config_manager)
    voices_test = test_platform_path("assets_voices", str(voices_path))
    cards.append(
        StatusCard(
            "Shared voice folders",
            voices_test["status"],
            voices_test["message"],
            _plain_message(voices_test["status"], voices_test["message"]),
        )
    )

    return cards


def default_migration_modules() -> list[dict[str, Any]]:
    return [
        {
            "id": module_id,
            "name": label,
            "status": "not_started",
            "source_path": "",
            "destination_path": "",
            "files_copied": 0,
            "verified": False,
            "notes": "",
            "last_action": "",
        }
        for module_id, label in MIGRATION_MODULE_IDS
    ]


def normalize_migration(data: dict[str, Any] | None, config_manager=None) -> dict[str, Any]:
    modules = data.get("modules", []) if data else []
    if not modules:
        modules = default_migration_modules()
    integration = integration_paths_from_platform(config_manager)
    normalized = []
    for item in modules:
        record = deepcopy(item)
        record.setdefault("id", _new_id("mod"))
        record.setdefault("name", "Module")
        record.setdefault("status", "not_started")
        record.setdefault("source_path", "")
        record.setdefault("destination_path", "")
        record.setdefault("files_copied", 0)
        record.setdefault("verified", False)
        record.setdefault("notes", "")
        record.setdefault("last_action", "")
        module_id = record.get("id", "")
        if not record.get("destination_path") and module_id in {
            key for key, _ in MIGRATION_MODULE_IDS
        }:
            mapping = {
                "livedj": "automation_livedj",
                "news": "automation_news",
                "requests": "automation_requests",
                "website": "automation_website",
                "advertising": "automation_advertising",
                "shared_voice": "assets_voices",
                "studio": "station_data",
            }
            key = mapping.get(module_id)
            if key:
                record["destination_path"] = str(platform_path(key, config_manager))
        if not record.get("source_path") and module_id in integration:
            record["source_path"] = integration[module_id].get("config", integration[module_id].get("folder", ""))
        normalized.append(record)
    return {"modules": normalized}


def normalize_bundle(data: dict[str, Any] | None, config_manager=None) -> dict[str, Any]:
    payload = data or {}
    deployment = payload.get("deployment", {})
    deployment.setdefault("development_version", f"{APP_VERSION}-dev")
    deployment.setdefault("production_version", APP_VERSION)
    deployment.setdefault("build_date", datetime.now().strftime("%Y-%m-%d"))
    deployment.setdefault("release_notes", "")
    return {
        "deployment": deployment,
        "migration": normalize_migration(payload.get("migration"), config_manager),
        "log": payload.get(
            "log",
            {
                "operations": [],
                "backups": [],
                "deployments": [],
                "migrations": [],
                "errors": [],
                "warnings": [],
            },
        ),
        "state": payload.get("state", {"last_validated": "", "version": 1}),
    }


def ensure_operations_data(config_manager=None) -> None:
    if deployment_path(config_manager).exists():
        return
    bundle = normalize_bundle({}, config_manager)
    save_operations_bundle(bundle, config_manager)


def append_log(bundle: dict[str, Any], category: str, message: str) -> None:
    entry = {"timestamp": datetime.now().strftime("%Y-%m-%d %I:%M %p"), "message": message}
    log = bundle.setdefault("log", {})
    log.setdefault(category, []).insert(0, entry)
    log[category] = log[category][:100]


def backup_sources_for_type(backup_type: str, config_manager) -> dict[str, Path]:
    cfg = config_dir()
    sources: dict[str, Path] = {}
    if backup_type == "studio_settings":
        for path in cfg.glob("*.json"):
            if path.name != "integration.local.json":
                sources[path.stem] = path
    elif backup_type == "platform_configuration":
        sources["PlatformManager"] = cfg / "PlatformManager.json"
    elif backup_type == "personalities":
        sources["personalities"] = cfg / "personalities.json"
    elif backup_type == "voices":
        sources["voice_library"] = cfg / "voice_library.json"
    elif backup_type == "schedules":
        sources["schedule"] = cfg / "schedule.json"
    elif backup_type == "advertising":
        folder = platform_path("automation_advertising", config_manager)
        if folder.exists():
            sources["advertising_folder"] = folder
    elif backup_type == "website":
        folder = platform_path("automation_website", config_manager)
        if folder.exists():
            sources["website_folder"] = folder
    return sources


def run_backup(backup_type: str, config_manager, bundle: dict[str, Any]) -> tuple[bool, str, Path | None]:
    sources = backup_sources_for_type(backup_type, config_manager)
    if not sources:
        return False, f"No backup sources found for {backup_type}.", None

    backup_root = platform_backups_dir(config_manager)
    backup_root.mkdir(parents=True, exist_ok=True)
    timestamp = _timestamp()
    target = backup_root / backup_type / timestamp
    target.mkdir(parents=True, exist_ok=True)
    copied = 0
    for name, source in sources.items():
        if not source.exists():
            continue
        if source.is_dir():
            shutil.copytree(source, target / name, dirs_exist_ok=True)
        else:
            shutil.copy2(source, target / f"{name}{source.suffix}")
        copied += 1

    if copied == 0:
        return False, "Nothing was copied — source files were missing.", None

    message = f"Backed up {backup_type} to {target}"
    append_log(
        bundle,
        "backups",
        f"{backup_type} · {timestamp} · {copied} item(s)",
    )
    append_log(bundle, "operations", message)
    return True, message, target


def list_backup_history(config_manager) -> list[str]:
    backup_root = platform_backups_dir(config_manager)
    lines: list[str] = []
    if not backup_root.exists():
        return ["No backups found yet."]
    for backup_type, _label in BACKUP_TYPES:
        folder = backup_root / backup_type
        if not folder.exists():
            continue
        for path in sorted(folder.iterdir(), reverse=True)[:5]:
            if path.is_dir():
                lines.append(f"{backup_type} · {path.name}")
    return lines or ["No backups found yet."]


def restore_backup_folder(backup_path: Path, destinations: dict[str, Path]) -> tuple[bool, str]:
    if not backup_path.exists():
        return False, "Backup folder not found."
    restored = 0
    for name, destination in destinations.items():
        source = backup_path / f"{name}{destination.suffix}"
        if source.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            restored += 1
            continue
        folder_source = backup_path / name
        if folder_source.exists() and folder_source.is_dir():
            if destination.exists():
                shutil.copytree(folder_source, destination, dirs_exist_ok=True)
            else:
                shutil.copytree(folder_source, destination)
            restored += 1
    if restored == 0:
        return False, "No matching files found in the selected backup."
    return True, f"Restored {restored} item(s) from {backup_path.name}."


def validate_deployment(bundle: dict[str, Any], config_manager) -> list[str]:
    warnings: list[str] = []
    config = load_platform_config(config_manager)
    for key in ("platform_root", "automation_livedj", "automation_news", "automation_requests"):
        result = test_platform_path(key, config["paths"].get(key, ""))
        if result["status"] != HEALTH_OK:
            warnings.append(f"{PATH_DEFINITIONS[key]['label']}: {result['message']}")

    for name in ("personalities", "voice_library", "schedule", "settings"):
        path = config_dir() / f"{name}.json"
        if not path.exists():
            warnings.append(f"Missing Studio config: {name}.json")

    if not bundle["deployment"].get("release_notes", "").strip():
        warnings.append("Release notes are empty.")

    return warnings


def create_deployment_package(config_manager, bundle: dict[str, Any]) -> tuple[bool, str, Path | None]:
    warnings = validate_deployment(bundle, config_manager)
    if warnings:
        return False, "Deployment validation failed:\n" + "\n".join(warnings), None

    backup_ok, backup_msg, _ = run_backup("studio_settings", config_manager, bundle)
    if not backup_ok:
        return False, f"Automatic production backup failed: {backup_msg}", None

    deploy_root = platform_backups_dir(config_manager) / "Deployments" / _timestamp()
    deploy_root.mkdir(parents=True, exist_ok=True)
    copied = 0
    for path in config_dir().glob("*.json"):
        if path.name.startswith("integration"):
            continue
        shutil.copy2(path, deploy_root / path.name)
        copied += 1

    bundle["deployment"]["last_deployed"] = datetime.now().strftime("%Y-%m-%d %I:%M %p")
    append_log(bundle, "deployments", f"Package created · {deploy_root.name} · {copied} files")
    append_log(bundle, "operations", f"Deployment package created at {deploy_root}")
    return True, f"Deployment package created with {copied} files. Live station was not modified.", deploy_root


def rollback_deployment(config_manager, bundle: dict[str, Any]) -> tuple[bool, str]:
    deploy_root = platform_backups_dir(config_manager) / "Deployments"
    if not deploy_root.exists():
        return False, "No deployment packages found."
    packages = sorted((p for p in deploy_root.iterdir() if p.is_dir()), reverse=True)
    if len(packages) < 2:
        return False, "Need at least two deployment packages to roll back."

    previous = packages[1]
    restored = 0
    for path in previous.glob("*.json"):
        destination = config_dir() / path.name
        shutil.copy2(path, destination)
        restored += 1

    bundle["deployment"]["last_rollback"] = datetime.now().strftime("%Y-%m-%d %I:%M %p")
    append_log(bundle, "deployments", f"Rolled back to {previous.name}")
    append_log(bundle, "operations", f"Rolled back Studio config to {previous.name}")
    return True, f"Rolled back {restored} Studio config file(s) to {previous.name}. Live station was not modified."


def _module_paths(module_id: str, config_manager) -> tuple[Path, Path]:
    mapping = {
        "livedj": ("automation_livedj", "automation_livedj"),
        "news": ("automation_news", "automation_news"),
        "requests": ("automation_requests", "automation_requests"),
        "website": ("automation_website", "automation_website"),
        "advertising": ("automation_advertising", "automation_advertising"),
        "shared_voice": ("assets_voices", "assets_voices"),
        "studio": ("station_data", "station_data"),
    }
    key = mapping.get(module_id)
    if not key:
        return Path(), Path()
    dest = platform_path(key[1], config_manager)
    integration = integration_paths_from_platform(config_manager)
    source_str = ""
    if module_id in integration:
        source_str = integration[module_id].get("config", integration[module_id].get("folder", ""))
    elif module_id == "studio":
        source_str = str(platform_path("station_data", config_manager))
    elif module_id in {"shared_voice"}:
        source_str = str(platform_path("assets_voices", config_manager))
    else:
        source_str = str(dest)
    return Path(source_str), dest


def copy_migration_module(
    module: dict[str, Any],
    config_manager,
    bundle: dict[str, Any],
) -> tuple[bool, str]:
    source = Path(module.get("source_path") or "")
    destination = Path(module.get("destination_path") or "")
    if not source.exists():
        return False, f"Source path not found: {source}"
    staging = destination / f"staging_{_timestamp()}"
    staging.mkdir(parents=True, exist_ok=True)
    copied = 0

    if source.is_file():
        shutil.copy2(source, staging / source.name)
        copied = 1
    else:
        for path in source.rglob("*"):
            if path.is_file():
                relative = path.relative_to(source)
                target = staging / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
                copied += 1

    module["files_copied"] = copied
    module["status"] = "copied"
    module["last_action"] = datetime.now().strftime("%Y-%m-%d %I:%M %p")
    module["verified"] = False
    module["notes"] = f"Staging copy at {staging}"
    append_log(bundle, "migrations", f"Copied {module.get('name', '')} · {copied} file(s) to {staging.name}")
    return True, f"Copied {copied} file(s) for {module.get('name', '')} to staging. Originals were not moved."


def verify_migration_copy(module: dict[str, Any]) -> tuple[bool, str, str]:
    source = Path(module.get("source_path") or "")
    destination = Path(module.get("destination_path") or "")
    if not source.exists():
        return False, "Source missing", "Source path no longer exists."
    if not destination.exists():
        return False, "Destination missing", "Destination path was not found."

    if source.is_file() and destination.is_file():
        match = source.stat().st_size == destination.stat().st_size
        module["verified"] = match
        return match, "Match" if match else "Mismatch", f"Source {source.stat().st_size} bytes vs dest {destination.stat().st_size} bytes"

    source_files = list(source.rglob("*")) if source.is_dir() else [source]
    dest_files = list(destination.rglob("*")) if destination.is_dir() else [destination]
    source_count = sum(1 for p in source_files if p.is_file())
    dest_count = sum(1 for p in dest_files if p.is_file())
    match = source_count == dest_count
    module["verified"] = match
    return (
        match,
        "Match" if match else "Mismatch",
        f"Source files: {source_count} · Destination files: {dest_count}",
    )


def build_production_map(config_manager) -> list[str]:
    config = load_platform_config(config_manager)
    lines = ["Production Map", ""]
    for _key, label, path_key in PRODUCTION_MAP_KEYS:
        current = config["paths"].get(path_key, "")
        future = PATH_DEFINITIONS.get(path_key, {}).get("default") or PATH_DEFINITIONS.get(path_key, {}).get("relative", "")
        if "relative" in PATH_DEFINITIONS.get(path_key, {}):
            future = str(platform_path("platform_root", config_manager) / PATH_DEFINITIONS[path_key]["relative"])
        lines.append(f"{label}")
        lines.append(f"  Current: {current}")
        lines.append(f"  Future:  {future}")
        lines.append("")
    return lines


def get_module_operation_info(module_name: str, config_manager) -> dict[str, str]:
    integration = integration_bundle(config_manager.load("settings", {}))
    paths = integration_paths_from_platform(config_manager)
    info = {"folder": "", "log": ""}
    if module_name == "RadioDJ":
        info["folder"] = paths["radiodj"]["folder"]
    elif module_name == "LiveDJ":
        info["folder"] = str(platform_path("automation_livedj", config_manager))
        info["log"] = str(platform_path("automation_livedj", config_manager) / "livedj.log")
    elif module_name == "News":
        info["folder"] = str(platform_path("automation_news", config_manager))
        info["log"] = str(platform_path("automation_news", config_manager) / "news.log")
    elif module_name == "Request Watcher":
        info["folder"] = str(platform_path("automation_requests", config_manager))
        info["log"] = str(platform_path("automation_requests", config_manager) / "requests.log")
    elif module_name == "Website Scheduler":
        info["folder"] = str(platform_path("automation_website", config_manager))
    return info


def safety_summary(settings: dict[str, Any]) -> dict[str, Any]:
    mode = environment_mode(settings)
    return {
        "mode": mode,
        "production_actions_require_confirmation": True,
        "delete_operations_allowed": False,
        "automatic_cutover_allowed": False,
        "radiodj_database_changes": False,
        "task_scheduler_changes": False,
    }


def collect_recent_logs(bundle: dict[str, Any]) -> dict[str, list[str]]:
    log = bundle.get("log", {})
    return {
        "operations": [entry["message"] for entry in log.get("operations", [])[:20]],
        "backups": [entry["message"] for entry in log.get("backups", [])[:20]],
        "deployments": [entry["message"] for entry in log.get("deployments", [])[:20]],
        "migrations": [entry["message"] for entry in log.get("migrations", [])[:20]],
        "errors": [entry["message"] for entry in log.get("errors", [])[:20]],
        "warnings": [entry["message"] for entry in log.get("warnings", [])[:20]],
    }

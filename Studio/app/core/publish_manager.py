"""Safe publish workflows with backup support."""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any

from app.core.backup_manager import create_backup, restore_last_backup
from app.core.integration_settings import (
    livedj_live_paths,
    news_live_paths,
    normalize_integration_settings,
    requests_live_paths,
    studio_config_path,
)
from app.core.livedj_integration import import_livedj_from_live, livedj_publish_files, validate_livedj_bundle
from app.core.news_model import normalize_news_data, validate_news_data
from app.core.requests_model import normalize_requests_data, validate_requests_settings

logger = logging.getLogger("moplace.studio.publish")


def _copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")


def import_requests_from_live(integration: dict[str, Any]) -> tuple[bool, str]:
    live = requests_live_paths(integration)
    source = live["config"]
    if not source.exists():
        return False, f"Live request config not found: {source}"
    destination = studio_config_path("requests")
    shutil.copy2(source, destination)
    return True, "Imported live request settings into Studio development config."


def import_news_from_live(integration: dict[str, Any]) -> tuple[bool, str]:
    live = news_live_paths(integration)
    source = live["config"]
    if not source.exists():
        return False, f"Live news config not found: {source}"
    destination = studio_config_path("news")
    shutil.copy2(source, destination)
    return True, "Imported live news configuration into Studio development config."


def publish_livedj(config_manager, integration: dict[str, Any]) -> tuple[bool, str]:
    errors = validate_livedj_bundle(config_manager)
    if errors:
        return False, "Validation failed:\n" + "\n".join(errors[:12])

    files = livedj_publish_files(integration)
    backup_sources = {key: destination for key, (_, destination) in files.items() if destination.exists()}
    if backup_sources:
        create_backup("livedj", backup_sources)

    copied = 0
    for key, (source, destination) in files.items():
        if not source.exists():
            return False, f"Development config missing: {source.name}"
        _copy_file(source, destination)
        copied += 1

    logger.info("Published LiveDJ configuration (%s files)", copied)
    return True, f"Published {copied} LiveDJ file(s) to live paths with backup."


def publish_requests(config_manager, integration: dict[str, Any]) -> tuple[bool, str]:
    data = normalize_requests_data(config_manager.load("requests", {}))
    errors, _warnings = validate_requests_settings(data)
    if errors:
        return False, "Validation failed:\n" + "\n".join(errors)

    live = requests_live_paths(integration)
    destination = live["config"]
    backup_sources = {"requests": destination} if destination.exists() else {}
    if backup_sources:
        create_backup("requests", backup_sources)

    _write_json(destination, data)
    config_manager.save("requests", data)
    return True, "Published request settings to live path with backup."


def publish_news(config_manager, integration: dict[str, Any]) -> tuple[bool, str]:
    data = normalize_news_data(config_manager.load("news", {}))
    errors = validate_news_data(data)
    if errors:
        return False, "Validation failed:\n" + "\n".join(errors)

    live = news_live_paths(integration)
    destination = live["config"]
    backup_sources = {"news": destination} if destination.exists() else {}
    if backup_sources:
        create_backup("news", backup_sources)

    _write_json(destination, data)
    config_manager.save("news", data)
    return True, "Published news configuration to live path with backup."


def restore_livedj_backup(integration: dict[str, Any]) -> tuple[bool, str]:
    files = livedj_publish_files(integration)
    destinations = {key: destination for key, (_, destination) in files.items()}
    return restore_last_backup("livedj", destinations)


def restore_requests_backup(integration: dict[str, Any]) -> tuple[bool, str]:
    live = requests_live_paths(integration)
    return restore_last_backup("requests", {"requests": live["config"]})


def restore_news_backup(integration: dict[str, Any]) -> tuple[bool, str]:
    live = news_live_paths(integration)
    return restore_last_backup("news", {"news": live["config"]})


def integration_bundle(settings: dict[str, Any]) -> dict[str, Any]:
    return normalize_integration_settings(settings)

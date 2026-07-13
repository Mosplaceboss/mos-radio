"""Cross-module summaries for the integrated Studio v2 dashboard."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from app.core.advertising_model import build_overview_lines as advertising_lines, normalize_bundle as normalize_advertising
from app.core.advertising_storage import load_advertising_bundle
from app.core.health_constants import HEALTH_ERROR, HEALTH_OK, HEALTH_WARN
from app.core.operations_manager_model import list_backup_history
from app.core.platform_manager import load_platform_config, validate_all_paths
from app.core.schedule_model import normalize_schedule_data
from app.core.station_data import inventory_reports_dir
from app.core.website_audience_model import build_overview_lines as website_lines, normalize_bundle as normalize_website
from app.core.website_audience_storage import load_website_bundle


@dataclass
class IntegrationSnapshot:
    platform_status: str = HEALTH_OK
    platform_message: str = "Platform paths not checked yet."
    inventory_status: str = HEALTH_WARN
    inventory_message: str = "No inventory scan found."
    advertising_summary: str = "Advertising not loaded."
    website_summary: str = "Website not loaded."
    schedule_summary: str = "Schedule not loaded."
    backup_summary: str = "No backups found."
    alerts: list[str] = field(default_factory=list)
    module_lines: list[str] = field(default_factory=list)


def _inventory_status(config_manager) -> tuple[str, str]:
    reports_dir = inventory_reports_dir(config_manager)
    inventory_file = reports_dir / "Inventory.json"
    if not inventory_file.exists():
        return HEALTH_WARN, "No inventory scan found."
    try:
        data = json.loads(inventory_file.read_text(encoding="utf-8"))
        scanned_at = data.get("scanned_at", "Unknown time")
        status = data.get("status", "unknown")
        return HEALTH_OK, f"Last scan: {scanned_at} · status: {status}"
    except (OSError, json.JSONDecodeError):
        return HEALTH_WARN, "Inventory report found but could not be read."


def _schedule_status(config_manager) -> str:
    schedule = normalize_schedule_data(config_manager.load("schedule", {"slots": []}), [])
    slots = schedule.get("slots", [])
    enabled = sum(1 for slot in slots if slot.get("enabled", True))
    return f"{len(slots)} slots configured, {enabled} active"


def _backup_status(config_manager) -> str:
    history = list_backup_history(config_manager)
    if history and history[0] != "No backups found yet.":
        return history[0]
    return "No backups found yet."


def build_integration_snapshot(config_manager) -> IntegrationSnapshot:
    platform = validate_all_paths(load_platform_config(config_manager))
    platform_status = platform.get("validation_status", HEALTH_WARN)
    platform_message = f"Last validated: {platform.get('last_validated', 'Never')}"

    inv_status, inv_message = _inventory_status(config_manager)

    advertising = normalize_advertising(load_advertising_bundle(config_manager))
    website = normalize_website(load_website_bundle(config_manager))

    alerts: list[str] = []
    if platform_status == HEALTH_ERROR:
        alerts.append("One or more platform paths need attention.")
    if inv_status != HEALTH_OK:
        alerts.append(inv_message)

    for line in advertising_lines(advertising, config_manager):
        if line.startswith("• "):
            alerts.append(f"Advertising: {line[2:]}")

    for line in website_lines(website, config_manager):
        if line.startswith("• "):
            alerts.append(f"Website: {line[2:]}")

    if not alerts:
        alerts.append("No active alerts. Studio development build is ready.")

    module_lines = [
        "Module Overview",
        "",
        f"Platform: {platform_status.upper()} — {platform_message}",
        f"Inventory: {inv_status.upper()} — {inv_message}",
        f"Schedule: {_schedule_status(config_manager)}",
        f"Backup: {_backup_status(config_manager)}",
        "",
        "Advertising:",
        *advertising_lines(advertising, config_manager),
        "",
        "Website & Audience:",
        *website_lines(website, config_manager),
    ]

    return IntegrationSnapshot(
        platform_status=platform_status,
        platform_message=platform_message,
        inventory_status=inv_status,
        inventory_message=inv_message,
        advertising_summary=advertising_lines(advertising, config_manager)[0],
        website_summary=website_lines(website, config_manager)[0],
        schedule_summary=_schedule_status(config_manager),
        backup_summary=_backup_status(config_manager),
        alerts=alerts,
        module_lines=module_lines,
    )

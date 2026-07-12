"""Station Manager snapshot aggregation and health activity parsing."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.automation_model import _collect_activity_log
from app.core.dashboard_model import DashboardSnapshot, StatusLight, build_dashboard_snapshot
from app.core.health_constants import HEALTH_ERROR, HEALTH_OK, HEALTH_WARN
from app.core.paths import automation_logs_dir, logs_dir
from app.core.platform_manager import automation_module_dir, platform_path
from app.core.station_data import inventory_reports_dir, load_station_info
from app.core.system_status import build_live_system_status, service_lookup

logger = logging.getLogger("moplace.studio.station_manager")

ERROR_PATTERN = re.compile(r"\b(error|failed|failure|exception|traceback)\b", re.IGNORECASE)
SUCCESS_PATTERN = re.compile(
    r"\b(success|completed|finished|saved|started|refreshed|ok)\b",
    re.IGNORECASE,
)


@dataclass
class StationManagerSnapshot:
    clock: str = ""
    clock_date: str = ""
    last_refreshed: str = ""
    on_air_status: str = "—"
    current_host: str = "—"
    current_format: str = "—"
    now_playing: str = "—"
    next_event: str = "—"
    last_inventory_scan: str = "No inventory scan found"
    alerts: list[str] = field(default_factory=list)
    service_cards: list[StatusLight] = field(default_factory=list)
    recent_errors: list[str] = field(default_factory=list)
    recent_successes: list[str] = field(default_factory=list)


def _website_status(config_manager=None) -> StatusLight:
    folder = automation_module_dir("Website", config_manager)
    platform_website = platform_path("website", config_manager)
    for path in (folder, platform_website):
        if path.exists():
            files = list(path.glob("*"))
            if files:
                return StatusLight("Website", HEALTH_OK, f"Content folder ready ({len(files)} item(s))")
            return StatusLight("Website", HEALTH_WARN, "Folder exists but no content files yet")
    return StatusLight("Website", HEALTH_WARN, "Website folder not found")


def _read_inventory_scan(config_manager=None) -> str:
    reports_dir = inventory_reports_dir(config_manager)
    inventory_file = reports_dir / "Inventory.json"
    if not inventory_file.exists():
        return "No inventory scan found"

    try:
        with inventory_file.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        scanned_at = data.get("scanned_at", "")
        status = data.get("status", "unknown")
        office_pc = data.get("office_pc", "")
        if scanned_at:
            host = f" on {office_pc}" if office_pc else ""
            return f"{scanned_at}{host} · status: {status}"
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to read inventory scan: %s", exc)
        return "Inventory report found but could not be read"
    return "Inventory report found"


def _collect_log_lines(sources: list[Path], limit: int = 40) -> list[str]:
    lines: list[str] = []
    for source in sources:
        if not source.exists():
            continue
        try:
            content = source.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for line in reversed(content):
            text = line.strip()
            if text:
                lines.append(text)
            if len(lines) >= limit:
                return lines
    return lines


def _split_activity(lines: list[str]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    successes: list[str] = []
    for line in lines:
        if ERROR_PATTERN.search(line):
            errors.append(line[:120])
        elif SUCCESS_PATTERN.search(line):
            successes.append(line[:120])
        if len(errors) >= 8 and len(successes) >= 8:
            break
    return errors[:8], successes[:8]


def _build_alerts(service_cards: list[StatusLight], dashboard: DashboardSnapshot) -> list[str]:
    alerts: list[str] = []
    for card in service_cards:
        if card.status == HEALTH_ERROR:
            alerts.append(f"{card.name} needs attention: {card.detail}")
        elif card.status == HEALTH_WARN and card.name in {"RadioDJ", "LiveDJ", "News", "Requests", "Internet"}:
            alerts.append(f"{card.name} warning: {card.detail}")

    if dashboard.on_air_personality.startswith("Off air"):
        alerts.append("No scheduled show is on the air right now.")

    if not alerts:
        alerts.append("No active alerts. All monitored services look normal.")
    return alerts


def _service_tuple(service) -> tuple[str, str]:
    if not service:
        return HEALTH_WARN, "Not monitored"
    return service.status, service.detail


def build_station_manager_snapshot(config_manager) -> StationManagerSnapshot:
    settings = config_manager.load("settings", {})
    dashboard = build_dashboard_snapshot(config_manager)
    live_status = build_live_system_status(settings, force_refresh=True)
    now = datetime.now()

    current = dashboard.current_event
    if current.show_name != "—":
        on_air_status = "On Air"
        next_event = "—"
        if dashboard.upcoming_events:
            event = dashboard.upcoming_events[0]
            next_event = (
                f"{event.show_name} · {event.personality} · "
                f"{event.day} {event.start_time}–{event.end_time}"
            )
    else:
        on_air_status = "Off Air"
        next_event = "No upcoming scheduled event"

    service_cards = [
        StatusLight("RadioDJ", *_service_tuple(service_lookup(live_status, "RadioDJ"))),
        StatusLight("Voicebox", *_service_tuple(service_lookup(live_status, "Voicebox"))),
        StatusLight("LiveDJ", *_service_tuple(service_lookup(live_status, "LiveDJ Watcher"))),
        StatusLight("News", *_service_tuple(service_lookup(live_status, "News Tasks"))),
        StatusLight("Requests", *_service_tuple(service_lookup(live_status, "Request Watcher"))),
        _website_status(config_manager),
        StatusLight("Internet", *_service_tuple(service_lookup(live_status, "Internet"))),
    ]

    log_sources = [
        logs_dir() / "studio.log",
        automation_logs_dir() / "automation.log",
        platform_path("logs", config_manager) / "studio.log",
    ]
    activity = _collect_activity_log(limit=24) or _collect_log_lines(log_sources, limit=24)
    recent_errors, recent_successes = _split_activity(activity)

    station_info = load_station_info(config_manager, settings)
    on_air_label = on_air_status
    if on_air_status == "On Air" and station_info.get("station_name"):
        on_air_label = f"On Air — {station_info['station_name']}"

    return StationManagerSnapshot(
        clock=now.strftime("%I:%M:%S %p"),
        clock_date=now.strftime("%A, %B %d, %Y"),
        last_refreshed=now.strftime("%I:%M:%S %p"),
        on_air_status=on_air_label,
        current_host=dashboard.on_air_personality,
        current_format=dashboard.music_format,
        now_playing=dashboard.now_playing,
        next_event=next_event,
        last_inventory_scan=_read_inventory_scan(config_manager),
        alerts=_build_alerts(service_cards, dashboard),
        service_cards=service_cards,
        recent_errors=recent_errors or ["No recent errors logged."],
        recent_successes=recent_successes or ["No recent successful jobs logged."],
    )

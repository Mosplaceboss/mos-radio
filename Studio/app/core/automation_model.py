"""Read-only automation monitoring and health aggregation."""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.health_constants import HEALTH_ERROR, HEALTH_OK, HEALTH_WARN
from app.core.hidden_process import NETWORK_TIMEOUT
from app.core.paths import automation_logs_dir, automation_root, config_dir, logs_dir, studio_root
from app.core.personality_model import normalize_personalities_data
from app.core.requests_model import normalize_requests_data
from app.core.schedule_model import DAYS, normalize_schedule_data, time_to_minutes
from app.core.voice_model import normalize_voice_library_data

MODULE_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "id": "livedj",
        "name": "LiveDJ",
        "folder": "LiveDJ",
        "schedule_source": "Studio/config/schedule.json",
        "config_files": ("personalities.json", "voice_library.json", "schedule.json"),
        "log_name": "livedj.log",
    },
    {
        "id": "news",
        "name": "News",
        "folder": "News",
        "schedule_source": "Studio/config/schedule.json",
        "config_files": ("schedule.json",),
        "log_name": "news.log",
    },
    {
        "id": "requests",
        "name": "Requests",
        "folder": "Requests",
        "schedule_source": "Studio/config/requests.json",
        "config_files": ("requests.json",),
        "log_name": "requests.log",
    },
    {
        "id": "casey",
        "name": "Casey",
        "folder": "Casey",
        "schedule_source": "Studio/config/schedule.json",
        "config_files": ("personalities.json", "voice_library.json"),
        "log_name": "casey.log",
    },
    {
        "id": "sunday_morning_blues",
        "name": "Sunday Morning Blues",
        "folder": "SundayMorningBlues",
        "schedule_source": "Studio/config/schedule.json",
        "config_files": ("schedule.json",),
        "log_name": "sunday_morning_blues.log",
    },
    {
        "id": "future_modules",
        "name": "Future Modules",
        "folder": "FutureModules",
        "schedule_source": "Studio/config/automation.json",
        "config_files": ("automation.json",),
        "log_name": "future_modules.log",
    },
)


@dataclass
class AutomationModuleStatus:
    module_id: str
    name: str
    enabled: bool
    running: bool
    last_run: str
    next_run: str
    schedule_source: str
    configuration_file: str
    log_file: str
    status: str
    version: str
    detail: str
    config_paths: list[str] = field(default_factory=list)


@dataclass
class SystemHealthStatus:
    name: str
    status: str
    detail: str


@dataclass
class AutomationSnapshot:
    modules: list[AutomationModuleStatus] = field(default_factory=list)
    system_health: list[SystemHealthStatus] = field(default_factory=list)
    activity_log: list[str] = field(default_factory=list)
    summary: str = "—"
    healthy_count: int = 0
    warning_count: int = 0
    stopped_count: int = 0


def normalize_automation_data(data: dict[str, Any]) -> dict[str, Any]:
    record = dict(data)
    modules = record.setdefault("modules", {})
    for definition in MODULE_DEFINITIONS:
        modules.setdefault(definition["id"], {"enabled": False, "version": "planned"})
    return record


def _module_log_path(definition: dict[str, Any]) -> Path:
    engine_log = automation_root() / definition["folder"] / definition["log_name"]
    if engine_log.exists():
        return engine_log
    return automation_logs_dir() / definition["log_name"]


def _last_log_line(path: Path) -> str:
    if not path.exists():
        return "Never"
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        for line in reversed(lines):
            if line.strip():
                return line.strip()[:80]
    except OSError:
        return "Unreadable"
    return "Never"


def _last_log_timestamp(path: Path) -> str:
    if not path.exists():
        return "Never"
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        for line in reversed(lines):
            if line.strip():
                return line[:19] if len(line) >= 19 else line.strip()
    except OSError:
        return "Never"
    return "Never"


def _next_schedule_run(slots: list[dict[str, Any]]) -> str:
    now = datetime.now()
    day = DAYS[now.weekday()]
    minutes = now.hour * 60 + now.minute
    day_index = DAYS.index(day)
    upcoming: list[tuple[int, dict[str, Any]]] = []
    for slot in slots:
        slot_day = slot.get("day", "").lower()
        if slot_day not in DAYS:
            continue
        try:
            start = time_to_minutes(slot.get("start_time", "00:00"))
        except ValueError:
            continue
        slot_day_index = DAYS.index(slot_day)
        offset = (slot_day_index - day_index) % 7
        if offset == 0 and start <= minutes:
            continue
        upcoming.append((offset * 24 * 60 + start, slot))
    if not upcoming:
        return "No upcoming schedule"
    upcoming.sort(key=lambda item: item[0])
    slot = upcoming[0][1]
    return f"{slot.get('day', '').title()} {slot.get('start_time', '')} · {slot.get('show_name', 'Show')}"


def _module_running(folder: Path) -> bool:
    if not folder.exists():
        return False
    for marker in ("running.lock", "engine.pid", ".running"):
        if (folder / marker).exists():
            return True
    return False


def _module_health(
    definition: dict[str, Any],
    enabled: bool,
    config_paths: list[Path],
) -> tuple[str, str]:
    folder = automation_root() / definition["folder"]
    if not enabled:
        return HEALTH_WARN, "Disabled in Studio automation registry"
    if definition["id"] in {"future_modules", "casey", "sunday_morning_blues"}:
        if not folder.exists():
            return HEALTH_WARN, "Planned module · engine folder not present"
    missing_configs = [path.name for path in config_paths if not path.exists()]
    if missing_configs:
        return HEALTH_ERROR, f"Missing config: {', '.join(missing_configs)}"
    if not folder.exists():
        return HEALTH_WARN, "External engine folder missing"
    return HEALTH_OK, "Configuration available · read-only monitoring"


def build_module_status(
    definition: dict[str, Any],
    registry: dict[str, Any],
    schedule_slots: list[dict[str, Any]],
) -> AutomationModuleStatus:
    module_id = definition["id"]
    settings = registry.get(module_id, {})
    enabled = settings.get("enabled", False)
    version = settings.get("version", "unknown")
    config_paths = [config_dir() / name for name in definition["config_files"]]
    log_path = _module_log_path(definition)
    folder = automation_root() / definition["folder"]
    status, detail = _module_health(definition, enabled, config_paths)
    running = _module_running(folder)
    if enabled and not running:
        detail = f"{detail} · Stopped"

    next_run = "—"
    if "schedule.json" in definition["config_files"]:
        next_run = _next_schedule_run(schedule_slots)
    elif "requests.json" in definition["config_files"]:
        next_run = "Follows request hours and mode"

    return AutomationModuleStatus(
        module_id=module_id,
        name=definition["name"],
        enabled=enabled,
        running=running,
        last_run=_last_log_timestamp(log_path),
        next_run=next_run,
        schedule_source=definition["schedule_source"],
        configuration_file=", ".join(str(path) for path in config_paths),
        log_file=str(log_path),
        status=status,
        version=version,
        detail=detail,
        config_paths=[str(path) for path in config_paths],
    )


def _internet_connected() -> tuple[str, str]:
    try:
        with urllib.request.urlopen("https://example.com", timeout=1.0) as response:
            if 200 <= response.status < 500:
                return HEALTH_OK, "Internet reachable"
    except (OSError, urllib.error.URLError, TimeoutError):
        pass
    return HEALTH_WARN, "Internet not verified"


def build_system_health(config_manager) -> list[SystemHealthStatus]:
    voices = normalize_voice_library_data(config_manager.load("voice_library", {"voices": []})).get("voices", [])
    personalities = normalize_personalities_data(config_manager.load("personalities", {"personalities": []})).get(
        "personalities", []
    )
    requests = normalize_requests_data(config_manager.load("requests", {}))

    voicebox_ok = any(voice.get("active", True) and voice.get("voicebox_id") for voice in voices)
    radiodj_ok = any(personality.get("radiodj_cart_id") for personality in personalities)
    queue_ok = requests.get("request_mode") != "disabled" and requests.get("max_active_queue", 0) > 0

    internet_status, internet_detail = _internet_connected()

    return [
        SystemHealthStatus(
            "Voicebox Connected",
            HEALTH_OK if voicebox_ok else HEALTH_WARN,
            "Active Voicebox voices configured" if voicebox_ok else "No active Voicebox voices",
        ),
        SystemHealthStatus(
            "RadioDJ Connected",
            HEALTH_OK if radiodj_ok else HEALTH_WARN,
            "RadioDJ cart IDs present" if radiodj_ok else "No RadioDJ cart IDs configured",
        ),
        SystemHealthStatus(
            "Database Connected",
            HEALTH_WARN,
            "Not monitored (read-only)",
        ),
        SystemHealthStatus(
            "RSS Connected",
            HEALTH_WARN,
            "News engine external (read-only)",
        ),
        SystemHealthStatus("Internet Connected", internet_status, internet_detail),
        SystemHealthStatus(
            "Queue Healthy",
            HEALTH_OK if queue_ok else HEALTH_WARN,
            "Request queue configured" if queue_ok else "Requests disabled or queue not configured",
        ),
        SystemHealthStatus(
            "Audio Output Healthy",
            HEALTH_WARN,
            "Not monitored (read-only)",
        ),
    ]


def _collect_activity_log(limit: int = 20) -> list[str]:
    sources = [logs_dir() / "studio.log", automation_logs_dir() / "automation.log"]
    for definition in MODULE_DEFINITIONS:
        sources.append(_module_log_path(definition))

    lines: list[str] = []
    keywords = ("start", "finish", "error", "warn", "script", "queue", "generated", "insert")
    for source in sources:
        if not source.exists():
            continue
        try:
            for line in source.read_text(encoding="utf-8", errors="ignore").splitlines():
                lower = line.lower()
                if any(keyword in lower for keyword in keywords) or "INFO" in line or "ERROR" in line:
                    lines.append(line.strip())
        except OSError:
            continue

    if not lines:
        return ["No automation activity logged yet."]
    return lines[-limit:]


def build_automation_summary(modules: list[AutomationModuleStatus]) -> tuple[str, int, int, int]:
    total = len(modules)
    healthy = sum(1 for module in modules if module.status == HEALTH_OK and module.enabled)
    warnings = sum(1 for module in modules if module.status == HEALTH_WARN)
    stopped = sum(1 for module in modules if module.enabled and not module.running)

    if warnings == 0 and stopped == 0:
        return f"{healthy}/{total} automations healthy", healthy, warnings, stopped
    if stopped > 0 and warnings > 0:
        return f"{stopped} stopped · {warnings} warning(s)", healthy, warnings, stopped
    if stopped > 0:
        return f"{stopped} stopped", healthy, warnings, stopped
    return f"{warnings} warning(s)", healthy, warnings, stopped


def build_automation_snapshot(config_manager) -> AutomationSnapshot:
    registry = normalize_automation_data(config_manager.load("automation", {"modules": {}})).get("modules", {})
    personalities = normalize_personalities_data(config_manager.load("personalities", {"personalities": []}))
    schedule = normalize_schedule_data(
        config_manager.load("schedule", {"slots": []}),
        [item["id"] for item in personalities.get("personalities", [])],
    )
    slots = schedule.get("slots", [])

    modules = [build_module_status(defn, registry, slots) for defn in MODULE_DEFINITIONS]
    summary, healthy, warnings, stopped = build_automation_summary(modules)

    return AutomationSnapshot(
        modules=modules,
        system_health=build_system_health(config_manager),
        activity_log=_collect_activity_log(),
        summary=summary,
        healthy_count=healthy,
        warning_count=warnings,
        stopped_count=stopped,
    )


def append_automation_log(message: str) -> None:
    log_file = automation_logs_dir() / "automation.log"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with log_file.open("a", encoding="utf-8") as handle:
        handle.write(f"{timestamp} | INFO | automation | {message}\n")

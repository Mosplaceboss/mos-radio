"""Live system process and service detection."""

from __future__ import annotations

import json
import logging
import socket
import time
import urllib.error
import urllib.request
from app.core.hidden_process import NETWORK_TIMEOUT, clear_process_cache, list_windows_process_lines
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app.core.automation_model import MODULE_DEFINITIONS, _module_log_path, _last_log_timestamp
from app.core.health_constants import HEALTH_ERROR, HEALTH_OK, HEALTH_WARN
from app.core.integration_settings import (
    livedj_live_paths,
    news_live_paths,
    normalize_integration_settings,
    requests_live_paths,
    resolve_integration_path,
)
from app.core.platform_manager import automation_module_dir

logger = logging.getLogger("moplace.studio.system_status")

_STATUS_CACHE: LiveSystemStatus | None = None
_STATUS_CACHE_MONO: float = 0.0
STATUS_CACHE_TTL_SECONDS = 30.0
FAST_NETWORK_TIMEOUT = 1.0


def clear_system_status_cache() -> None:
    global _STATUS_CACHE, _STATUS_CACHE_MONO
    _STATUS_CACHE = None
    _STATUS_CACHE_MONO = 0.0


@dataclass
class ServiceStatus:
    name: str
    status: str
    detail: str
    running: bool = False


@dataclass
class LiveSystemStatus:
    services: list[ServiceStatus] = field(default_factory=list)
    last_refreshed: str = ""


def _process_running(
    image_name: str,
    match_text: str = "",
    process_lines: list[str] | None = None,
) -> tuple[bool, str]:
    lines = process_lines if process_lines is not None else list_windows_process_lines()
    if not lines:
        return False, "Process check unavailable"
    image_lower = image_name.lower()
    match_lower = match_text.lower()
    for line in lines:
        parts = [part.strip('"') for part in line.split('","')]
        if not parts:
            continue
        proc_name = parts[0].lower()
        if proc_name != image_lower and not proc_name.endswith(image_lower):
            continue
        if match_lower and match_lower not in line.lower():
            continue
        return True, f"{parts[0]} detected"
    return False, f"{image_name} not running"


def _lock_file_running(folder_name: str) -> bool:
    folder = automation_module_dir(folder_name)
    if not folder.exists():
        return False
    for marker in ("running.lock", "engine.pid", ".running"):
        if (folder / marker).exists():
            return True
    return False


def _voicebox_api_ok(
    api_url: str,
    health_path: str,
    *,
    timeout: float = NETWORK_TIMEOUT,
    max_candidates: int | None = None,
) -> tuple[str, str, bool]:
    base = api_url.rstrip("/")
    path = health_path if health_path.startswith("/") else f"/{health_path}"
    candidates = (f"{base}{path}", base, f"{base}/health", f"{base}/v1/health")
    if max_candidates is not None:
        candidates = candidates[:max_candidates]
    for url in candidates:
        try:
            with urllib.request.urlopen(url, timeout=timeout) as response:
                if 200 <= response.status < 500:
                    return HEALTH_OK, f"API responding ({response.status})", True
        except (OSError, urllib.error.URLError, TimeoutError):
            continue
    try:
        host = urlparse(base).hostname or "127.0.0.1"
        port = urlparse(base).port or (7860 if "7860" in base else 80)
        with socket.create_connection((host, port), timeout=timeout):
            return HEALTH_WARN, "Port open but API health endpoint not verified", True
    except OSError:
        pass
    return HEALTH_WARN, "Voicebox API not responding", False


def _internet_connected(*, timeout: float = NETWORK_TIMEOUT) -> tuple[str, str]:
    try:
        with urllib.request.urlopen("https://example.com", timeout=timeout) as response:
            if 200 <= response.status < 500:
                return HEALTH_OK, "Internet reachable"
    except (OSError, urllib.error.URLError, TimeoutError):
        pass
    return HEALTH_WARN, "Internet not verified"


def _news_task_status(news_config_path: Path) -> tuple[str, str, bool]:
    if not news_config_path.exists():
        return HEALTH_WARN, "News config not found on live path", False
    try:
        with news_config_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        enabled = data.get("enabled", True)
        feeds = [feed for feed in data.get("rss_feeds", []) if feed.get("enabled", True)]
        last_run = data.get("last_successful_run", "Not recorded")
        if not enabled:
            return HEALTH_WARN, "News tasks disabled", False
        if not feeds:
            return HEALTH_WARN, "No enabled RSS feeds", False
        running = _lock_file_running("News")
        detail = f"{len(feeds)} feed(s) · last run: {last_run}"
        if running:
            return HEALTH_OK, f"Tasks active · {detail}", True
        return HEALTH_WARN, f"Tasks idle/stopped · {detail}", False
    except (OSError, json.JSONDecodeError) as exc:
        return HEALTH_ERROR, f"News config error: {exc}", False


def build_live_system_status(settings: dict[str, Any], *, force_refresh: bool = False) -> LiveSystemStatus:
    global _STATUS_CACHE, _STATUS_CACHE_MONO

    now = time.monotonic()
    if not force_refresh and _STATUS_CACHE is not None and (now - _STATUS_CACHE_MONO) < STATUS_CACHE_TTL_SECONDS:
        return _STATUS_CACHE

    if force_refresh:
        clear_process_cache()
        process_lines = list_windows_process_lines(force_refresh=True)
        network_timeout = NETWORK_TIMEOUT
        voicebox_candidates = None
    else:
        process_lines = list_windows_process_lines(force_refresh=False)
        network_timeout = FAST_NETWORK_TIMEOUT
        voicebox_candidates = 2

    integration = normalize_integration_settings(settings)
    livedj_paths = livedj_live_paths(integration)
    request_paths = requests_live_paths(integration)
    news_paths = news_live_paths(integration)

    radiodj_executable = integration.get("radiodj_executable", "").strip()
    if radiodj_executable:
        exe_path = Path(radiodj_executable)
        if exe_path.exists():
            process_name = exe_path.name
            radiodj_running, radiodj_detail = _process_running(process_name, process_lines=process_lines)
            radiodj_status = HEALTH_OK if radiodj_running else HEALTH_WARN
            if not radiodj_running:
                radiodj_detail = f"Executable found but {process_name} is not running"
        else:
            radiodj_running = False
            radiodj_status = HEALTH_ERROR
            radiodj_detail = f"Executable not found: {radiodj_executable}"
    else:
        radiodj_running, radiodj_detail = _process_running(
            integration["radiodj_process"], process_lines=process_lines
        )
        radiodj_status = HEALTH_OK if radiodj_running else HEALTH_WARN

    voicebox_status, voicebox_detail, voicebox_running = _voicebox_api_ok(
        integration["voicebox_api_url"],
        integration["voicebox_health_path"],
        timeout=network_timeout,
        max_candidates=voicebox_candidates,
    )

    livedj_lock = _lock_file_running("LiveDJ")
    livedj_proc, livedj_proc_detail = _process_running(
        integration["livedj_process"],
        integration["livedj_process_match"],
        process_lines=process_lines,
    )
    livedj_running = livedj_lock or livedj_proc
    if livedj_running:
        livedj_status = HEALTH_OK
        livedj_detail = "Watcher running" if livedj_lock else livedj_proc_detail
    elif any(path.exists() for path in (livedj_paths["schedule"], livedj_paths["personalities"])):
        livedj_status = HEALTH_WARN
        livedj_detail = "Config present · watcher not running"
    else:
        livedj_status = HEALTH_WARN
        livedj_detail = "Watcher not detected"

    request_lock = _lock_file_running("Requests")
    request_proc, request_proc_detail = _process_running(
        integration["request_watcher_process"],
        integration["request_watcher_match"],
        process_lines=process_lines,
    )
    request_running = request_lock or request_proc
    if request_running:
        request_status = HEALTH_OK
        request_detail = "Watcher running" if request_lock else request_proc_detail
    elif request_paths["config"].exists():
        request_status = HEALTH_WARN
        request_detail = "Config present · watcher not running"
    else:
        request_status = HEALTH_WARN
        request_detail = "Watcher not detected"

    news_status, news_detail, news_running = _news_task_status(news_paths["config"])
    internet_status, internet_detail = _internet_connected(timeout=network_timeout)

    services = [
        ServiceStatus("RadioDJ", radiodj_status, radiodj_detail, radiodj_running),
        ServiceStatus("Voicebox", voicebox_status, voicebox_detail, voicebox_running),
        ServiceStatus("LiveDJ Watcher", livedj_status, livedj_detail, livedj_running),
        ServiceStatus("News Tasks", news_status, news_detail, news_running),
        ServiceStatus("Request Watcher", request_status, request_detail, request_running),
        ServiceStatus("Internet", internet_status, internet_detail, internet_status == HEALTH_OK),
    ]

    result = LiveSystemStatus(services=services, last_refreshed=datetime.now().strftime("%I:%M:%S %p"))
    _STATUS_CACHE = result
    _STATUS_CACHE_MONO = time.monotonic()
    return result


def service_lookup(status: LiveSystemStatus, name: str) -> ServiceStatus | None:
    for service in status.services:
        if service.name == name:
            return service
    return None


def last_run_for_module(folder: str, log_name: str) -> str:
    definition = next((item for item in MODULE_DEFINITIONS if item["folder"] == folder), None)
    if definition:
        return _last_log_timestamp(_module_log_path(definition))
    return _last_log_timestamp(automation_module_dir(folder) / log_name)

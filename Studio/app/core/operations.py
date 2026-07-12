"""Confirmed operational controls for external automation engines."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from app.core.automation_model import append_automation_log
from app.core.hidden_process import popen_hidden
from app.core.integration_settings import livedj_live_paths, news_live_paths, requests_live_paths
from app.core.live_connector import resolve_engine_script
from app.core.system_status import build_live_system_status

logger = logging.getLogger("moplace.studio.operations")


def _run_script(script_path: Path, action: str) -> tuple[bool, str]:
    if not script_path.exists():
        return False, f"Script not found: {script_path}"
    try:
        if sys.platform == "win32":
            popen_hidden(["cmd", "/c", str(script_path)], cwd=script_path.parent)
        else:
            popen_hidden([str(script_path)], cwd=script_path.parent)
        append_automation_log(f"{action} launched via {script_path.name}")
        return True, f"{action} started using {script_path.name}"
    except OSError as exc:
        logger.error("Failed to launch %s: %s", script_path, exc)
        return False, f"Failed to start {action}: {exc}"


def start_request_watcher(integration: dict) -> tuple[bool, str]:
    paths = requests_live_paths(integration)
    script = resolve_engine_script(integration, "requests_start", paths["start_script"])
    return _run_script(script, "Request Watcher")


def restart_request_watcher(integration: dict) -> tuple[bool, str]:
    paths = requests_live_paths(integration)
    script = resolve_engine_script(integration, "requests_restart", paths["restart_script"])
    return _run_script(script, "Request Watcher restart")


def start_livedj_watcher(integration: dict) -> tuple[bool, str]:
    paths = livedj_live_paths(integration)
    script = resolve_engine_script(integration, "livedj_start", paths["start_script"])
    return _run_script(script, "LiveDJ Watcher")


def restart_livedj_watcher(integration: dict) -> tuple[bool, str]:
    paths = livedj_live_paths(integration)
    script = resolve_engine_script(integration, "livedj_restart", paths["restart_script"])
    return _run_script(script, "LiveDJ Watcher restart")


def run_news_now(integration: dict) -> tuple[bool, str]:
    paths = news_live_paths(integration)
    script = resolve_engine_script(integration, "news_run_now", paths["run_now_script"])
    return _run_script(script, "News run now")


def refresh_all_statuses(settings: dict) -> tuple[bool, str]:
    status = build_live_system_status(settings)
    running = sum(1 for service in status.services if service.running)
    append_automation_log(f"Status refresh: {running}/{len(status.services)} services running")
    return True, f"Refreshed at {status.last_refreshed} · {running} service(s) running"

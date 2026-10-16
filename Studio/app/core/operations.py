"""Confirmed operational controls for external automation engines."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from app.core.automation_model import append_automation_log
from app.core.hidden_process import popen_hidden
from app.core.integration_settings import livedj_live_paths, news_live_paths, requests_live_paths
from app.core.live_connector import resolve_engine_script
from app.core.system_status import build_live_system_status, clear_system_status_cache

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
    """Install news launcher files, write bulletin.txt, then run the local engine hook."""
    paths = news_live_paths(integration)
    news_dir = Path(paths["run_now_script"]).parent
    from app.core.news_runtime import ensure_news_runtime_scripts

    ok, message = ensure_news_runtime_scripts(news_dir)
    if not ok:
        append_automation_log(f"News runtime install failed: {message}")
        return False, message
    append_automation_log(message)

    try:
        from app.core.news_bulletin import next_air_label, write_bulletin

        bulletin_path = write_bulletin(air=next_air_label(), fetch=True, news_dir=news_dir)
        append_automation_log(f"Wrote news bulletin {bulletin_path}")
    except Exception as exc:
        logger.error("News bulletin build failed: %s", exc)
        append_automation_log(f"News bulletin build failed: {exc}")
        return False, f"News bulletin build failed: {exc}"

    engine = news_dir / "engine.local.cmd"
    if engine.exists():
        return _run_script(engine, "News engine")

    # No local engine hook yet — bulletin is ready for the next scheduled speak.
    append_automation_log("Wrote bulletin.txt; engine.local.cmd is not beside the news folder")
    return True, "News bulletin written. engine.local.cmd is not installed yet (local station hook only)."


def refresh_all_statuses(settings: dict) -> tuple[bool, str]:
    clear_system_status_cache()
    status = build_live_system_status(settings, force_refresh=True)
    running = sum(1 for service in status.services if service.running)
    append_automation_log(f"Status refresh: {running}/{len(status.services)} services running")
    return True, f"Refreshed at {status.last_refreshed} · {running} service(s) running"

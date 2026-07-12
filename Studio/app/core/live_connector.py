"""Load local live-system overrides and connection testing."""

from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.health_constants import HEALTH_OK
from app.core.integration_settings import (
    base_integration_settings,
    livedj_live_paths,
    news_live_paths,
    requests_live_paths,
    studio_config_path,
)
from app.core.livedj_integration import import_livedj_from_live
from app.core.paths import config_dir, studio_root
from app.core.publish_manager import import_news_from_live, import_requests_from_live
from app.core.system_status import build_live_system_status

logger = logging.getLogger("moplace.studio.live_connector")

LOCAL_FILE = "integration.local.json"


@dataclass
class ConnectionResult:
    name: str
    ok: bool
    detail: str


def local_integration_path() -> Path:
    return config_dir() / LOCAL_FILE


def load_local_integration() -> dict[str, Any]:
    path = local_integration_path()
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to load %s: %s", path, exc)
        return {}


def save_local_integration(data: dict[str, Any]) -> None:
    path = local_integration_path()
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")


def ensure_local_integration_template() -> Path:
    path = local_integration_path()
    if path.exists():
        return path
    example = studio_root() / "config" / "integration.local.json.example"
    if example.exists():
        shutil.copy2(example, path)
        data = load_local_integration()
        data["enabled"] = True
        data.setdefault("live_paths", {})
        data["live_paths"].setdefault("livedj", {})
        data["live_paths"]["livedj"].update(
            {
                "personalities": "Automation/LiveDJ/personalities.json",
                "schedule": "Automation/LiveDJ/schedule.json",
                "voice_library": "Automation/LiveDJ/voice_library.json",
            }
        )
        data["live_paths"].setdefault("requests", {})
        data["live_paths"]["requests"]["config"] = "Automation/Requests/requests.json"
        data["live_paths"].setdefault("news", {})
        data["live_paths"]["news"]["config"] = "Automation/News/news.json"
        data.setdefault("engine_scripts", {})
        data["engine_scripts"].update(
            {
                "livedj_start": "Automation/LiveDJ/start_watcher.bat",
                "livedj_restart": "Automation/LiveDJ/restart_watcher.bat",
                "requests_start": "Automation/Requests/start_watcher.bat",
                "requests_restart": "Automation/Requests/restart_watcher.bat",
                "news_run_now": "Automation/News/run_news_now.bat",
            }
        )
        save_local_integration(data)
    else:
        save_local_integration({"enabled": False})
    return path


def merge_integration_settings(settings: dict[str, Any]) -> dict[str, Any]:
    integration = base_integration_settings(settings)
    local = load_local_integration()
    if not local.get("enabled"):
        return integration

    local_paths = local.get("live_paths", {})
    for target, paths in local_paths.items():
        if not isinstance(paths, dict) or target not in integration["live_paths"]:
            continue
        for key, value in paths.items():
            if isinstance(value, str) and value.strip():
                integration["live_paths"][target][key] = value.strip()

    engine_scripts = local.get("engine_scripts", {})
    if isinstance(engine_scripts, dict):
        integration["engine_scripts"] = {
            key: value.strip()
            for key, value in engine_scripts.items()
            if isinstance(value, str) and value.strip()
        }

    for key in ("radiodj_process", "voicebox_api_url", "voicebox_health_path", "now_playing_file"):
        value = local.get(key)
        if isinstance(value, str) and value.strip():
            integration[key] = value.strip()

    return integration


def now_playing_path(settings: dict[str, Any]) -> Path | None:
    integration = merge_integration_settings(settings)
    configured = integration.get("now_playing_file", "").strip()
    if configured:
        return Path(configured)
    local = load_local_integration()
    local_path = local.get("now_playing_file", "").strip()
    if local_path:
        return Path(local_path)
    return None


def resolve_engine_script(integration: dict[str, Any], key: str, fallback: Path) -> Path:
    scripts = integration.get("engine_scripts", {})
    configured = scripts.get(key, "").strip() if isinstance(scripts, dict) else ""
    if configured:
        return Path(configured)
    return fallback


def test_path(path: Path, label: str) -> ConnectionResult:
    if not str(path):
        return ConnectionResult(label, False, "Path not configured")
    if path.exists():
        return ConnectionResult(label, True, f"Found: {path}")
    return ConnectionResult(label, False, f"Missing: {path}")


def test_all_connections(settings: dict[str, Any]) -> list[ConnectionResult]:
    integration = merge_integration_settings(settings)
    livedj = livedj_live_paths(integration)
    requests = requests_live_paths(integration)
    news = news_live_paths(integration)

    results = [
        test_path(livedj["personalities"], "LiveDJ personalities"),
        test_path(livedj["schedule"], "LiveDJ schedule"),
        test_path(livedj["voice_library"], "LiveDJ voice library"),
        test_path(requests["config"], "Request settings"),
        test_path(news["config"], "News configuration"),
        test_path(resolve_engine_script(integration, "livedj_start", livedj["start_script"]), "LiveDJ start script"),
        test_path(
            resolve_engine_script(integration, "requests_start", requests["start_script"]),
            "Request watcher start script",
        ),
        test_path(resolve_engine_script(integration, "news_run_now", news["run_now_script"]), "News run-now script"),
    ]

    now_playing = now_playing_path(settings)
    if now_playing:
        results.append(test_path(now_playing, "Now playing file"))

    live_status = build_live_system_status(settings)
    for service in live_status.services:
        results.append(
            ConnectionResult(
                service.name,
                service.status == HEALTH_OK,
                service.detail,
            )
        )
    return results


def import_all_from_live(settings: dict[str, Any]) -> tuple[bool, str]:
    integration = merge_integration_settings(settings)
    messages: list[str] = []

    ok, message, imported = import_livedj_from_live(integration)
    messages.append(message)
    livedj_ok = ok

    ok, message = import_requests_from_live(integration)
    messages.append(message)
    requests_ok = ok

    ok, message = import_news_from_live(integration)
    messages.append(message)
    news_ok = ok

    overall = livedj_ok or requests_ok or news_ok
    return overall, "\n".join(messages)


def activate_local_integration(paths: dict[str, str], engine_scripts: dict[str, str] | None = None) -> None:
    data = load_local_integration()
    data["enabled"] = True
    data.setdefault("live_paths", {})
    for target, mapping in paths.items():
        if target not in data["live_paths"]:
            data["live_paths"][target] = {}
        data["live_paths"][target].update({key: value for key, value in mapping.items() if value.strip()})
    if engine_scripts:
        data.setdefault("engine_scripts", {})
        data["engine_scripts"].update({key: value for key, value in engine_scripts.items() if value.strip()})
    save_local_integration(data)

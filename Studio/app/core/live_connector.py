"""Load local live-system overrides and connection testing."""

from __future__ import annotations

import json
import logging
import shutil
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.health_constants import HEALTH_ERROR, HEALTH_OK, HEALTH_WARN
from app.core.hidden_process import NETWORK_TIMEOUT, list_windows_process_lines
from app.core.integration_settings import (
    base_integration_settings,
    livedj_live_paths,
    news_live_paths,
    requests_live_paths,
    resolve_integration_path,
    studio_config_path,
)
from app.core.platform_manager import platform_path
from app.core.paths import config_dir, studio_root
from app.core.system_status import _internet_connected, _voicebox_api_ok

logger = logging.getLogger("moplace.studio.live_connector")

LOCAL_FILE = "integration.local.json"

DEFAULT_STATION = {
    "radio_pc": "",
    "livedj_folder": "",
    "news_folder": "",
    "requests_folder": "",
    "radiodj_executable": "",
    "voicebox_api_url": "http://127.0.0.1:7860",
}


@dataclass
class ConnectionResult:
    name: str
    status: str
    message: str

    @property
    def ok(self) -> bool:
        return self.status == HEALTH_OK


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


def load_station_connection() -> dict[str, str]:
    local = load_local_integration()
    station = local.get("station", {})
    if not isinstance(station, dict):
        station = {}
    merged = dict(DEFAULT_STATION)
    for key, value in station.items():
        if key in merged and isinstance(value, str):
            merged[key] = value.strip()
    return merged


def _folder_path(value: str) -> Path:
    text = value.strip()
    if not text:
        return Path()
    path = Path(text)
    if not path.is_absolute():
        return platform_path("platform_root") / path
    return path


def derive_paths_from_station(station: dict[str, str]) -> tuple[dict[str, Any], dict[str, str]]:
    livedj_folder = _folder_path(station.get("livedj_folder", ""))
    news_folder = _folder_path(station.get("news_folder", ""))
    requests_folder = _folder_path(station.get("requests_folder", ""))

    live_paths = {
        "livedj": {
            "personalities": str(livedj_folder / "personalities.json") if livedj_folder else "",
            "schedule": str(livedj_folder / "schedule.json") if livedj_folder else "",
            "voice_library": str(livedj_folder / "voice_library.json") if livedj_folder else "",
            "start_script": str(livedj_folder / "start_watcher.bat") if livedj_folder else "",
            "restart_script": str(livedj_folder / "restart_watcher.bat") if livedj_folder else "",
        },
        "requests": {
            "config": str(requests_folder / "requests.json") if requests_folder else "",
            "start_script": str(requests_folder / "start_watcher.bat") if requests_folder else "",
            "restart_script": str(requests_folder / "restart_watcher.bat") if requests_folder else "",
        },
        "news": {
            "config": str(news_folder / "news.json") if news_folder else "",
            "start_script": str(news_folder / "start_tasks.bat") if news_folder else "",
            "restart_script": str(news_folder / "restart_tasks.bat") if news_folder else "",
            "run_now_script": str(news_folder / "run_news_now.bat") if news_folder else "",
        },
    }
    engine_scripts = {
        "livedj_start": live_paths["livedj"]["start_script"],
        "livedj_restart": live_paths["livedj"]["restart_script"],
        "requests_start": live_paths["requests"]["start_script"],
        "requests_restart": live_paths["requests"]["restart_script"],
        "news_run_now": live_paths["news"]["run_now_script"],
    }
    return live_paths, engine_scripts


def build_local_from_station(station: dict[str, str], *, enabled: bool = True) -> dict[str, Any]:
    live_paths, engine_scripts = derive_paths_from_station(station)
    radiodj_executable = station.get("radiodj_executable", "").strip()
    process_name = Path(radiodj_executable).name if radiodj_executable else "RadioDJ.exe"
    return {
        "enabled": enabled,
        "station": station,
        "radiodj_process": process_name,
        "radiodj_executable": radiodj_executable,
        "voicebox_api_url": station.get("voicebox_api_url", DEFAULT_STATION["voicebox_api_url"]),
        "live_paths": live_paths,
        "engine_scripts": engine_scripts,
    }


def ensure_local_integration_template() -> Path:
    path = local_integration_path()
    if path.exists():
        return path
    example = studio_root() / "config" / "integration.local.json.example"
    if example.exists():
        shutil.copy2(example, path)
    station = {
        "radio_pc": "",
        "livedj_folder": str(platform_path("automation_livedj")),
        "news_folder": str(platform_path("automation_news")),
        "requests_folder": str(platform_path("automation_requests")),
        "radiodj_executable": str(platform_path("radiodj")),
        "voicebox_api_url": "http://127.0.0.1:7860",
    }
    save_local_integration(build_local_from_station(station, enabled=True))
    return path


def merge_integration_settings(settings: dict[str, Any]) -> dict[str, Any]:
    integration = base_integration_settings(settings)
    local = load_local_integration()
    if not local.get("enabled"):
        return integration

    station = local.get("station", {})
    if isinstance(station, dict) and any(station.get(key, "").strip() for key in DEFAULT_STATION):
        derived_paths, derived_scripts = derive_paths_from_station(
            {key: str(station.get(key, "")) for key in DEFAULT_STATION}
        )
        for target, paths in derived_paths.items():
            if target in integration["live_paths"]:
                for key, value in paths.items():
                    if value:
                        integration["live_paths"][target][key] = value
        integration["engine_scripts"] = {key: value for key, value in derived_scripts.items() if value}

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

    for key in ("radiodj_process", "radiodj_executable", "voicebox_api_url", "voicebox_health_path", "now_playing_file"):
        value = local.get(key)
        if isinstance(value, str) and value.strip():
            integration[key] = value.strip()

    if isinstance(station, dict):
        voicebox = station.get("voicebox_api_url", "").strip()
        if voicebox:
            integration["voicebox_api_url"] = voicebox
        radiodj_executable = station.get("radiodj_executable", "").strip()
        if radiodj_executable:
            integration["radiodj_executable"] = radiodj_executable
            integration["radiodj_process"] = Path(radiodj_executable).name

    return integration


def now_playing_path(settings: dict[str, Any]) -> Path | None:
    integration = merge_integration_settings(settings)
    configured = integration.get("now_playing_file", "").strip()
    if configured:
        return Path(configured)
    return None


def resolve_engine_script(integration: dict[str, Any], key: str, fallback: Path) -> Path:
    scripts = integration.get("engine_scripts", {})
    configured = scripts.get(key, "").strip() if isinstance(scripts, dict) else ""
    if configured:
        return Path(configured)
    return fallback


def _test_radio_pc(host: str) -> ConnectionResult:
    if not host.strip():
        return ConnectionResult("Radio PC", HEALTH_WARN, "Radio PC name or IP is not configured yet.")
    previous_timeout = socket.getdefaulttimeout()
    try:
        socket.setdefaulttimeout(NETWORK_TIMEOUT)
        socket.getaddrinfo(host.strip(), None)
        return ConnectionResult("Radio PC", HEALTH_OK, f"Radio PC '{host}' is reachable on the network.")
    except OSError:
        return ConnectionResult(
            "Radio PC",
            HEALTH_WARN,
            f"Could not resolve or reach '{host}'. Check the name/IP or network connection.",
        )
    finally:
        socket.setdefaulttimeout(previous_timeout)


def _test_folder(label: str, folder: Path, required_files: tuple[str, ...]) -> ConnectionResult:
    if not str(folder):
        return ConnectionResult(label, HEALTH_WARN, f"{label} path is not configured yet.")
    if not folder.exists():
        return ConnectionResult(label, HEALTH_ERROR, f"{label} folder was not found: {folder}")
    missing = [name for name in required_files if not (folder / name).exists()]
    if missing:
        return ConnectionResult(
            label,
            HEALTH_WARN,
            f"{label} folder exists but missing: {', '.join(missing)}",
        )
    return ConnectionResult(label, HEALTH_OK, f"{label} folder is connected with required files.")


def _test_radiodj_executable(executable: str) -> ConnectionResult:
    if not executable.strip():
        return ConnectionResult("RadioDJ", HEALTH_WARN, "RadioDJ executable path is not configured yet.")
    path = Path(executable.strip())
    if not path.exists():
        return ConnectionResult("RadioDJ", HEALTH_ERROR, f"RadioDJ executable was not found: {path}")
    process_name = path.name
    lines = list_windows_process_lines(force_refresh=True)
    running = any(process_name.lower() in line.lower() for line in lines)
    if running:
        return ConnectionResult("RadioDJ", HEALTH_OK, f"RadioDJ is running ({process_name}).")
    return ConnectionResult("RadioDJ", HEALTH_WARN, f"RadioDJ executable found but {process_name} is not running.")


def _test_voicebox(api_url: str) -> ConnectionResult:
    if not api_url.strip():
        return ConnectionResult("Voicebox API", HEALTH_WARN, "Voicebox API address is not configured yet.")
    status, detail, _running = _voicebox_api_ok(api_url.strip(), "/")
    return ConnectionResult("Voicebox API", status, detail)


def test_connection_setup(settings: dict[str, Any]) -> list[ConnectionResult]:
    station = load_station_connection()
    local = load_local_integration()
    if isinstance(local.get("station"), dict):
        station.update({key: str(local["station"].get(key, "")).strip() for key in DEFAULT_STATION})

    livedj_folder = _folder_path(station.get("livedj_folder", ""))
    news_folder = _folder_path(station.get("news_folder", ""))
    requests_folder = _folder_path(station.get("requests_folder", ""))

    results = [
        _test_radio_pc(station.get("radio_pc", "")),
        _test_folder("LiveDJ", livedj_folder, ("personalities.json", "schedule.json")),
        _test_folder("News", news_folder, ("news.json",)),
        _test_folder("Request Watcher", requests_folder, ("requests.json",)),
        _test_radiodj_executable(station.get("radiodj_executable", "")),
        _test_voicebox(station.get("voicebox_api_url", "")),
    ]

    internet_status, internet_detail = _internet_connected()
    results.append(ConnectionResult("Internet", internet_status, internet_detail))
    return results


def test_all_connections(settings: dict[str, Any]) -> list[ConnectionResult]:
    return test_connection_setup(settings)


def _copy_readonly(source: Path, destination: Path, label: str) -> tuple[bool, str]:
    if not source.exists():
        return False, f"{label} not found: {source}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return True, f"Imported {label} into Studio (read-only copy)."


def import_livedj_personalities_readonly(settings: dict[str, Any]) -> tuple[bool, str]:
    integration = merge_integration_settings(settings)
    source = livedj_live_paths(integration)["personalities"]
    return _copy_readonly(source, studio_config_path("personalities"), "LiveDJ personalities")


def import_livedj_schedule_readonly(settings: dict[str, Any]) -> tuple[bool, str]:
    integration = merge_integration_settings(settings)
    source = livedj_live_paths(integration)["schedule"]
    return _copy_readonly(source, studio_config_path("schedule"), "LiveDJ schedule")


def import_news_status_readonly(settings: dict[str, Any]) -> tuple[bool, str]:
    integration = merge_integration_settings(settings)
    source = news_live_paths(integration)["config"]
    return _copy_readonly(source, studio_config_path("news"), "News status")


def import_request_settings_readonly(settings: dict[str, Any]) -> tuple[bool, str]:
    integration = merge_integration_settings(settings)
    source = requests_live_paths(integration)["config"]
    return _copy_readonly(source, studio_config_path("requests"), "Request settings")


def import_all_from_live(settings: dict[str, Any]) -> tuple[bool, str]:
    messages: list[str] = []
    overall = False
    for importer in (
        import_livedj_personalities_readonly,
        import_livedj_schedule_readonly,
        import_news_status_readonly,
        import_request_settings_readonly,
    ):
        ok, message = importer(settings)
        messages.append(message)
        overall = overall or ok
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

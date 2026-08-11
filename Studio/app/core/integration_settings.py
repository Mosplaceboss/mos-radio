"""Integration path resolution and settings normalization."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from app.core.paths import repo_root, studio_root

DEFAULT_INTEGRATION: dict[str, Any] = {
    "radiodj_process": "RadioDJ.exe",
    # Piper is the only TTS engine for requests. No Voicebox keys.
    "tts_provider": "piper",
    "tts_api_url": "http://127.0.0.1:5000",
    "tts_health_path": "/voices",
    "piper_api_url": "http://127.0.0.1:5000",
    "piper_health_path": "/voices",
    "voice_api_url": "http://127.0.0.1:5000",
    "voice_engine": "piper",
    "use_piper": True,
    "livedj_process": "MosLiveDJ.exe",
    "livedj_process_match": "",
    "livedj_process_fallbacks": [
        ["MosLiveDJ.exe", ""],
        ["python.exe", "livedj"],
        ["pythonw.exe", "livedj"],
    ],
    "request_watcher_process": "MoRequestsWatcher.exe",
    "request_watcher_match": "",
    "request_watcher_process_fallbacks": [
        ["MoRequestsWatcher.exe", ""],
        ["python.exe", "request"],
        ["pythonw.exe", "request"],
    ],
    "news_process": "MosNews.exe",
    "news_process_match": "",
    "news_process_fallbacks": [
        ["MosNews.exe", ""],
        ["python.exe", "news"],
        ["pythonw.exe", "news"],
    ],
    "live_paths": {
        "livedj": {
            "personalities": "Automation/LiveDJ/personalities.json",
            "schedule": "Automation/LiveDJ/schedule.json",
            "voice_library": "Automation/LiveDJ/voice_library.json",
            "start_script": "Automation/LiveDJ/start_watcher.bat",
            "restart_script": "Automation/LiveDJ/restart_watcher.bat",
        },
        "requests": {
            "config": "Automation/Requests/requests.json",
            "start_script": "Automation/Requests/start_watcher.bat",
            "restart_script": "Automation/Requests/restart_watcher.bat",
        },
        "news": {
            "config": "Automation/News/news.json",
            "start_script": "Automation/News/start_tasks.bat",
            "restart_script": "Automation/News/restart_tasks.bat",
            "run_now_script": "Automation/News/run_news_now.bat",
        },
    },
}


def base_integration_settings(settings: dict[str, Any]) -> dict[str, Any]:
    from app.core.platform_manager import integration_paths_from_platform

    integration = deepcopy(DEFAULT_INTEGRATION)
    platform_paths = integration_paths_from_platform()
    for target, paths in platform_paths.items():
        if target in integration["live_paths"] and isinstance(paths, dict):
            integration["live_paths"][target].update(paths)

    raw = settings.get("integration", {})
    if isinstance(raw, dict):
        for key, value in raw.items():
            if key == "live_paths" and isinstance(value, dict):
                for target, paths in value.items():
                    if isinstance(paths, dict) and target in integration["live_paths"]:
                        integration["live_paths"][target].update(paths)
            else:
                integration[key] = value
    from app.core.tts_settings import apply_tts_defaults

    return apply_tts_defaults(integration)


def normalize_integration_settings(settings: dict[str, Any]) -> dict[str, Any]:
    from app.core.live_connector import merge_integration_settings
    from app.core.tts_settings import apply_tts_defaults

    return apply_tts_defaults(merge_integration_settings(settings))


def operation_mode(settings: dict[str, Any]) -> str:
    mode = settings.get("operation_mode", "").strip().lower()
    if mode in ("development", "production"):
        return mode
    return "development"


def is_production_mode(settings: dict[str, Any]) -> bool:
    return operation_mode(settings) == "production"


def resolve_integration_path(relative_path: str) -> Path:
    path = Path(relative_path)
    if path.is_absolute():
        return path
    from app.core.platform_manager import platform_path

    platform_root = platform_path("platform_root")
    return platform_root / path


def livedj_live_paths(integration: dict[str, Any]) -> dict[str, Path]:
    paths = integration["live_paths"]["livedj"]
    return {
        "personalities": resolve_integration_path(paths["personalities"]),
        "schedule": resolve_integration_path(paths["schedule"]),
        "voice_library": resolve_integration_path(paths["voice_library"]),
        "start_script": resolve_integration_path(paths["start_script"]),
        "restart_script": resolve_integration_path(paths["restart_script"]),
    }


def requests_live_paths(integration: dict[str, Any]) -> dict[str, Path]:
    paths = integration["live_paths"]["requests"]
    return {
        "config": resolve_integration_path(paths["config"]),
        "start_script": resolve_integration_path(paths["start_script"]),
        "restart_script": resolve_integration_path(paths["restart_script"]),
    }


def news_live_paths(integration: dict[str, Any]) -> dict[str, Path]:
    paths = integration["live_paths"]["news"]
    return {
        "config": resolve_integration_path(paths["config"]),
        "start_script": resolve_integration_path(paths["start_script"]),
        "restart_script": resolve_integration_path(paths["restart_script"]),
        "run_now_script": resolve_integration_path(paths["run_now_script"]),
    }


def studio_config_path(name: str) -> Path:
    return studio_root() / "config" / f"{name}.json"

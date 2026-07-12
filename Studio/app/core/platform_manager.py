"""Platform path registry — single source of truth for production folders."""

from __future__ import annotations

import os
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config_io import read_json, write_json
from app.core.health_constants import HEALTH_ERROR, HEALTH_OK, HEALTH_WARN
from app.core.paths import config_dir

CONFIG_NAME = "PlatformManager"
DEFAULT_PLATFORM_ROOT = r"D:\MosPlaceRadioPlatform"

PathDefinition = dict[str, str]

PATH_DEFINITIONS: dict[str, PathDefinition] = {
    "platform_root": {
        "label": "Platform Root",
        "category": "Core",
        "description": "Main Mo's Place Radio platform folder on this computer.",
        "default": DEFAULT_PLATFORM_ROOT,
    },
    "music_library": {
        "label": "Music Library",
        "category": "External",
        "description": "Network or local music library used by RadioDJ.",
        "default": r"W:\Music",
    },
    "radiodj": {
        "label": "RadioDJ",
        "category": "External",
        "description": "RadioDJ installation folder on the broadcast computer.",
        "default": r"\\MOSPLACERADIO\RadioDJv3",
    },
    "automation_livedj": {
        "label": "Automation — LiveDJ",
        "category": "Automation",
        "description": "LiveDJ automation scripts, configs, and watcher files.",
        "relative": "Automation/LiveDJ",
    },
    "automation_news": {
        "label": "Automation — News",
        "category": "Automation",
        "description": "News automation tasks, feeds, and scripts.",
        "relative": "Automation/News",
    },
    "automation_requests": {
        "label": "Automation — Requests",
        "category": "Automation",
        "description": "Listener request watcher and request automation files.",
        "relative": "Automation/Requests",
    },
    "automation_advertising": {
        "label": "Automation — Advertising",
        "category": "Automation",
        "description": "Advertising automation and scheduling scripts.",
        "relative": "Automation/Advertising",
    },
    "automation_website": {
        "label": "Automation — Website",
        "category": "Automation",
        "description": "Website automation and publishing scripts.",
        "relative": "Automation/Website",
    },
    "assets_voices": {
        "label": "Assets — Voices",
        "category": "Assets",
        "description": "Voice reference files and voice-related assets.",
        "relative": "Assets/Voices",
    },
    "assets_personalities": {
        "label": "Assets — Personalities",
        "category": "Assets",
        "description": "On-air personality images and profile assets.",
        "relative": "Assets/Personalities",
    },
    "assets_logos": {
        "label": "Assets — Logos",
        "category": "Assets",
        "description": "Station logos and brand artwork.",
        "relative": "Assets/Logos",
    },
    "assets_images": {
        "label": "Assets — Images",
        "category": "Assets",
        "description": "General station images and graphics.",
        "relative": "Assets/Images",
    },
    "audio_commercials": {
        "label": "Audio — Commercials",
        "category": "Audio",
        "description": "Commercial and sponsor audio files.",
        "relative": "Audio/Commercials",
    },
    "audio_generated": {
        "label": "Audio — Generated",
        "category": "Audio",
        "description": "Generated voice tracks and automated audio output.",
        "relative": "Audio/Generated",
    },
    "audio_news": {
        "label": "Audio — News",
        "category": "Audio",
        "description": "News audio segments and headline recordings.",
        "relative": "Audio/News",
    },
    "audio_promos": {
        "label": "Audio — Promos",
        "category": "Audio",
        "description": "Station promos and imaging audio.",
        "relative": "Audio/Promos",
    },
    "audio_requests": {
        "label": "Audio — Requests",
        "category": "Audio",
        "description": "Listener request audio and greeting files.",
        "relative": "Audio/Requests",
    },
    "audio_sweepers": {
        "label": "Audio — Sweepers",
        "category": "Audio",
        "description": "Sweepers, liners, and short station IDs.",
        "relative": "Audio/Sweepers",
    },
    "documentation": {
        "label": "Documentation",
        "category": "Platform",
        "description": "Station procedures, production notes, and reference documents.",
        "relative": "Documentation",
    },
    "logs": {
        "label": "Logs",
        "category": "Platform",
        "description": "Platform-wide operational logs.",
        "relative": "Logs",
    },
    "reports": {
        "label": "Reports",
        "category": "Platform",
        "description": "Generated station reports and summaries.",
        "relative": "Reports",
    },
    "backups": {
        "label": "Backups",
        "category": "Platform",
        "description": "Configuration and data backups.",
        "relative": "Backups",
    },
    "archive": {
        "label": "Archive",
        "category": "Platform",
        "description": "Archived shows, scripts, and retired content.",
        "relative": "Archive",
    },
    "studio": {
        "label": "Studio",
        "category": "Platform",
        "description": "Studio production workspace on the platform.",
        "relative": "Studio",
    },
    "website": {
        "label": "Website",
        "category": "Platform",
        "description": "Website content and publishing files.",
        "relative": "Website",
    },
    "station_data": {
        "label": "Station Data",
        "category": "Platform",
        "description": "Shared station data, exports, and operational datasets.",
        "relative": "StationData",
    },
}

AUTOMATION_FOLDER_KEYS = {
    "LiveDJ": "automation_livedj",
    "News": "automation_news",
    "Requests": "automation_requests",
    "Advertising": "automation_advertising",
    "Website": "automation_website",
}


def default_path_for_key(key: str, platform_root: str | None = None) -> str:
    definition = PATH_DEFINITIONS[key]
    if "default" in definition:
        return definition["default"]
    root = platform_root or DEFAULT_PLATFORM_ROOT
    return str(Path(root) / definition["relative"])


def default_paths(platform_root: str | None = None) -> dict[str, str]:
    root = platform_root or DEFAULT_PLATFORM_ROOT
    return {key: default_path_for_key(key, root) for key in PATH_DEFINITIONS}


def default_platform_config() -> dict[str, Any]:
    paths = default_paths()
    return {
        "version": 1,
        "paths": paths,
        "last_validated": "",
        "validation_status": HEALTH_WARN,
        "validation_results": {},
    }


def normalize_platform_config(data: dict[str, Any] | None) -> dict[str, Any]:
    base = default_platform_config()
    if not data:
        return base

    merged = deepcopy(base)
    raw_paths = data.get("paths", {})
    if isinstance(raw_paths, dict):
        for key in PATH_DEFINITIONS:
            value = raw_paths.get(key, "")
            if isinstance(value, str) and value.strip():
                merged["paths"][key] = value.strip()

    platform_root = merged["paths"]["platform_root"]
    for key, definition in PATH_DEFINITIONS.items():
        if "relative" in definition and not raw_paths.get(key):
            merged["paths"][key] = default_path_for_key(key, platform_root)

    if isinstance(data.get("last_validated"), str):
        merged["last_validated"] = data["last_validated"]
    if isinstance(data.get("validation_status"), str):
        merged["validation_status"] = data["validation_status"]
    if isinstance(data.get("validation_results"), dict):
        merged["validation_results"] = deepcopy(data["validation_results"])
    return merged


def config_file_path() -> Path:
    return config_dir() / f"{CONFIG_NAME}.json"


def load_platform_config(config_manager=None) -> dict[str, Any]:
    if config_manager is not None:
        return normalize_platform_config(config_manager.load(CONFIG_NAME, default_platform_config()))

    path = config_file_path()
    if path.exists():
        data = read_json(path, default_platform_config())
        return normalize_platform_config(data)
    return default_platform_config()


def save_platform_config(data: dict[str, Any], config_manager=None) -> dict[str, Any]:
    normalized = normalize_platform_config(data)
    if config_manager is not None:
        config_manager.save(CONFIG_NAME, normalized)
        return normalized

    write_json(config_file_path(), normalized)
    return normalized


def platform_path(key: str, config_manager=None) -> Path:
    config = load_platform_config(config_manager)
    path_str = config["paths"].get(key, default_path_for_key(key))
    return Path(path_str)


def platform_path_str(key: str, config_manager=None) -> str:
    return str(platform_path(key, config_manager))


def automation_root(config_manager=None) -> Path:
    return platform_path("platform_root", config_manager) / "Automation"


def automation_module_dir(folder_name: str, config_manager=None) -> Path:
    mapped_key = AUTOMATION_FOLDER_KEYS.get(folder_name)
    if mapped_key:
        return platform_path(mapped_key, config_manager)
    return automation_root(config_manager) / folder_name


def platform_logs_dir(config_manager=None) -> Path:
    return platform_path("logs", config_manager)


def platform_backups_dir(config_manager=None) -> Path:
    return platform_path("backups", config_manager)


def platform_reports_dir(config_manager=None) -> Path:
    return platform_path("reports", config_manager)


def platform_documentation_dir(config_manager=None) -> Path:
    return platform_path("documentation", config_manager)


def integration_paths_from_platform(config_manager=None) -> dict[str, dict[str, str]]:
    livedj = platform_path("automation_livedj", config_manager)
    news = platform_path("automation_news", config_manager)
    requests = platform_path("automation_requests", config_manager)
    radiodj = platform_path("radiodj", config_manager)

    return {
        "livedj": {
            "personalities": str(livedj / "personalities.json"),
            "schedule": str(livedj / "schedule.json"),
            "voice_library": str(livedj / "voice_library.json"),
            "start_script": str(livedj / "start_watcher.bat"),
            "restart_script": str(livedj / "restart_watcher.bat"),
        },
        "requests": {
            "config": str(requests / "requests.json"),
            "start_script": str(requests / "start_watcher.bat"),
            "restart_script": str(requests / "restart_watcher.bat"),
        },
        "news": {
            "config": str(news / "news.json"),
            "start_script": str(news / "start_tasks.bat"),
            "restart_script": str(news / "restart_tasks.bat"),
            "run_now_script": str(news / "run_news_now.bat"),
        },
        "radiodj": {
            "folder": str(radiodj),
        },
        "music_library": {
            "folder": platform_path_str("music_library", config_manager),
        },
    }


def test_platform_path(key: str, path_value: str) -> dict[str, str]:
    text = path_value.strip()
    if not text:
        return {"status": HEALTH_ERROR, "message": "Path is empty."}

    path = Path(text)
    if path.exists():
        if path.is_dir():
            return {"status": HEALTH_OK, "message": "Folder found and accessible."}
        return {"status": HEALTH_OK, "message": "Path found."}

    parent = path.parent
    if parent != path and parent.exists():
        return {
            "status": HEALTH_WARN,
            "message": "Parent folder exists, but this exact path was not found yet.",
        }

    return {"status": HEALTH_ERROR, "message": "Path was not found or is not accessible."}


def validate_all_paths(config: dict[str, Any] | None = None) -> dict[str, Any]:
    normalized = normalize_platform_config(config)
    results: dict[str, dict[str, str]] = {}
    statuses: list[str] = []

    for key in PATH_DEFINITIONS:
        result = test_platform_path(key, normalized["paths"].get(key, ""))
        results[key] = result
        statuses.append(result["status"])

    if HEALTH_ERROR in statuses:
        overall = HEALTH_ERROR
    elif HEALTH_WARN in statuses:
        overall = HEALTH_WARN
    else:
        overall = HEALTH_OK

    normalized["validation_results"] = results
    normalized["validation_status"] = overall
    normalized["last_validated"] = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
    return normalized


def open_folder(path_value: str) -> None:
    path = Path(path_value.strip())
    target = path if path.exists() else path.parent
    if not str(target):
        raise FileNotFoundError("No folder path to open.")
    os.startfile(str(target))


def managed_folder_count() -> int:
    return len(PATH_DEFINITIONS)


def ensure_default_platform_config() -> Path:
    path = config_file_path()
    if not path.exists():
        write_json(path, default_platform_config())
    return path

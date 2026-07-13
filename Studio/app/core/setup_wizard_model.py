"""First-run setup wizard — save platform paths and test connections."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.health_constants import HEALTH_ERROR, HEALTH_OK, HEALTH_WARN
from app.core.live_connector import (
    build_local_from_station,
    save_local_integration,
    test_connection_setup,
)
from app.core.paths import writable_assets_dir
from app.core.platform_manager import (
    PATH_DEFINITIONS,
    load_platform_config,
    save_platform_config,
    test_platform_path,
    validate_all_paths,
)

DEFAULT_PLATFORM_ROOT = r"D:\MosPlaceRadioPlatform"


@dataclass
class SetupWizardData:
    station_name: str = "Mo's Place Radio"
    logo_path: str = ""
    platform_root: str = DEFAULT_PLATFORM_ROOT
    radiodj_path: str = ""
    music_library_path: str = ""
    voicebox_api_url: str = "http://127.0.0.1:7860"
    voice_output_path: str = ""
    livedj_folder: str = ""
    news_folder: str = ""
    requests_folder: str = ""
    website_folder: str = ""
    radio_pc: str = ""


@dataclass
class SetupTestResult:
    name: str
    status: str
    message: str


@dataclass
class SetupWizardSnapshot:
    data: SetupWizardData
    path_results: list[SetupTestResult] = field(default_factory=list)
    connection_results: list[SetupTestResult] = field(default_factory=list)


def _default_paths(platform_root: str) -> dict[str, str]:
    root = Path(platform_root)
    paths: dict[str, str] = {"platform_root": str(root)}
    for key, definition in PATH_DEFINITIONS.items():
        if key == "platform_root":
            continue
        if "default" in definition:
            paths[key] = definition["default"]
        elif "relative" in definition:
            paths[key] = str(root / definition["relative"])
    if not paths.get("radiodj"):
        paths["radiodj"] = PATH_DEFINITIONS["radiodj"]["default"]
    if not paths.get("music_library"):
        paths["music_library"] = PATH_DEFINITIONS["music_library"]["default"]
    return paths


def load_setup_data(config_manager) -> SetupWizardData:
    settings = config_manager.load("settings", {})
    platform = load_platform_config(config_manager)
    paths = platform.get("paths", {})
    root = paths.get("platform_root", DEFAULT_PLATFORM_ROOT)
    station = settings.get("integration", {})
    local_station = {}
    try:
        from app.core.live_connector import load_local_integration

        local = load_local_integration()
        if isinstance(local.get("station"), dict):
            local_station = local["station"]
    except Exception:
        pass

    return SetupWizardData(
        station_name=settings.get("station_name", "Mo's Place Radio"),
        logo_path=settings.get("station_logo", ""),
        platform_root=root,
        radiodj_path=paths.get("radiodj", PATH_DEFINITIONS["radiodj"]["default"]),
        music_library_path=paths.get("music_library", PATH_DEFINITIONS["music_library"]["default"]),
        voicebox_api_url=local_station.get("voicebox_api_url", station.get("voicebox_api_url", "http://127.0.0.1:7860")),
        voice_output_path=paths.get("audio_generated", str(Path(root) / "Audio" / "Generated")),
        livedj_folder=local_station.get("livedj_folder", paths.get("automation_livedj", str(Path(root) / "Automation" / "LiveDJ"))),
        news_folder=local_station.get("news_folder", paths.get("automation_news", str(Path(root) / "Automation" / "News"))),
        requests_folder=local_station.get("requests_folder", paths.get("automation_requests", str(Path(root) / "Automation" / "Requests"))),
        website_folder=paths.get("website", str(Path(root) / "Website")),
        radio_pc=local_station.get("radio_pc", ""),
    )


def test_setup(data: SetupWizardData, config_manager) -> SetupWizardSnapshot:
    path_results: list[SetupTestResult] = []
    checks = (
        ("Platform Root", "platform_root", data.platform_root),
        ("RadioDJ", "radiodj", data.radiodj_path),
        ("Music Library", "music_library", data.music_library_path),
        ("Generated Voice Output", "audio_generated", data.voice_output_path),
        ("LiveDJ", "automation_livedj", data.livedj_folder),
        ("News", "automation_news", data.news_folder),
        ("Requests", "automation_requests", data.requests_folder),
        ("Website", "website", data.website_folder),
    )
    for label, key, value in checks:
        result = test_platform_path(key, value)
        path_results.append(SetupTestResult(label, result["status"], result["message"]))

    platform_config = load_platform_config(config_manager)
    platform_config["paths"] = _default_paths(data.platform_root)
    platform_config["paths"].update(
        {
            "platform_root": data.platform_root,
            "radiodj": data.radiodj_path,
            "music_library": data.music_library_path,
            "audio_generated": data.voice_output_path,
            "automation_livedj": data.livedj_folder,
            "automation_news": data.news_folder,
            "automation_requests": data.requests_folder,
            "website": data.website_folder,
            "assets_voices": str(Path(data.platform_root) / "Assets" / "Voices"),
        }
    )
    save_platform_config(platform_config, config_manager)

    station = {
        "radio_pc": data.radio_pc,
        "livedj_folder": data.livedj_folder,
        "news_folder": data.news_folder,
        "requests_folder": data.requests_folder,
        "radiodj_executable": str(Path(data.radiodj_path) / "RadioDJ.exe"),
        "voicebox_api_url": data.voicebox_api_url,
    }
    save_local_integration(build_local_from_station(station, enabled=True))

    settings = config_manager.load("settings", {})
    settings["station_name"] = data.station_name
    settings.setdefault("integration", {})
    settings["integration"]["voicebox_api_url"] = data.voicebox_api_url
    config_manager.save("settings", settings)

    connection_results = [
        SetupTestResult(item.name, item.status, item.message)
        for item in test_connection_setup(settings)
    ]
    website_folder = Path(data.website_folder)
    if website_folder.exists():
        connection_results.append(
            SetupTestResult("Website", HEALTH_OK, f"Website folder is ready at {website_folder}")
        )
    else:
        connection_results.append(
            SetupTestResult("Website", HEALTH_WARN, f"Website folder was not found: {website_folder}")
        )

    return SetupWizardSnapshot(data=data, path_results=path_results, connection_results=connection_results)


def apply_setup(data: SetupWizardData, config_manager) -> None:
    platform_config = load_platform_config(config_manager)
    platform_config["paths"] = _default_paths(data.platform_root)
    platform_config["paths"].update(
        {
            "platform_root": data.platform_root,
            "radiodj": data.radiodj_path,
            "music_library": data.music_library_path,
            "audio_generated": data.voice_output_path,
            "automation_livedj": data.livedj_folder,
            "automation_news": data.news_folder,
            "automation_requests": data.requests_folder,
            "website": data.website_folder,
            "assets_voices": str(Path(data.platform_root) / "Assets" / "Voices"),
            "studio": str(Path(data.platform_root) / "Studio"),
        }
    )
    validated = validate_all_paths(platform_config)
    save_platform_config(validated, config_manager)

    station = {
        "radio_pc": data.radio_pc,
        "livedj_folder": data.livedj_folder,
        "news_folder": data.news_folder,
        "requests_folder": data.requests_folder,
        "radiodj_executable": str(Path(data.radiodj_path) / "RadioDJ.exe"),
        "voicebox_api_url": data.voicebox_api_url,
    }
    save_local_integration(build_local_from_station(station, enabled=True))

    settings = config_manager.load("settings", {})
    settings["station_name"] = data.station_name
    settings["setup_complete"] = True
    settings.setdefault("integration", {})
    settings["integration"]["voicebox_api_url"] = data.voicebox_api_url
    if data.logo_path:
        settings["station_logo"] = data.logo_path
    config_manager.save("settings", settings)

    _ensure_platform_folders(data.platform_root)


def copy_station_logo(source: Path) -> str:
    if not source.exists():
        raise FileNotFoundError(f"Logo file not found: {source}")
    destination = writable_assets_dir() / "logo.png"
    shutil.copy2(source, destination)
    return str(destination)


def _ensure_platform_folders(platform_root: str) -> None:
    root = Path(platform_root)
    for relative in (
        "Automation/LiveDJ",
        "Automation/News",
        "Automation/Requests",
        "Automation/Website",
        "Audio/Generated",
        "Audio/News",
        "Assets/Voices",
        "Backups",
        "Documentation",
        "Documentation/InventoryReports",
        "Logs",
        "Reports",
        "StationData",
        "Studio",
        "Website",
    ):
        (root / relative).mkdir(parents=True, exist_ok=True)


def setup_required(settings: dict[str, Any] | None) -> bool:
    data = settings or {}
    return not bool(data.get("setup_complete", False))

"""Verify Connection Setup save, test, and read-only import."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

STUDIO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(STUDIO_ROOT))

from app.core.config_manager import ConfigManager
from app.core.health_constants import HEALTH_OK
from app.core.live_connector import (
    build_local_from_station,
    import_livedj_personalities_readonly,
    import_livedj_schedule_readonly,
    import_news_status_readonly,
    import_request_settings_readonly,
    local_integration_path,
    save_local_integration,
    test_connection_setup,
)


def main() -> int:
    config_dir = STUDIO_ROOT / "config"
    local_path = local_integration_path()
    backup = None
    if local_path.exists():
        backup = local_path.read_text(encoding="utf-8")

    temp_live = Path(tempfile.mkdtemp(prefix="moplace-live-"))
    try:
        livedj = temp_live / "LiveDJ"
        news = temp_live / "News"
        requests = temp_live / "Requests"
        for folder in (livedj, news, requests):
            folder.mkdir(parents=True)
        (livedj / "personalities.json").write_text('{"personalities":[]}', encoding="utf-8")
        (livedj / "schedule.json").write_text('{"slots":[]}', encoding="utf-8")
        (news / "news.json").write_text('{"feeds":[]}', encoding="utf-8")
        (requests / "requests.json").write_text('{"enabled":true}', encoding="utf-8")

        station = {
            "radio_pc": "127.0.0.1",
            "livedj_folder": str(livedj),
            "news_folder": str(news),
            "requests_folder": str(requests),
            "radiodj_executable": "",
            "voicebox_api_url": "http://127.0.0.1:7860",
        }
        save_local_integration(build_local_from_station(station, enabled=True))

        settings = ConfigManager().load("settings", {})
        results = test_connection_setup(settings)
        names = {result.name for result in results}
        required = {"Radio PC", "LiveDJ", "News", "Request Watcher", "RadioDJ", "Voicebox API", "Internet"}
        if names != required:
            print(f"FAIL: expected {required}, got {names}")
            return 1

        livedj_result = next(result for result in results if result.name == "LiveDJ")
        if livedj_result.status != HEALTH_OK:
            print(f"FAIL: LiveDJ test: {livedj_result.message}")
            return 1

        for importer, label in (
            (import_livedj_personalities_readonly, "personalities"),
            (import_livedj_schedule_readonly, "schedule"),
            (import_news_status_readonly, "news"),
            (import_request_settings_readonly, "requests"),
        ):
            ok, message = importer(settings)
            if not ok:
                print(f"FAIL: {label}: {message}")
                return 1
            print(f"IMPORT OK: {label}")

        print("CONNECTION OK: save, test, and read-only import verified.")
        return 0
    finally:
        shutil.rmtree(temp_live, ignore_errors=True)
        if backup is not None:
            local_path.write_text(backup, encoding="utf-8")
        elif local_path.exists():
            local_path.unlink()


if __name__ == "__main__":
    raise SystemExit(main())

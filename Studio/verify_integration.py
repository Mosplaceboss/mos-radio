"""Integration verification: import, publish, backup, restore, and status detection."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

STUDIO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(STUDIO_ROOT))

from app.core.backup_manager import create_backup, last_backup_path, restore_last_backup
from app.core.config_manager import ConfigManager
from app.core.integration_settings import normalize_integration_settings
from app.core.livedj_integration import import_livedj_from_live, validate_livedj_bundle
from app.core.publish_manager import (
    import_news_from_live,
    import_requests_from_live,
    publish_livedj,
    publish_news,
    publish_requests,
    restore_livedj_backup,
    restore_news_backup,
    restore_requests_backup,
)
from app.core.system_status import build_live_system_status


def _assert(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    repo = STUDIO_ROOT.parent
    temp_live = Path(tempfile.mkdtemp(prefix="mos-live-"))
    integration = normalize_integration_settings({})
    integration["live_paths"]["livedj"]["personalities"] = str(temp_live / "personalities.json")
    integration["live_paths"]["livedj"]["schedule"] = str(temp_live / "schedule.json")
    integration["live_paths"]["livedj"]["voice_library"] = str(temp_live / "voice_library.json")
    integration["live_paths"]["requests"]["config"] = str(temp_live / "requests.json")
    integration["live_paths"]["news"]["config"] = str(temp_live / "news.json")

    for name in ("personalities", "schedule", "voice_library", "requests", "news"):
        source = STUDIO_ROOT / "config" / f"{name}.json"
        shutil.copy2(source, temp_live / f"{name}.json")

    cm = ConfigManager()

    ok, message, imported = import_livedj_from_live(integration)
    _assert(ok, f"LiveDJ import failed: {message}", errors)
    _assert(len(imported) == 3, "LiveDJ import did not copy 3 files", errors)

    ok, message = import_requests_from_live(integration)
    _assert(ok, f"Requests import failed: {message}", errors)

    ok, message = import_news_from_live(integration)
    _assert(ok, f"News import failed: {message}", errors)

    validation_errors = validate_livedj_bundle(cm)
    _assert(not validation_errors, f"LiveDJ validation failed: {validation_errors[:3]}", errors)

    live_requests = temp_live / "requests.json"
    original_requests = json.loads(live_requests.read_text(encoding="utf-8"))
    original_requests["requests_per_listener"] = 99
    live_requests.write_text(json.dumps(original_requests, indent=2) + "\n", encoding="utf-8")

    ok, message = publish_requests(cm, integration)
    _assert(ok, f"Requests publish failed: {message}", errors)
    published = json.loads(live_requests.read_text(encoding="utf-8"))
    _assert(published.get("requests_per_listener") != 99, "Requests publish did not overwrite live file", errors)
    _assert(last_backup_path("requests") is not None, "Requests backup not recorded", errors)

    ok, message = restore_requests_backup(integration)
    _assert(ok, f"Requests restore failed: {message}", errors)
    restored = json.loads(live_requests.read_text(encoding="utf-8"))
    _assert(restored.get("requests_per_listener") == 99, "Requests restore did not revert live file", errors)

    ok, message = publish_livedj(cm, integration)
    _assert(ok, f"LiveDJ publish failed: {message}", errors)
    _assert(last_backup_path("livedj") is not None, "LiveDJ backup not recorded", errors)

    ok, message = restore_livedj_backup(integration)
    _assert(ok, f"LiveDJ restore failed: {message}", errors)

    ok, message = publish_news(cm, integration)
    _assert(ok, f"News publish failed: {message}", errors)
    _assert(last_backup_path("news") is not None, "News backup not recorded", errors)

    ok, message = restore_news_backup(integration)
    _assert(ok, f"News restore failed: {message}", errors)

    status = build_live_system_status(cm.load("settings", {}))
    _assert(len(status.services) >= 5, "Live system status missing services", errors)

    shutil.rmtree(temp_live, ignore_errors=True)

    if errors:
        print("INTEGRATION FAILURES:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("Integration verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

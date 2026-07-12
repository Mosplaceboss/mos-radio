"""Mo's Place Inventory entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

INVENTORY_ROOT = Path(__file__).resolve().parent.parent
if str(INVENTORY_ROOT) not in sys.path:
    sys.path.insert(0, str(INVENTORY_ROOT))

from app.core.path_validation import all_scan_paths_valid
from app.core.scan_engine import ScanEngine
from app.core.settings_store import load_settings


def run_headless_scan() -> int:
    settings = load_settings()
    ok, messages = all_scan_paths_valid(settings)
    if not ok:
        for message in messages:
            print(message, file=sys.stderr)
        return 1

    done = {"ok": False, "error": ""}

    def complete(_snapshot, _paths) -> None:
        done["ok"] = True

    def failed(error: Exception) -> None:
        done["error"] = str(error)

    engine = ScanEngine(on_complete=complete, on_error=failed)
    engine.start(
        office_folders=settings["office_pc_folders"],
        radio_folders=settings["radio_pc_folders"],
        output_folder=settings["output_folder"],
    )
    engine.join()
    if done["error"]:
        print(done["error"], file=sys.stderr)
        return 1
    if not done["ok"]:
        print("Scan did not complete.", file=sys.stderr)
        return 1
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Mo's Place Inventory")
    parser.add_argument(
        "--scan",
        action="store_true",
        help="Run an unattended inventory scan using saved defaults and exit.",
    )
    parser.add_argument(
        "--auto-scan",
        action="store_true",
        help="Open the UI and start scanning immediately when paths are valid.",
    )
    args = parser.parse_args()

    if args.scan:
        raise SystemExit(run_headless_scan())

    from app.ui.main_window import InventoryApplication

    InventoryApplication(auto_scan=args.auto_scan).run()


if __name__ == "__main__":
    main()

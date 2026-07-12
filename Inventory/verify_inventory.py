"""Verify Mo's Place Inventory modules and a local read-only scan."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

INVENTORY_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(INVENTORY_ROOT))

from app.core.compare import find_duplicate_files
from app.core.file_scanner import FileInventoryScanner
from app.core.models import FileRecord, ScanError
from app.core.recommendations import build_recommendations
from app.core.reports import write_checkpoint, write_reports
from app.core.scan_engine import ScanEngine


def test_settings_roundtrip() -> None:
    from app.core.settings_store import (
        DEFAULT_OFFICE_PC,
        DEFAULT_OUTPUT_FOLDER,
        DEFAULT_RADIO_PC,
        OFFICE_PLATFORM_PHYSICAL,
        browse_initial_dir,
        current_machine_name,
        load_settings,
        machine_defaults,
        save_settings,
    )

    defaults = machine_defaults()
    if defaults["office_pc_path"] != DEFAULT_OFFICE_PC:
        raise RuntimeError("Office PC default should be Office")
    if defaults["radio_pc_path"] != DEFAULT_RADIO_PC:
        raise RuntimeError("Radio PC default should be MosPlaceRadio")
    if defaults["platform_folder"] != OFFICE_PLATFORM_PHYSICAL:
        raise RuntimeError("Platform default should be D:\\MosPlaceRadioPlatform")
    if defaults["output_folder"] != DEFAULT_OUTPUT_FOLDER:
        raise RuntimeError("Output default should be the Documentation\\InventoryReports folder")

    machine = current_machine_name()
    save_settings(
        {
            "office_pc_path": DEFAULT_OFFICE_PC,
            "radio_pc_path": DEFAULT_RADIO_PC,
            "platform_folder": OFFICE_PLATFORM_PHYSICAL,
            "output_folder": DEFAULT_OUTPUT_FOLDER,
        }
    )
    loaded = load_settings()
    if loaded["platform_folder"] != OFFICE_PLATFORM_PHYSICAL:
        raise RuntimeError("Office PC platform path was not saved correctly")
    if loaded["output_folder"] != DEFAULT_OUTPUT_FOLDER:
        raise RuntimeError("Office PC output path was not saved correctly")
    store_path = INVENTORY_ROOT / "inventory_settings.json"
    if store_path.exists():
        text = store_path.read_text(encoding="utf-8")
        if machine not in text:
            raise RuntimeError("Settings were not stored under the current machine profile")

    if not browse_initial_dir("platform_folder"):
        raise RuntimeError("Browse initial directory should not be empty")
    if browse_initial_dir("radio_pc_path") != r"\\":
        raise RuntimeError("Radio PC browse should start at the network root when unset")


def test_resolve_local_office() -> None:
    from app.core.paths_util import is_computer_name, resolve_computer_root

    if not is_computer_name("Office"):
        raise RuntimeError("Office should be treated as a computer name")
    label, roots, _errors = resolve_computer_root("Office")
    if label != "Office":
        raise RuntimeError("Office label was not preserved")
    if not roots:
        raise RuntimeError("Local Office scan should resolve at least one root")


def test_scan_error_recording() -> None:
    scanner = FileInventoryScanner()
    errors: list[ScanError] = []
    scanner._record_error = errors.append  # type: ignore[method-assign]
    drives, folders, files, _components = scanner.scan_roots("Test", [Path("Z:\\definitely-missing-root")])
    if drives and not errors:
        return
    if not errors:
        raise RuntimeError("Expected scan errors for a missing root")


def test_duplicate_detection() -> None:
    files = [
        FileRecord("a.txt", "a.txt", ".txt", 10, "", "", "Office"),
        FileRecord("b.txt", "a.txt", ".txt", 10, "", "", "Radio"),
    ]
    groups = find_duplicate_files(files)
    if not groups:
        raise RuntimeError("Expected duplicate file groups")


def test_local_scan() -> None:
    done = {"ok": False, "error": ""}

    def complete(snapshot, _paths) -> None:
        if not snapshot.files:
            raise RuntimeError("Expected files from local scan")
        done["ok"] = True

    def failed(error: Exception) -> None:
        done["error"] = str(error)

    with tempfile.TemporaryDirectory() as tmp:
        engine = ScanEngine(on_complete=complete, on_error=failed)
        engine.start(
            office_pc=str(INVENTORY_ROOT),
            radio_pc=str(INVENTORY_ROOT),
            platform_folder=str(INVENTORY_ROOT),
            output_folder=tmp,
        )
        engine.join(timeout=120)
    if done["error"]:
        raise RuntimeError(done["error"])
    if not done["ok"]:
        raise RuntimeError("Scan did not complete")


def test_report_generation() -> None:
    from app.core.models import InventorySnapshot

    with tempfile.TemporaryDirectory() as tmp:
        snapshot = InventorySnapshot(
            scanned_at="now",
            office_pc="Office",
            radio_pc="MosPlaceRadio",
            platform_folder=".",
            output_folder=tmp,
            status="complete",
        )
        paths = write_reports(snapshot)
        for name in (
            "Inventory.json",
            "ProductionMap.html",
            "FolderMap.html",
            "ScheduledTasks.html",
            "DuplicateFiles.html",
            "Recommendations.html",
        ):
            if name not in paths:
                raise RuntimeError(f"Missing report: {name}")
        checkpoint = write_checkpoint(snapshot)
        if "Inventory.json.partial" not in checkpoint:
            raise RuntimeError("Missing partial checkpoint report")


def main() -> int:
    test_settings_roundtrip()
    test_resolve_local_office()
    test_scan_error_recording()
    test_duplicate_detection()
    test_report_generation()
    test_local_scan()
    print("Inventory verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

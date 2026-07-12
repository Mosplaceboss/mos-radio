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
from app.core.reports import write_checkpoint, write_reports
from app.core.scan_engine import ScanEngine


def test_settings_roundtrip() -> None:
    from app.core.settings_store import (
        DEFAULT_OFFICE_FOLDERS,
        DEFAULT_OUTPUT_FOLDER,
        browse_initial_dir,
        current_machine_name,
        default_office_folders,
        load_settings,
        machine_defaults,
        save_settings,
    )

    defaults = machine_defaults()
    if defaults["radio_pc_folders"]:
        raise RuntimeError("Radio PC folder list should start empty")
    if defaults["output_folder"] != DEFAULT_OUTPUT_FOLDER:
        raise RuntimeError("Output default should be the Documentation\\InventoryReports folder")
    if default_office_folders() != list(DEFAULT_OFFICE_FOLDERS):
        raise RuntimeError("Office defaults should include MoPlaceStudio, MosPlaceRadioPlatform, and MosNews")

    machine = current_machine_name()
    save_settings(
        {
            "office_pc_folders": [str(INVENTORY_ROOT)],
            "radio_pc_folders": [],
            "output_folder": DEFAULT_OUTPUT_FOLDER,
        }
    )
    loaded = load_settings()
    if loaded["output_folder"] != DEFAULT_OUTPUT_FOLDER:
        raise RuntimeError("Office PC output path was not saved correctly")
    if loaded["radio_pc_folders"]:
        raise RuntimeError("Radio folder list should remain empty unless user adds folders")
    store_path = INVENTORY_ROOT / "inventory_settings.json"
    if store_path.exists():
        text = store_path.read_text(encoding="utf-8")
        if machine not in text:
            raise RuntimeError("Settings were not stored under the current machine profile")

    if browse_initial_dir("radio_pc_folders") != r"\\":
        raise RuntimeError("Radio PC browse should start at the network root when unset")


def test_legacy_settings_migration() -> None:
    from app.core.settings_store import _migrate_legacy_settings, sanitize_folder_list

    migrated = _migrate_legacy_settings(
        {
            "office_pc_path": r"\\MosPlaceRadio\C$",
            "radio_pc_path": r"\\MosPlaceRadio\D$",
            "platform_folder": r"D:\MosPlaceRadioPlatform",
            "output_folder": r"D:\MosPlaceRadioPlatform\Documentation\InventoryReports",
        }
    )
    office = sanitize_folder_list(migrated["office_pc_folders"])
    radio = sanitize_folder_list(migrated["radio_pc_folders"])
    if any("C$" in path or "D$" in path for path in office + radio):
        raise RuntimeError("Legacy admin shares should be removed during migration")
    if r"D:\MosPlaceRadioPlatform" not in office:
        raise RuntimeError("Legacy platform folder should migrate into office folders")


def test_admin_share_rejected() -> None:
    from app.core.path_validation import validate_scan_path
    from app.core.paths_util import is_admin_share, resolve_scan_folder, sanitize_folder_path

    if not is_admin_share(r"\\MosPlaceRadio\C$"):
        raise RuntimeError("C$ admin share should be detected")
    if sanitize_folder_path(r"\\MosPlaceRadio\D$") is not None:
        raise RuntimeError("D$ admin share should be sanitized away")
    ok, message, _warning = validate_scan_path(r"\\MosPlaceRadio\D$", label="Radio PC folder")
    if ok:
        raise RuntimeError("Admin share should be rejected during validation")

    _label, roots, errors = resolve_scan_folder(r"\\MosPlaceRadio\C$", label="Radio")
    if roots:
        raise RuntimeError("Admin share should not resolve to scan roots")
    if not errors:
        raise RuntimeError("Admin share resolution should record an error")


def test_inaccessible_folder_continues() -> None:
    from app.core.paths_util import resolve_scan_folder

    _label, roots, errors = resolve_scan_folder(r"\\MosPlaceRadio\MissingShare", label="Radio")
    if roots:
        raise RuntimeError("Missing share should not resolve to scan roots")
    if not errors:
        raise RuntimeError("Missing share should record a resolution error")


def test_scan_error_recording() -> None:
    scanner = FileInventoryScanner()
    errors: list[ScanError] = []
    scanner._record_error = errors.append  # type: ignore[method-assign]
    _drives, _folders, _files, _components = scanner.scan_roots(
        "Test",
        [Path("Z:\\definitely-missing-root")],
        folder_path="Z:\\definitely-missing-root",
    )
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
            office_folders=[str(INVENTORY_ROOT)],
            radio_folders=[],
            output_folder=tmp,
        )
        engine.join(timeout=120)
    if done["error"]:
        raise RuntimeError(done["error"])
    if not done["ok"]:
        raise RuntimeError("Scan did not complete")


def test_unreachable_share_scan_completes() -> None:
    done = {"ok": False, "snapshot": None}

    def complete(snapshot, _paths) -> None:
        done["ok"] = True
        done["snapshot"] = snapshot

    with tempfile.TemporaryDirectory() as tmp:
        engine = ScanEngine(on_complete=complete, on_error=lambda _e: None)
        engine.start(
            office_folders=[str(INVENTORY_ROOT)],
            radio_folders=[r"\\MosPlaceRadio\MissingShare"],
            output_folder=tmp,
        )
        engine.join(timeout=120)

    if not done["ok"]:
        raise RuntimeError("Scan should complete even when a share is unreachable")
    snapshot = done["snapshot"]
    if snapshot is None or not snapshot.scan_errors:
        raise RuntimeError("Unreachable share should be recorded in scan errors")


def test_report_generation() -> None:
    from app.core.models import InventorySnapshot

    with tempfile.TemporaryDirectory() as tmp:
        snapshot = InventorySnapshot(
            scanned_at="now",
            office_pc=str(INVENTORY_ROOT),
            radio_pc="",
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


def test_app_imports() -> None:
    from app.ui.main_window import InventoryApplication

    if InventoryApplication is None:
        raise RuntimeError("Inventory UI should import cleanly")


def main() -> int:
    test_settings_roundtrip()
    test_legacy_settings_migration()
    test_admin_share_rejected()
    test_inaccessible_folder_continues()
    test_scan_error_recording()
    test_duplicate_detection()
    test_report_generation()
    test_local_scan()
    test_unreachable_share_scan_completes()
    test_app_imports()
    print("Inventory verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

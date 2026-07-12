"""Verify Mo's Place Inventory modules and a local read-only scan."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

INVENTORY_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(INVENTORY_ROOT))

from app.core.compare import find_duplicate_files
from app.core.file_scanner import FileInventoryScanner
from app.core.models import FileRecord
from app.core.recommendations import build_recommendations
from app.core.reports import write_reports
from app.core.scan_engine import ScanEngine


def test_settings_roundtrip() -> None:
    from app.core.settings_store import current_machine_name, load_settings, save_settings

    machine = current_machine_name()
    save_settings(
        {
            "office_pc_path": r"\\OFFICE-PC\D$\MosPlaceRadioPlatform",
            "radio_pc_path": r"V:\\",
            "platform_folder": r"V:\\",
            "output_folder": r"V:\Documentation\InventoryReports",
        }
    )
    loaded = load_settings()
    if loaded["platform_folder"] != r"V:\\":
        raise RuntimeError("Machine-specific platform path was not saved correctly")
    store_path = INVENTORY_ROOT / "inventory_settings.json"
    if store_path.exists():
        text = store_path.read_text(encoding="utf-8")
        if machine not in text:
            raise RuntimeError("Settings were not stored under the current machine profile")


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
        if engine._thread:
            engine._thread.join(timeout=120)
    if done["error"]:
        raise RuntimeError(done["error"])
    if not done["ok"]:
        raise RuntimeError("Scan did not complete")


def test_report_generation() -> None:
    from app.core.models import InventorySnapshot

    with tempfile.TemporaryDirectory() as tmp:
        snapshot = InventorySnapshot(
            scanned_at="now",
            office_pc=".",
            radio_pc=".",
            platform_folder=".",
            output_folder=tmp,
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


def main() -> int:
    test_settings_roundtrip()
    test_duplicate_detection()
    test_report_generation()
    test_local_scan()
    print("Inventory verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

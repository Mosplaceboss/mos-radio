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
    test_duplicate_detection()
    test_report_generation()
    test_local_scan()
    print("Inventory verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

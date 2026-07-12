"""Background scan orchestration."""

from __future__ import annotations

import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

from app.core.compare import compare_folder_sets, find_duplicate_files, find_duplicate_folders
from app.core.file_scanner import FileInventoryScanner
from app.core.models import ComponentHit, InventorySnapshot
from app.core.paths_util import resolve_computer_root
from app.core.recommendations import build_recommendations
from app.core.reports import write_reports
from app.core.system_collectors import (
    collect_processes,
    collect_scheduled_tasks,
    collect_services,
    enrich_service_details,
)


class ScanEngine:
    def __init__(
        self,
        *,
        on_progress: Callable[[str, float, str], None] | None = None,
        on_complete: Callable[[InventorySnapshot, dict[str, str]], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        self._on_progress = on_progress or (lambda _m, _p, _e: None)
        self._on_complete = on_complete or (lambda _s, _p: None)
        self._on_error = on_error or (lambda _e: None)
        self._cancel = threading.Event()
        self._thread: threading.Thread | None = None
        self._started = 0.0

    def cancel(self) -> None:
        self._cancel.set()

    def start(
        self,
        *,
        office_pc: str,
        radio_pc: str,
        platform_folder: str,
        output_folder: str,
    ) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._cancel.clear()
        self._started = time.perf_counter()
        self._thread = threading.Thread(
            target=self._run,
            args=(office_pc, radio_pc, platform_folder, output_folder),
            daemon=True,
            name="inventory-scan",
        )
        self._thread.start()

    def _progress(self, message: str, fraction: float) -> None:
        elapsed = time.perf_counter() - self._started
        if fraction > 0.02:
            remaining = elapsed * (1.0 - fraction) / fraction
            eta = f"{int(remaining)}s remaining"
        else:
            eta = "estimating..."
        self._on_progress(message, min(max(fraction, 0.0), 1.0), eta)

    def _run(self, office_pc: str, radio_pc: str, platform_folder: str, output_folder: str) -> None:
        try:
            snapshot = InventorySnapshot(
                scanned_at=datetime.now().isoformat(timespec="seconds"),
                office_pc=office_pc,
                radio_pc=radio_pc,
                platform_folder=platform_folder,
                output_folder=output_folder,
            )
            scanner = FileInventoryScanner(
                progress_callback=lambda msg, frac: self._progress(msg, frac * 0.55),
                cancel_check=self._cancel.is_set,
            )

            office_label, office_roots = resolve_computer_root(office_pc)
            radio_label, radio_roots = resolve_computer_root(radio_pc)
            platform_path = Path(platform_folder) if platform_folder else None
            platform_roots = [platform_path] if platform_path and platform_path.exists() else []

            if not office_roots:
                office_roots = [Path.cwd()]
            if not radio_roots:
                radio_roots = office_roots[:]

            self._progress("Scanning Office PC", 0.05)
            d1, f1, files1, comps1 = scanner.scan_roots(office_label or "Office", office_roots)
            snapshot.drives.extend(d1)
            snapshot.folders.extend(f1)
            snapshot.files.extend(files1)

            if self._cancel.is_set():
                return

            self._progress("Scanning Radio PC", 0.25)
            d2, f2, files2, comps2 = scanner.scan_roots(radio_label or "Radio", radio_roots)
            snapshot.drives.extend(d2)
            snapshot.folders.extend(f2)
            snapshot.files.extend(files2)

            if platform_roots:
                self._progress("Scanning Platform Folder", 0.4)
                _, f3, files3, comps3 = scanner.scan_roots("Platform", platform_roots)
                snapshot.folders.extend(f3)
                snapshot.files.extend(files3)
                comps1 += comps3
            else:
                files3 = []
                comps3 = []

            for name, path, computer in comps1 + comps2 + comps3:
                snapshot.components.append(ComponentHit(name=name, path=path, computer=computer, kind="file"))

            self._progress("Collecting scheduled tasks", 0.55)
            snapshot.tasks.extend(collect_scheduled_tasks(office_label or office_pc))
            snapshot.tasks.extend(collect_scheduled_tasks(radio_label or radio_pc))

            self._progress("Collecting processes and services", 0.68)
            snapshot.processes.extend(collect_processes(office_label or office_pc))
            snapshot.processes.extend(collect_processes(radio_label or radio_pc))
            snapshot.services.extend(collect_services(office_label or office_pc))
            enrich_service_details(snapshot.services)

            self._progress("Comparing folders and duplicates", 0.78)
            office_files = [f for f in snapshot.files if f.computer in {office_label, "Office"} or f.computer == office_pc]
            radio_files = [f for f in snapshot.files if f.computer in {radio_label, "Radio"} or f.computer == radio_pc]
            platform_files = [f for f in snapshot.files if f.computer == "Platform"]
            snapshot.duplicates.extend(find_duplicate_files(snapshot.files))
            snapshot.duplicates.extend(find_duplicate_folders([f.path for f in snapshot.folders]))
            snapshot.comparisons = compare_folder_sets(
                str(office_roots[0]) if office_roots else "",
                str(radio_roots[0]) if radio_roots else "",
                platform_folder,
                office_files,
                radio_files,
                platform_files,
            )

            self._progress("Building recommendations", 0.9)
            snapshot.recommendations = build_recommendations(
                snapshot.files,
                [f.path for f in snapshot.folders],
                snapshot.duplicates,
                snapshot.comparisons,
            )

            self._progress("Writing reports", 0.95)
            report_paths = write_reports(snapshot)
            self._progress("Scan complete", 1.0)
            self._on_complete(snapshot, report_paths)
        except Exception as exc:
            self._on_error(exc)

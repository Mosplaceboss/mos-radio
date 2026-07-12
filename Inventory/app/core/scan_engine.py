"""Background scan orchestration."""

from __future__ import annotations

import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

from app.core.compare import compare_folder_sets, find_duplicate_files, find_duplicate_folders
from app.core.file_scanner import FileInventoryScanner
from app.core.models import ComponentHit, InventorySnapshot, ScanError
from app.core.paths_util import resolve_computer_root
from app.core.recommendations import build_recommendations
from app.core.reports import write_checkpoint, write_reports
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

    def join(self, timeout: float | None = None) -> None:
        if self._thread:
            self._thread.join(timeout=timeout)

    def _progress(self, message: str, fraction: float) -> None:
        elapsed = time.perf_counter() - self._started
        if fraction > 0.02:
            remaining = elapsed * (1.0 - fraction) / fraction
            eta = f"{int(remaining)}s remaining"
        else:
            eta = "estimating..."
        self._on_progress(message, min(max(fraction, 0.0), 1.0), eta)

    def _record_resolution_errors(self, snapshot: InventorySnapshot, computer: str, errors: list[str]) -> None:
        for error in errors:
            snapshot.scan_errors.append(
                ScanError(
                    computer=computer,
                    path=computer,
                    error=error,
                    phase="resolve",
                )
            )

    def _checkpoint(self, snapshot: InventorySnapshot, message: str) -> None:
        snapshot.progress_message = message
        write_checkpoint(snapshot)

    def _finish_partial(self, snapshot: InventorySnapshot, status: str, message: str) -> dict[str, str]:
        snapshot.status = status
        snapshot.progress_message = message
        return write_reports(snapshot, partial=True)

    def _run(self, office_pc: str, radio_pc: str, platform_folder: str, output_folder: str) -> None:
        snapshot = InventorySnapshot(
            scanned_at=datetime.now().isoformat(timespec="seconds"),
            office_pc=office_pc,
            radio_pc=radio_pc,
            platform_folder=platform_folder,
            output_folder=output_folder,
            status="running",
            progress_message="Scan started",
        )
        try:
            self._checkpoint(snapshot, "Resolving scan targets")

            def record_error(error: ScanError) -> None:
                snapshot.scan_errors.append(error)

            scanner = FileInventoryScanner(
                progress_callback=lambda msg, frac: self._progress(msg, frac * 0.55),
                cancel_check=self._cancel.is_set,
                error_callback=record_error,
                checkpoint_callback=lambda: self._checkpoint(snapshot, f"Indexed {len(snapshot.files):,} files"),
            )

            office_label, office_roots, office_errors = resolve_computer_root(office_pc)
            radio_label, radio_roots, radio_errors = resolve_computer_root(radio_pc)
            self._record_resolution_errors(snapshot, office_label or office_pc, office_errors)
            self._record_resolution_errors(snapshot, radio_label or radio_pc, radio_errors)

            platform_path = Path(platform_folder) if platform_folder else None
            platform_roots = [platform_path] if platform_path and platform_path.exists() else []
            if platform_folder and not platform_roots:
                snapshot.scan_errors.append(
                    ScanError(
                        computer="Platform",
                        path=platform_folder,
                        error="Platform folder does not exist or is not reachable.",
                        phase="resolve",
                    )
                )

            self._progress("Scanning Office PC", 0.05)
            snapshot.progress_message = "Scanning Office PC"
            d1, f1, files1, comps1 = scanner.scan_roots(
                office_label or office_pc,
                office_roots,
                target_name=office_pc,
            )
            snapshot.drives.extend(d1)
            snapshot.folders.extend(f1)
            snapshot.files.extend(files1)
            self._checkpoint(snapshot, f"Office PC indexed ({len(snapshot.files):,} files)")

            if self._cancel.is_set():
                self._on_complete(snapshot, self._finish_partial(snapshot, "cancelled", "Scan cancelled after Office PC"))
                return

            self._progress("Scanning Radio PC", 0.25)
            snapshot.progress_message = "Scanning Radio PC"
            d2, f2, files2, comps2 = scanner.scan_roots(
                radio_label or radio_pc,
                radio_roots,
                target_name=radio_pc,
            )
            snapshot.drives.extend(d2)
            snapshot.folders.extend(f2)
            snapshot.files.extend(files2)
            self._checkpoint(snapshot, f"Radio PC indexed ({len(snapshot.files):,} files)")

            if self._cancel.is_set():
                self._on_complete(snapshot, self._finish_partial(snapshot, "cancelled", "Scan cancelled after Radio PC"))
                return

            if platform_roots:
                self._progress("Scanning Platform Folder", 0.4)
                snapshot.progress_message = "Scanning Platform Folder"
                _, f3, files3, comps3 = scanner.scan_roots("Platform", platform_roots, target_name=platform_folder)
                snapshot.folders.extend(f3)
                snapshot.files.extend(files3)
                comps1 += comps3
                self._checkpoint(snapshot, f"Platform indexed ({len(snapshot.files):,} files)")
            else:
                files3 = []
                comps3 = []

            for name, path, computer in comps1 + comps2 + comps3:
                snapshot.components.append(ComponentHit(name=name, path=path, computer=computer, kind="file"))

            self._progress("Collecting scheduled tasks", 0.55)
            snapshot.progress_message = "Collecting scheduled tasks"
            office_tasks, office_task_errors = collect_scheduled_tasks(office_label or office_pc)
            radio_tasks, radio_task_errors = collect_scheduled_tasks(radio_label or radio_pc)
            snapshot.tasks.extend(office_tasks)
            snapshot.tasks.extend(radio_tasks)
            snapshot.scan_errors.extend(office_task_errors)
            snapshot.scan_errors.extend(radio_task_errors)
            self._checkpoint(snapshot, "Scheduled tasks collected")

            self._progress("Collecting processes and services", 0.68)
            snapshot.progress_message = "Collecting processes and services"
            office_processes, office_proc_errors = collect_processes(office_label or office_pc)
            radio_processes, radio_proc_errors = collect_processes(radio_label or radio_pc)
            office_services, office_svc_errors = collect_services(office_label or office_pc)
            radio_services, radio_svc_errors = collect_services(radio_label or radio_pc)
            snapshot.processes.extend(office_processes)
            snapshot.processes.extend(radio_processes)
            snapshot.services.extend(office_services)
            snapshot.services.extend(radio_services)
            snapshot.scan_errors.extend(office_proc_errors)
            snapshot.scan_errors.extend(radio_proc_errors)
            snapshot.scan_errors.extend(office_svc_errors)
            snapshot.scan_errors.extend(radio_svc_errors)
            enrich_service_details(snapshot.services)
            self._checkpoint(snapshot, "Processes and services collected")

            self._progress("Comparing folders and duplicates", 0.78)
            snapshot.progress_message = "Comparing folders and duplicates"
            office_files = [f for f in snapshot.files if f.computer in {office_label, office_pc, "Office"}]
            radio_files = [f for f in snapshot.files if f.computer in {radio_label, radio_pc, "Radio", "MosPlaceRadio"}]
            platform_files = [f for f in snapshot.files if f.computer == "Platform"]
            snapshot.duplicates.extend(find_duplicate_files(snapshot.files))
            snapshot.duplicates.extend(find_duplicate_folders([f.path for f in snapshot.folders]))
            snapshot.comparisons = compare_folder_sets(
                str(office_roots[0]) if office_roots else office_pc,
                str(radio_roots[0]) if radio_roots else radio_pc,
                platform_folder,
                office_files,
                radio_files,
                platform_files,
            )

            self._progress("Building recommendations", 0.9)
            snapshot.progress_message = "Building recommendations"
            snapshot.recommendations = build_recommendations(
                snapshot.files,
                [f.path for f in snapshot.folders],
                snapshot.duplicates,
                snapshot.comparisons,
            )

            self._progress("Writing reports", 0.95)
            snapshot.progress_message = "Writing reports"
            snapshot.status = "complete"
            report_paths = write_reports(snapshot)
            self._progress("Scan complete", 1.0)
            snapshot.progress_message = "Scan complete"
            self._on_complete(snapshot, report_paths)
        except Exception as exc:
            snapshot.status = "failed"
            snapshot.progress_message = str(exc)
            snapshot.scan_errors.append(
                ScanError(
                    computer="Inventory",
                    path=output_folder,
                    error=str(exc),
                    phase="scan_engine",
                )
            )
            try:
                self._finish_partial(snapshot, "failed", str(exc))
            except OSError:
                pass
            self._on_error(exc)

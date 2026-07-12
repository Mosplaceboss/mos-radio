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
from app.core.paths_util import resolve_scan_folder, sanitize_folder_path
from app.core.recommendations import build_recommendations
from app.core.reports import write_checkpoint, write_reports
from app.core.settings_store import OFFICE_PLATFORM_PHYSICAL, sanitize_folder_list
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
        office_folders: list[str],
        radio_folders: list[str],
        output_folder: str,
    ) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._cancel.clear()
        self._started = time.perf_counter()
        self._thread = threading.Thread(
            target=self._run,
            args=(office_folders, radio_folders, output_folder),
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

    def _checkpoint(self, snapshot: InventorySnapshot, message: str) -> None:
        snapshot.progress_message = message
        try:
            write_checkpoint(snapshot)
        except (OSError, PermissionError) as exc:
            snapshot.scan_errors.append(
                ScanError(
                    computer="Inventory",
                    path=snapshot.output_folder,
                    error=f"Checkpoint save failed: {exc}",
                    phase="reports",
                )
            )

    def _finish_partial(self, snapshot: InventorySnapshot, status: str, message: str) -> dict[str, str]:
        snapshot.status = status
        snapshot.progress_message = message
        try:
            return write_reports(snapshot, partial=True)
        except (OSError, PermissionError) as exc:
            snapshot.scan_errors.append(
                ScanError(
                    computer="Inventory",
                    path=snapshot.output_folder,
                    error=f"Partial report save failed: {exc}",
                    phase="reports",
                )
            )
            return {}

    def _scan_selected_folders(
        self,
        scanner: FileInventoryScanner,
        snapshot: InventorySnapshot,
        folders: list[str],
        *,
        label: str,
        include_drives: bool,
    ) -> list[tuple[str, str, str]]:
        components: list[tuple[str, str, str]] = []
        drives_added = False

        for folder in folders:
            if self._cancel.is_set():
                break

            cleaned = sanitize_folder_path(folder)
            if not cleaned:
                if folder.strip():
                    snapshot.scan_errors.append(
                        ScanError(
                            computer=label,
                            path=folder,
                            error="Administrative shares are not supported.",
                            phase="resolve",
                        )
                    )
                continue

            _folder_label, roots, errors = resolve_scan_folder(cleaned, label=label)
            for error in errors:
                snapshot.scan_errors.append(
                    ScanError(
                        computer=label,
                        path=cleaned,
                        error=error,
                        phase="resolve",
                    )
                )

            self._progress(f"Scanning {label}: {cleaned}", 0.0)
            d, f, files, comps = scanner.scan_roots(
                label,
                roots,
                folder_path=cleaned,
                include_drives=include_drives and not drives_added,
            )
            drives_added = drives_added or bool(d)
            snapshot.drives.extend(d)
            snapshot.folders.extend(f)
            snapshot.files.extend(files)
            components.extend(comps)
            self._checkpoint(snapshot, f"{label} indexed ({len(snapshot.files):,} files)")

        return components

    def _run(self, office_folders: list[str], radio_folders: list[str], output_folder: str) -> None:
        office_list = sanitize_folder_list(office_folders)
        radio_list = sanitize_folder_list(radio_folders)
        platform_folder = next(
            (folder for folder in office_list if folder.lower() == OFFICE_PLATFORM_PHYSICAL.lower()),
            OFFICE_PLATFORM_PHYSICAL,
        )

        snapshot = InventorySnapshot(
            scanned_at=datetime.now().isoformat(timespec="seconds"),
            office_pc=" | ".join(office_list),
            radio_pc=" | ".join(radio_list),
            platform_folder=platform_folder,
            output_folder=output_folder,
            status="running",
            progress_message="Scan started",
        )
        try:
            self._checkpoint(snapshot, "Preparing selected folders")

            def record_error(error: ScanError) -> None:
                snapshot.scan_errors.append(error)

            scanner = FileInventoryScanner(
                progress_callback=lambda msg, frac: self._progress(msg, frac * 0.55),
                cancel_check=self._cancel.is_set,
                error_callback=record_error,
                checkpoint_callback=lambda: self._checkpoint(snapshot, f"Indexed {len(snapshot.files):,} files"),
            )

            self._progress("Scanning Office PC folders", 0.05)
            snapshot.progress_message = "Scanning Office PC folders"
            office_components = self._scan_selected_folders(
                scanner,
                snapshot,
                office_list,
                label="Office",
                include_drives=True,
            )

            if self._cancel.is_set():
                self._on_complete(snapshot, self._finish_partial(snapshot, "cancelled", "Scan cancelled after Office folders"))
                return

            self._progress("Scanning Radio PC folders", 0.3)
            snapshot.progress_message = "Scanning Radio PC folders"
            radio_components = self._scan_selected_folders(
                scanner,
                snapshot,
                radio_list,
                label="Radio",
                include_drives=False,
            )

            if self._cancel.is_set():
                self._on_complete(snapshot, self._finish_partial(snapshot, "cancelled", "Scan cancelled after Radio folders"))
                return

            for name, path, computer in office_components + radio_components:
                snapshot.components.append(ComponentHit(name=name, path=path, computer=computer, kind="file"))

            from app.core.settings_store import current_machine_name

            host = current_machine_name()
            self._progress("Collecting local scheduled tasks", 0.55)
            snapshot.progress_message = "Collecting local scheduled tasks"
            tasks, task_errors = collect_scheduled_tasks(host)
            snapshot.tasks.extend(tasks)
            snapshot.scan_errors.extend(task_errors)
            self._checkpoint(snapshot, "Scheduled tasks collected")

            self._progress("Collecting local processes and services", 0.68)
            snapshot.progress_message = "Collecting local processes and services"
            processes, proc_errors = collect_processes(host)
            services, svc_errors = collect_services(host)
            snapshot.processes.extend(processes)
            snapshot.services.extend(services)
            snapshot.scan_errors.extend(proc_errors)
            snapshot.scan_errors.extend(svc_errors)
            enrich_service_details(snapshot.services)
            self._checkpoint(snapshot, "Processes and services collected")

            self._progress("Comparing folders and duplicates", 0.78)
            snapshot.progress_message = "Comparing folders and duplicates"
            office_files = [f for f in snapshot.files if f.computer == "Office"]
            radio_files = [f for f in snapshot.files if f.computer == "Radio"]
            platform_files = [
                f for f in office_files if OFFICE_PLATFORM_PHYSICAL.lower() in f.path.lower()
            ]
            snapshot.duplicates.extend(find_duplicate_files(snapshot.files))
            snapshot.duplicates.extend(find_duplicate_folders([f.path for f in snapshot.folders]))
            snapshot.comparisons = compare_folder_sets(
                office_list[0] if office_list else "",
                radio_list[0] if radio_list else "",
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
        except (OSError, PermissionError, Exception) as exc:
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
            report_paths = self._finish_partial(snapshot, "failed", str(exc))
            self._on_complete(snapshot, report_paths)

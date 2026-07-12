"""Read-only file and folder inventory scanner."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Callable

from app.core.models import DriveRecord, FileRecord, FolderRecord, ScanError
from app.core.paths_util import list_drives_for_folder
from app.core.safety import assert_read_only_path

CATEGORY_RULES = {
    "python": {".py"},
    "powershell": {".ps1"},
    "zip": {".zip"},
    "config": {".json", ".ini", ".yaml", ".yml", ".xml", ".config"},
    "audio": {".wav", ".mp3"},
    "logs": {".log", ".txt"},
}

COMPONENT_PATTERNS = {
    "RadioDJ": ("radiodj", "radio dj"),
    "Voicebox": ("voicebox",),
    "MosLiveDJ": ("moslivedj", "livedj", "mos-live-dj"),
    "MosNews": ("mosnews", "news"),
    "MoRequestsWatcher": ("morequestswatcher", "requests watcher", "request watcher"),
    "Studio": ("moplace studio", "mos-radio", "moplacestudio"),
    "Website": ("website", "wwwroot", "htdocs"),
    "Python": ("python.exe", "pythonw.exe", "venv", "virtualenv"),
}


def categorize(extension: str, filename: str) -> str:
    ext = extension.lower()
    for category, extensions in CATEGORY_RULES.items():
        if ext in extensions:
            return category
    lower_name = filename.lower()
    if ext == ".zip":
        return "zip"
    if "backup" in lower_name:
        return "possible_backup"
    return "other"


def detect_component(path: Path) -> str | None:
    text = str(path).lower()
    name = path.name.lower()
    for component, patterns in COMPONENT_PATTERNS.items():
        if any(pattern in text or pattern in name for pattern in patterns):
            return component
    return None


class FileInventoryScanner:
    def __init__(
        self,
        progress_callback=None,
        cancel_check=None,
        error_callback: Callable[[ScanError], None] | None = None,
        checkpoint_callback: Callable[[], None] | None = None,
    ) -> None:
        self._progress = progress_callback or (lambda _m, _p: None)
        self._cancel = cancel_check or (lambda: False)
        self._record_error = error_callback or (lambda _error: None)
        self._checkpoint = checkpoint_callback or (lambda: None)

    def scan_roots(
        self,
        computer: str,
        roots: list[Path],
        *,
        folder_path: str = "",
        include_drives: bool = True,
    ) -> tuple[list[DriveRecord], list[FolderRecord], list[FileRecord], list[tuple[str, str, str]]]:
        drives: list[DriveRecord] = []
        if include_drives:
            drives = [
                DriveRecord(letter=letter, label=label, total_bytes=total, free_bytes=free, computer=computer)
                for letter, label, total, free in list_drives_for_folder(folder_path or str(roots[0]) if roots else "")
            ]
        folders: list[FolderRecord] = []
        files: list[FileRecord] = []
        components: list[tuple[str, str, str]] = []

        if not roots:
            self._record_error(
                ScanError(
                    computer=computer,
                    path=folder_path or computer,
                    error="No scan folder was available.",
                    phase="file_scan",
                )
            )
            return drives, folders, files, components

        total_roots = max(len(roots), 1)
        for index, root in enumerate(roots):
            if self._cancel():
                break
            self._progress(f"Scanning {computer}: {root}", index / total_roots)
            self._walk_root(computer, root, folders, files, components)

        return drives, folders, files, components

    def _walk_root(
        self,
        computer: str,
        root: Path,
        folders: list[FolderRecord],
        files: list[FileRecord],
        components: list[tuple[str, str, str]],
    ) -> None:
        if not root.exists():
            self._record_error(
                ScanError(
                    computer=computer,
                    path=str(root),
                    error="Root path does not exist.",
                    phase="file_scan",
                )
            )
            return
        try:
            assert_read_only_path(root)
        except (OSError, PermissionError) as exc:
            self._record_error(
                ScanError(
                    computer=computer,
                    path=str(root),
                    error=str(exc),
                    phase="file_scan",
                )
            )
            return

        def onerror(exc: OSError) -> None:
            self._record_error(
                ScanError(
                    computer=computer,
                    path=str(getattr(exc, "filename", root)),
                    error=str(exc),
                    phase="file_scan",
                )
            )

        try:
            walker = os.walk(root, topdown=True, onerror=onerror)
        except (OSError, PermissionError) as exc:
            self._record_error(
                ScanError(
                    computer=computer,
                    path=str(root),
                    error=str(exc),
                    phase="file_scan",
                )
            )
            return

        for dirpath, _dirnames, filenames in walker:
            if self._cancel():
                return
            current = Path(dirpath)
            file_count = 0
            total_size = 0

            for filename in filenames:
                if self._cancel():
                    return
                file_path = current / filename
                try:
                    assert_read_only_path(file_path)
                    stat = file_path.stat()
                except (OSError, PermissionError) as exc:
                    self._record_error(
                        ScanError(
                            computer=computer,
                            path=str(file_path),
                            error=str(exc),
                            phase="file_scan",
                        )
                    )
                    continue

                extension = file_path.suffix
                category = categorize(extension, filename)
                record = FileRecord(
                    path=str(file_path),
                    filename=filename,
                    extension=extension.lower(),
                    size=stat.st_size,
                    created=_fmt_time(stat.st_ctime),
                    modified=_fmt_time(stat.st_mtime),
                    computer=computer,
                    category=category,
                )
                files.append(record)
                file_count += 1
                total_size += stat.st_size

                component = detect_component(file_path)
                if component:
                    components.append((component, str(file_path), computer))

            folders.append(FolderRecord(path=str(current), computer=computer, file_count=file_count, total_size=total_size))

            if len(files) % 250 == 0:
                self._progress(f"Indexed {len(files):,} files on {computer}", 0.0)
            if len(files) % 500 == 0:
                self._checkpoint()


def _fmt_time(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")

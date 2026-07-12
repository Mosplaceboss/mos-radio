"""Read-only file and folder inventory scanner."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from app.core.models import DriveRecord, FileRecord, FolderRecord
from app.core.paths_util import list_local_drives
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
    def __init__(self, progress_callback=None, cancel_check=None) -> None:
        self._progress = progress_callback or (lambda _m, _p: None)
        self._cancel = cancel_check or (lambda: False)

    def scan_roots(self, computer: str, roots: list[Path]) -> tuple[list[DriveRecord], list[FolderRecord], list[FileRecord], list[tuple[str, str, str]]]:
        drives = [
            DriveRecord(letter=letter, label=label, total_bytes=total, free_bytes=free, computer=computer)
            for letter, label, total, free in list_local_drives(computer)
        ]
        folders: list[FolderRecord] = []
        files: list[FileRecord] = []
        components: list[tuple[str, str, str]] = []

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
            return
        assert_read_only_path(root)

        for dirpath, dirnames, filenames in os.walk(root, topdown=True, onerror=lambda _e: None):
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
                except OSError:
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


def _fmt_time(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")

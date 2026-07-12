"""Data models for Mo's Place Inventory."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FileRecord:
    path: str
    filename: str
    extension: str
    size: int
    created: str
    modified: str
    computer: str
    category: str = "other"


@dataclass
class FolderRecord:
    path: str
    computer: str
    file_count: int = 0
    total_size: int = 0


@dataclass
class DriveRecord:
    letter: str
    label: str
    total_bytes: int
    free_bytes: int
    computer: str


@dataclass
class TaskRecord:
    name: str
    program: str
    arguments: str
    working_directory: str
    status: str
    trigger: str
    computer: str


@dataclass
class ProcessRecord:
    name: str
    executable: str
    command_line: str
    working_directory: str
    computer: str


@dataclass
class ServiceRecord:
    name: str
    status: str
    startup_type: str
    executable: str
    computer: str


@dataclass
class ComponentHit:
    name: str
    path: str
    computer: str
    kind: str


@dataclass
class DuplicateGroup:
    kind: str
    key: str
    paths: list[str] = field(default_factory=list)


@dataclass
class FolderComparisonRow:
    relative_path: str
    office_status: str
    radio_status: str
    platform_status: str
    detail: str = ""


@dataclass
class ScanError:
    computer: str
    path: str
    error: str
    phase: str = "file_scan"


@dataclass
class Recommendation:
    category: str
    severity: str
    title: str
    detail: str
    paths: list[str] = field(default_factory=list)


@dataclass
class InventorySnapshot:
    scanned_at: str
    office_pc: str
    radio_pc: str
    platform_folder: str
    output_folder: str
    drives: list[DriveRecord] = field(default_factory=list)
    folders: list[FolderRecord] = field(default_factory=list)
    files: list[FileRecord] = field(default_factory=list)
    tasks: list[TaskRecord] = field(default_factory=list)
    processes: list[ProcessRecord] = field(default_factory=list)
    services: list[ServiceRecord] = field(default_factory=list)
    components: list[ComponentHit] = field(default_factory=list)
    duplicates: list[DuplicateGroup] = field(default_factory=list)
    comparisons: list[FolderComparisonRow] = field(default_factory=list)
    recommendations: list[Recommendation] = field(default_factory=list)
    scan_errors: list[ScanError] = field(default_factory=list)
    status: str = "running"
    progress_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        def _list(items: list[Any]) -> list[dict[str, Any]]:
            return [item.__dict__ for item in items]

        return {
            "scanned_at": self.scanned_at,
            "office_pc": self.office_pc,
            "radio_pc": self.radio_pc,
            "platform_folder": self.platform_folder,
            "output_folder": self.output_folder,
            "drives": _list(self.drives),
            "folders": _list(self.folders),
            "files": _list(self.files),
            "tasks": _list(self.tasks),
            "processes": _list(self.processes),
            "services": _list(self.services),
            "components": _list(self.components),
            "duplicates": _list(self.duplicates),
            "comparisons": _list(self.comparisons),
            "recommendations": _list(self.recommendations),
            "scan_errors": _list(self.scan_errors),
            "status": self.status,
            "progress_message": self.progress_message,
        }

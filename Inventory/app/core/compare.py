"""Duplicate and folder comparison analysis."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from pathlib import Path

from app.core.models import DuplicateGroup, FileRecord, FolderComparisonRow


def find_duplicate_files(files: list[FileRecord]) -> list[DuplicateGroup]:
    by_name: dict[tuple[str, int], list[str]] = defaultdict(list)
    by_hash: dict[str, list[str]] = defaultdict(list)

    for record in files:
        key = (record.filename.lower(), record.size)
        by_name[key].append(record.path)
        digest = _quick_hash(record)
        by_hash[digest].append(record.path)

    groups: list[DuplicateGroup] = []
    for key, paths in by_name.items():
        if len(paths) > 1:
            groups.append(DuplicateGroup(kind="duplicate_name_size", key=str(key), paths=sorted(paths)))

    for digest, paths in by_hash.items():
        if len(paths) > 1:
            groups.append(DuplicateGroup(kind="duplicate_content", key=digest, paths=sorted(paths)))

    return groups


def find_duplicate_folders(folders: list[str]) -> list[DuplicateGroup]:
    by_name: dict[str, list[str]] = defaultdict(list)
    for folder in folders:
        by_name[Path(folder).name.lower()].append(folder)
    return [
        DuplicateGroup(kind="duplicate_folder_name", key=name, paths=sorted(paths))
        for name, paths in by_name.items()
        if len(paths) > 1
    ]


def compare_folder_sets(
    office_root: str,
    radio_root: str,
    platform_root: str,
    office_files: list[FileRecord],
    radio_files: list[FileRecord],
    platform_files: list[FileRecord],
) -> list[FolderComparisonRow]:
    office_map = _relative_map(office_root, office_files)
    radio_map = _relative_map(radio_root, radio_files)
    platform_map = _relative_map(platform_root, platform_files)
    all_paths = sorted(set(office_map) | set(radio_map) | set(platform_map))

    rows: list[FolderComparisonRow] = []
    for rel in all_paths:
        office = office_map.get(rel)
        radio = radio_map.get(rel)
        platform = platform_map.get(rel)
        office_status = _status_label(office)
        radio_status = _status_label(radio)
        platform_status = _status_label(platform)
        detail = _comparison_detail(office, radio, platform)
        rows.append(
            FolderComparisonRow(
                relative_path=rel,
                office_status=office_status,
                radio_status=radio_status,
                platform_status=platform_status,
                detail=detail,
            )
        )
    return rows


def _relative_map(root: str, files: list[FileRecord]) -> dict[str, FileRecord]:
    root_path = Path(root) if root else None
    mapping: dict[str, FileRecord] = {}
    for record in files:
        path = Path(record.path)
        if root_path and root_path.exists():
            try:
                rel = str(path.relative_to(root_path)).replace("\\", "/")
            except ValueError:
                rel = record.filename
        else:
            rel = record.filename
        mapping[rel.lower()] = record
    return mapping


def _status_label(record: FileRecord | None) -> str:
    if record is None:
        return "Missing"
    return "Present"


def _comparison_detail(office: FileRecord | None, radio: FileRecord | None, platform: FileRecord | None) -> str:
    present = [item for item in (office, radio, platform) if item is not None]
    if len(present) <= 1:
        return "Only one copy found"
    newest = max(present, key=lambda item: item.modified)
    oldest = min(present, key=lambda item: item.modified)
    if newest.modified != oldest.modified:
        return f"Newest: {newest.modified} · Oldest: {oldest.modified}"
    sizes = {item.size for item in present}
    if len(sizes) > 1:
        return "Different versions (size mismatch)"
    return "Same"


def _quick_hash(record: FileRecord) -> str:
    payload = f"{record.filename.lower()}|{record.size}|{record.modified}".encode("utf-8")
    return hashlib.sha1(payload).hexdigest()

"""Recommendation engine for inventory results."""

from __future__ import annotations

from pathlib import Path

from app.core.models import DuplicateGroup, FileRecord, FolderComparisonRow, Recommendation


DEV_MARKERS = ("dev", "development", "test", "scratch", "tmp", ".git", "node_modules", "__pycache__")
PROD_MARKERS = ("production", "prod", "release", "deploy", "live", "automation")
ARCHIVE_MARKERS = ("archive", "backup", "old", "retired")


def build_recommendations(
    files: list[FileRecord],
    folders: list[str],
    duplicates: list[DuplicateGroup],
    comparisons: list[FolderComparisonRow],
) -> list[Recommendation]:
    recs: list[Recommendation] = []

    recs.extend(_duplicate_recommendations(duplicates))
    recs.extend(_folder_role_recommendations(folders))
    recs.extend(_script_and_config_recommendations(files))
    recs.extend(_comparison_recommendations(comparisons))
    recs.extend(_missing_reference_recommendations(files))

    return recs


def _duplicate_recommendations(duplicates: list[DuplicateGroup]) -> list[Recommendation]:
    recs: list[Recommendation] = []
    for group in duplicates:
        if group.kind.startswith("duplicate_folder"):
            recs.append(
                Recommendation(
                    category="Duplicate folders",
                    severity="medium",
                    title=f"Duplicate folder name: {group.key}",
                    detail="Multiple folders share the same name on different paths.",
                    paths=group.paths,
                )
            )
        else:
            recs.append(
                Recommendation(
                    category="Duplicate files",
                    severity="medium",
                    title=f"Duplicate file group: {group.key}",
                    detail="Multiple files appear to be copies of the same content.",
                    paths=group.paths,
                )
            )
    return recs


def _folder_role_recommendations(folders: list[str]) -> list[Recommendation]:
    recs: list[Recommendation] = []
    for folder in folders:
        lower = folder.lower()
        if any(marker in lower for marker in DEV_MARKERS):
            recs.append(
                Recommendation(
                    category="Development folders",
                    severity="info",
                    title="Development folder detected",
                    detail=folder,
                    paths=[folder],
                )
            )
        if any(marker in lower for marker in PROD_MARKERS):
            recs.append(
                Recommendation(
                    category="Production folders",
                    severity="info",
                    title="Production folder detected",
                    detail=folder,
                    paths=[folder],
                )
            )
        if any(marker in lower for marker in ARCHIVE_MARKERS):
            recs.append(
                Recommendation(
                    category="Archive candidates",
                    severity="low",
                    title="Archive/backup folder detected",
                    detail=folder,
                    paths=[folder],
                )
            )
    return recs


def _script_and_config_recommendations(files: list[FileRecord]) -> list[Recommendation]:
    scripts = [f.path for f in files if f.category in {"python", "powershell"}]
    configs = [f.path for f in files if f.category == "config"]
    recs: list[Recommendation] = []

    by_name: dict[str, list[str]] = {}
    for path in scripts + configs:
        by_name.setdefault(Path(path).name.lower(), []).append(path)

    for name, paths in by_name.items():
        if len(paths) > 1:
            category = "Duplicate scripts" if name.endswith((".py", ".ps1")) else "Duplicate configurations"
            recs.append(
                Recommendation(
                    category=category,
                    severity="medium",
                    title=f"Multiple copies of {name}",
                    detail="Review whether all copies are still required.",
                    paths=paths,
                )
            )
    return recs


def _comparison_recommendations(comparisons: list[FolderComparisonRow]) -> list[Recommendation]:
    recs: list[Recommendation] = []
    for row in comparisons:
        statuses = {row.office_status, row.radio_status, row.platform_status}
        if "Missing" in statuses and "Present" in statuses:
            recs.append(
                Recommendation(
                    category="Broken references",
                    severity="high",
                    title=f"Path mismatch: {row.relative_path}",
                    detail=row.detail or "One or more locations are missing this file.",
                    paths=[row.relative_path],
                )
            )
        if "Different versions" in (row.detail or ""):
            recs.append(
                Recommendation(
                    category="Different versions",
                    severity="medium",
                    title=f"Version drift: {row.relative_path}",
                    detail=row.detail,
                    paths=[row.relative_path],
                )
            )
    return recs


def _missing_reference_recommendations(files: list[FileRecord]) -> list[Recommendation]:
    recs: list[Recommendation] = []
    for record in files:
        if record.category == "config" and not Path(record.path).exists():
            recs.append(
                Recommendation(
                    category="Missing paths",
                    severity="high",
                    title="Missing configuration file",
                    detail=record.path,
                    paths=[record.path],
                )
            )
    return recs

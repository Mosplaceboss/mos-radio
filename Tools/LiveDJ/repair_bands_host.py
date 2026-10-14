"""Point Band Announcements schedule rows at Reverend JJ — never Mo.

LiveDJ speaks with the schedule Host voice. Band listing breaks that still
say Host=Mo keep airing in Mo's voice. This repair rewrites those rows to
Reverend JJ and sets EventType=Band Announcements when it was blank.

Default schedule:
  D:\\MPR\\Config\\Schedules\\weekday_schedule.csv

Usage:
  python Tools/LiveDJ/repair_bands_host.py
  python Tools/LiveDJ/repair_bands_host.py --schedule path\\to\\schedule.csv --dry-run
"""

from __future__ import annotations

import argparse
import csv
import shutil
from datetime import datetime
from pathlib import Path

import Bands

DEFAULT_SCHEDULE = Path(r"D:\MPR\Config\Schedules\weekday_schedule.csv")
BACKUP_DIR = Path(r"D:\MPR\Backups\Schedule")


def _load_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    return fieldnames, rows


def _write_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def _backup_dir_for(schedule_path: Path) -> Path:
    """Prefer the Office PC backup folder when it exists; otherwise sit next to the schedule."""
    if BACKUP_DIR.is_dir() or str(schedule_path).startswith(r"D:\MPR"):
        return BACKUP_DIR
    return schedule_path.parent / "Backups"


def repair(schedule_path: Path, *, dry_run: bool = False) -> int:
    if not schedule_path.is_file():
        raise FileNotFoundError(f"Schedule not found: {schedule_path}")
    fieldnames, rows = _load_rows(schedule_path)
    if "Host" not in fieldnames:
        raise ValueError(f"Schedule is missing a Host column: {schedule_path}")
    fixed, changed = Bands.repair_schedule_hosts(rows)
    if changed == 0:
        print(f"No Mo band-announcement rows to repair in {schedule_path}")
        return 0
    if dry_run:
        print(f"Would rewrite {changed} row(s) to Host={Bands.BANDS_HOST_DISPLAY}")
        for row in fixed:
            if Bands.row_looks_like_bands(row):
                print(
                    f"  {row.get('day_of_week') or row.get('Day') or '?'} "
                    f"{row.get('Time')} Host={row.get('Host')} "
                    f"EventType={row.get('EventType')}"
                )
        return changed
    backup_dir = _backup_dir_for(schedule_path)
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = backup_dir / f"weekday_schedule_bands_host_{stamp}.csv"
    shutil.copy2(schedule_path, backup)
    _write_rows(schedule_path, fieldnames, fixed)
    print(f"Rewrote {changed} row(s) to Host={Bands.BANDS_HOST_DISPLAY}")
    print(f"Backup: {backup}")
    return changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Set Band Announcements Host to Reverend JJ (not Mo)."
    )
    parser.add_argument("--schedule", type=Path, default=DEFAULT_SCHEDULE)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        repair(args.schedule, dry_run=args.dry_run)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

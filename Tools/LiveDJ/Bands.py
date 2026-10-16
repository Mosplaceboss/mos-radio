"""Tonight's bands file from Weekly Events.csv.

The sheet has two event shapes:

- Repeat=Weekly, Day=Wednesday, Date blank. It airs every matching weekday.
- Repeat=Date, Date=YYYY-MM-DD, Day blank. It airs only on that date.

Weekly rows were dropped whenever the generator required a Date cell.
Wednesday night is only a weekly row, so the bands file never got written.
On=No and a blank Event are skipped. Note rows are instructions, not shows.
A night with no Yes row does not write a file, and an older bands file is
removed so last night's shows are not left on the air.
An existing bands file is replaced when tonight has events.
Friday, Saturday, and Sunday band-rundown wav files are a separate product.
This sheet never writes or replaces those wav files.

Deploy to D:\\MPR\\Engines\\LiveDJ\\Scripts\\Bands.py on the Office PC.
Calendar search, first file that exists wins:
  D:\\MPR\\Weekly Events.csv
  D:\\MPR\\Events\\Weekly Events.csv
  D:\\MPR\\Knowledge\\Weekly Events.csv
  D:\\MPR\\Weekly Events\\Weekly Events.csv
  D:\\MPR\\Engines\\LiveDJ\\Weekly Events.csv
  D:\\MPR\\Engines\\LiveDJ\\Knowledge\\Weekly Events.csv
  D:\\MPR\\Engines\\LiveDJ\\Weekly Events\\Weekly Events.csv
Output: D:\\MPR\\Knowledge\\BandsTonight.txt
The Radio PC only has the news voices. This script does not read or write them.

LiveDJ's platform_paths.LIVE_BASE on the Office PC is D:\\MPR\\Engines\\LiveDJ.
That folder is the script home, not the calendar. The Office PC sheet is
D:\\MPR\\Events\\Weekly Events.csv. Weekly rows still have a blank Date and
match on Day. D:\\MPR\\Events\\Mos_Place_Radio\\Weekly_Events.ics is not read.
"""

from __future__ import annotations

import argparse
import csv
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

logger = logging.getLogger("moplace.livedj.bands")

STATION_TZ = ZoneInfo("America/New_York")
STATION_ROOT = Path(r"D:\MPR")
BANDS_FILENAME = "BandsTonight.txt"
CALENDAR_FILENAME = "Weekly Events.csv"

_WEEKDAYS = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)
_WEEKDAY_ALIASES = {name.lower(): name for name in _WEEKDAYS}
_WEEKDAY_ALIASES.update(
    {
        "mon": "Monday",
        "tue": "Tuesday",
        "tues": "Tuesday",
        "wed": "Wednesday",
        "thu": "Thursday",
        "thur": "Thursday",
        "thurs": "Thursday",
        "fri": "Friday",
        "sat": "Saturday",
        "sun": "Sunday",
    }
)
_MONTHS = (
    "",
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
_ISO_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})\b")
_SLASH_DATE_RE = re.compile(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b")
_YES = {"yes", "y", "true", "1"}
_WEEKLY = {"weekly", "week", "every"}
_DATED = {"date", "dated", "once"}
_NOTES = {"note", "notes", "comment", "comments"}


@dataclass(frozen=True)
class BandEvent:
    event: str
    place: str
    town: str
    time: str
    repeat: str
    day: str
    event_date: str


def live_base() -> Path | None:
    """Script folder from platform_paths, when Bands.py is running inside LiveDJ.

    On the Office PC this is D:\\MPR\\Engines\\LiveDJ. It is not the calendar root.
    """
    try:
        from platform_paths import LIVE_BASE
    except ImportError:
        return None
    return Path(LIVE_BASE)


def station_roots(base: Path | None = None) -> list[Path]:
    """Office PC folders that can hold Weekly Events.csv.

    D:\\MPR comes first. LIVE_BASE is included after it so a calendar sitting
    next to the scripts can still be found, without hiding the station sheet.
    """
    if base is not None:
        return [base]
    roots: list[Path] = [STATION_ROOT]
    live = live_base()
    if live is not None and live not in roots:
        roots.append(live)
    return roots


def calendar_candidates(base: Path | None = None) -> list[Path]:
    """Paths tried for Weekly Events.csv.

    D:\\MPR\\Events\\Weekly Events.csv is the Office PC sheet. It is searched
    after D:\\MPR\\Weekly Events.csv and before the LiveDJ script folder.
    The .ics export in that Events tree is not a candidate.
    """
    candidates: list[Path] = []
    roots = station_roots(base)
    for index, root in enumerate(roots):
        candidates.append(root / CALENDAR_FILENAME)
        if index == 0:
            candidates.append(root / "Events" / CALENDAR_FILENAME)
        candidates.extend(
            (
                root / "Knowledge" / CALENDAR_FILENAME,
                root / "Weekly Events" / CALENDAR_FILENAME,
            )
        )
    unique: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def default_calendar_path(base: Path | None = None) -> Path:
    candidates = calendar_candidates(base)
    for path in candidates:
        if path.is_file():
            return path
    return candidates[0]


def default_output_path(base: Path | None = None) -> Path:
    """BandsTonight.txt under the Office PC knowledge folder, not the script folder."""
    root = base or STATION_ROOT
    return root / "Knowledge" / BANDS_FILENAME


def extra_output_paths(primary: Path) -> list[Path]:
    """Also update LiveDJ's own Knowledge folder when that folder already exists."""
    live = live_base()
    if live is None:
        return []
    extra = live / "Knowledge" / BANDS_FILENAME
    if extra == primary or not extra.parent.is_dir():
        return []
    return [extra]


def station_night(when: date | datetime | None = None) -> date:
    """Calendar night at the station, not the UTC date of a cloud clock."""
    if isinstance(when, datetime):
        if when.tzinfo is None:
            return when.replace(tzinfo=STATION_TZ).astimezone(STATION_TZ).date()
        return when.astimezone(STATION_TZ).date()
    if isinstance(when, date):
        return when
    return datetime.now(STATION_TZ).date()


def weekday_name(value: str) -> str | None:
    token = re.sub(r"[^a-z]", "", str(value or "").strip().lower())
    if not token:
        return None
    return _WEEKDAY_ALIASES.get(token)


def parse_event_date(value: str) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    iso = _ISO_DATE_RE.match(text)
    if iso:
        try:
            return date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        except ValueError:
            return None
    slash = _SLASH_DATE_RE.match(text)
    if slash:
        try:
            return date(int(slash.group(3)), int(slash.group(1)), int(slash.group(2)))
        except ValueError:
            return None
    return None


def _clean_row(row: dict[str, str | None]) -> dict[str, str]:
    cleaned: dict[str, str] = {}
    for key, value in row.items():
        name = str(key or "").strip()
        if not name:
            continue
        cleaned[name] = str(value or "").strip()
    return cleaned


def _is_yes(value: str) -> bool:
    return value.strip().lower() in _YES


def _row_kind(repeat: str, day: str, event_date: date | None) -> str:
    token = repeat.strip().lower()
    if token in _NOTES:
        return "note"
    if token in _WEEKLY:
        return "weekly"
    if token in _DATED:
        return "date"
    if event_date is not None:
        return "date"
    if weekday_name(day):
        return "weekly"
    return ""


def load_calendar(path: Path) -> list[dict[str, str]]:
    raw = path.read_bytes()
    text = None
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        text = raw.decode("utf-8", errors="replace")
    rows: list[dict[str, str]] = []
    reader = csv.DictReader(text.splitlines())
    for row in reader:
        if not row:
            continue
        cleaned = _clean_row(row)
        if any(cleaned.values()):
            rows.append(cleaned)
    return rows


def events_for_night(rows: list[dict[str, str]], night: date) -> list[BandEvent]:
    """Yes rows that air on this night.

    Weekly rows match Day and are kept when Date is blank.
    Date rows match YYYY-MM-DD and do not also have to match Day.
    """
    tonight = _WEEKDAYS[night.weekday()]
    selected: list[BandEvent] = []
    for row in rows:
        repeat = row.get("Repeat", "")
        day = row.get("Day", "")
        raw_date = row.get("Date", "")
        event_name = row.get("Event", "")
        event_date = parse_event_date(raw_date)
        kind = _row_kind(repeat, day, event_date)
        if kind in {"", "note"}:
            continue
        if not _is_yes(row.get("On", "")):
            continue
        if not event_name.strip():
            continue
        if kind == "weekly":
            if weekday_name(day) != tonight:
                continue
        elif event_date != night:
            continue
        selected.append(
            BandEvent(
                event=event_name.strip(),
                place=row.get("Place", "").strip(),
                town=row.get("Town", "").strip(),
                time=row.get("Time", "").strip(),
                repeat=kind,
                day=weekday_name(day) or "",
                event_date=event_date.isoformat() if event_date else "",
            )
        )
    return selected


def render_event_line(event: BandEvent) -> str:
    where: list[str] = []
    if event.place:
        where.append(f"at {event.place}")
    if event.town:
        where.append(f"in {event.town}")
    place = " ".join(where)
    if event.time and place:
        return f"{event.time}: {event.event} {place}."
    if event.time:
        return f"{event.time}: {event.event}."
    if place:
        return f"{event.event} {place}."
    return f"{event.event}."


def render_bands(events: list[BandEvent], night: date) -> str:
    heading = f"{_WEEKDAYS[night.weekday()]}, {_MONTHS[night.month]} {night.day}, {night.year}"
    lines = [heading, *[render_event_line(event) for event in events]]
    return "\n".join(lines) + "\n"


def _refuse_wav(path: Path) -> None:
    if path.suffix.lower() == ".wav":
        raise ValueError(
            "Weekly Events does not replace Friday, Saturday, and Sunday band rundown wav files."
        )


def write_bands_file(
    calendar_path: Path,
    output_path: Path,
    night: date | datetime | None = None,
) -> Path | None:
    """Write BandsTonight.txt, or remove it when this night has no Yes events.

    Replaces an existing text file. Never writes a wav.
    """
    _refuse_wav(output_path)
    when = station_night(night)
    if not calendar_path.is_file():
        logger.error("Weekly Events calendar not found: %s", calendar_path)
        return None
    events = events_for_night(load_calendar(calendar_path), when)
    if not events:
        if output_path.is_file():
            output_path.unlink()
            logger.info("No Yes events for %s. Removed %s", when.isoformat(), output_path)
        else:
            logger.info("No Yes events for %s. No bands file written.", when.isoformat())
        return None
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = output_path.with_suffix(output_path.suffix + ".tmp")
    tmp.write_text(render_bands(events, when), encoding="utf-8", newline="\n")
    tmp.replace(output_path)
    logger.info("Wrote %s bands for %s to %s", len(events), when.isoformat(), output_path)
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write tonight's bands file from Weekly Events.csv")
    parser.add_argument("--calendar", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--date", default="", help="Station night as YYYY-MM-DD. Default is today in America/New_York.")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    calendar_path = args.calendar or default_calendar_path()
    output_path = args.output or default_output_path()
    night = parse_event_date(args.date) if args.date else station_night()
    if args.date and night is None:
        logger.error("Date must be YYYY-MM-DD: %s", args.date)
        return 1
    if not calendar_path.is_file():
        tried = [calendar_path] if args.calendar else calendar_candidates()
        for path in tried:
            logger.error("Weekly Events calendar not found: %s", path)
        return 1
    written = write_bands_file(calendar_path, output_path, night)
    if args.output is None:
        for extra in extra_output_paths(output_path):
            write_bands_file(calendar_path, extra, night)
    if written is None:
        print(f"No bands file. No Yes events for {night.isoformat()}.")
        return 0
    print(f"Wrote {written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""LiveDJ break schedule editing — CSV schema compatible with the production engine."""

from __future__ import annotations

import importlib
import json
import re
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from app.core.platform_connector import livedj_personalities_path

_MPR_ROOT = Path(r"D:\MPR")
_LIVEDJ_SCRIPTS = _MPR_ROOT / "Engines" / "LiveDJ" / "Scripts"
_CANONICAL_SCHEDULE = _MPR_ROOT / "Config" / "Schedules" / "weekday_schedule.csv"
_PRESETS_FILE = _MPR_ROOT / "Config" / "schedule_mission_presets.json"
_BACKUP_DIR = _MPR_ROOT / "Backups" / "Schedule"
_MAX_BACKUPS = 20

SCHEDULE_DAYS = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)

SCHEDULE_FIELDS = [
    "day_of_week",
    "Time",
    "Host",
    "Type",
    "EventType",
    "Mission",
    "Format",
    "NextHost",
    "TargetWav",
    "CartId",
    "Enabled",
]

STATUS_VALID = "Valid"
STATUS_MISSING_MISSION = "Missing Mission"
STATUS_MISSING_VOICE = "Missing Voice"
STATUS_SETUP_REQUIRED = "Setup Required"
STATUS_DUPLICATE_TIME = "Duplicate Time"
STATUS_FORMAT_MISMATCH = "Format Mismatch"

FILTER_ALL = "All Events"
FILTER_SHOW_OPENS = "Show Opens"
FILTER_CHECK_INS = "Check-Ins"
FILTER_STORIES = "Stories"
FILTER_HANDOFFS = "Handoffs"
FILTER_FORMAT_CHANGES = "Format Changes"
FILTER_ERRORS = "Errors Only"

EVENT_FILTER_MAP = {
    FILTER_ALL: None,
    FILTER_SHOW_OPENS: {"Show Open"},
    FILTER_CHECK_INS: {"Check-In", "Weekend Check-In"},
    FILTER_STORIES: {"Music Story", "Artist Spotlight", "Listener Memory", "This Day in Music History", "On This Day in the 70s"},
    FILTER_HANDOFFS: {"Handoff", "Show Close"},
    FILTER_FORMAT_CHANGES: {"Format Change"},
    FILTER_ERRORS: "errors",
}


@dataclass
class SaveScheduleResult:
    success: bool = False
    message: str = ""
    backup_path: str = ""
    entry_count: int = 0
    warning_count: int = 0
    warnings: list[str] = field(default_factory=list)


@dataclass
class HostChoice:
    key: str
    label: str
    setup_required: bool = False
    inactive: bool = False


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}


def _ensure_livedj_scripts() -> None:
    text = str(_LIVEDJ_SCRIPTS)
    if _LIVEDJ_SCRIPTS.is_dir() and text not in sys.path:
        sys.path.insert(0, text)


def _engine():
    _ensure_livedj_scripts()
    schedule = importlib.import_module("livedj_schedule")
    events = importlib.import_module("livedj_events")
    return schedule, events


def schedule_file_path() -> Path:
    if _CANONICAL_SCHEDULE.is_file():
        return _CANONICAL_SCHEDULE
    from app.core.platform_connector import livedj_schedule_csv_path

    return livedj_schedule_csv_path()


def load_all_rows() -> list[dict[str, str]]:
    schedule, _events = _engine()
    return schedule.load_schedule_file(schedule_file_path())


def rows_for_day(all_rows: list[dict[str, str]], day: str) -> list[dict[str, str]]:
    schedule, _events = _engine()
    return schedule.rows_for_day(all_rows, day)


def merge_day_rows(all_rows: list[dict[str, str]], day: str, day_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    schedule, _events = _engine()
    return schedule.merge_day_rows(all_rows, day, day_rows)


def copy_day_rows(
    all_rows: list[dict[str, str]],
    source_day: str,
    target_day: str,
    *,
    append: bool = False,
) -> list[dict[str, str]]:
    schedule, _events = _engine()
    copied = schedule.rows_for_day(all_rows, source_day)
    if append:
        existing = schedule.rows_for_day(all_rows, target_day)
        return schedule.merge_day_rows(all_rows, target_day, existing + [dict(row) for row in copied])
    return schedule.copy_day_rows(all_rows, source_day, target_day)


def finalize_row(row: dict[str, str]) -> dict[str, str]:
    _schedule, events = _engine()
    return events.finalize_schedule_row(dict(row))


def event_types() -> tuple[str, ...]:
    _schedule, events = _engine()
    return tuple(events.EVENT_TYPES)


def schedule_type_for_event(event_type: str) -> str:
    _schedule, events = _engine()
    return events.schedule_type_for_event(event_type)


def schedule_type_labels() -> tuple[str, ...]:
    return ("show_open", "check_in", "music_story", "listener_memory", "handoff", "format_change", "show_close")


def load_hosts() -> dict[str, dict[str, Any]]:
    path = livedj_personalities_path()
    data = _read_json(path) if path.exists() else {}
    return dict(data.get("hosts") or {})


def host_is_setup_required(host: dict[str, Any]) -> bool:
    voice = str(host.get("voice_id") or host.get("voicebox_voice_id") or "").strip()
    cart = str(host.get("cart_id") or host.get("radiodj_cart_id") or "").strip()
    wav = str(host.get("wav_path") or host.get("wav_output_path") or "").strip()
    if not voice or not cart or not wav:
        return True
    if voice.upper() in {"SETUP REQUIRED", "TBD"}:
        return True
    return False


def host_choices(hosts: dict[str, dict[str, Any]] | None = None) -> list[HostChoice]:
    roster = hosts or load_hosts()
    choices: list[HostChoice] = []
    for key, record in sorted(roster.items(), key=lambda item: str(item[1].get("display_name") or item[0]).lower()):
        if record.get("active") is False:
            continue
        label = str(record.get("display_name") or key).strip() or key
        setup = host_is_setup_required(record)
        if setup:
            label = f"{label} (SETUP REQUIRED)"
        choices.append(HostChoice(key=key, label=label, setup_required=setup))
    return choices


def host_label_for_key(host_key: str, hosts: dict[str, dict[str, Any]] | None = None) -> str:
    roster = hosts or load_hosts()
    record = roster.get(host_key, {})
    return str(record.get("display_name") or host_key or "—")


def resolve_host_key(value: str, hosts: dict[str, dict[str, Any]] | None = None) -> str:
    schedule, _events = _engine()
    return schedule.resolve_host_key(value, hosts or load_hosts())


def format_choices(host_key: str = "", hosts: dict[str, dict[str, Any]] | None = None) -> list[str]:
    _schedule, events = _engine()
    roster = hosts or load_hosts()
    choices = list(events.station_format_choices(roster))
    host = roster.get(host_key, {})
    for fmt in host.get("formats") or []:
        text = str(fmt or "").strip()
        if text and text not in choices:
            choices.append(text)
    return sorted(set(choices), key=str.lower)


def host_defaults(host_key: str, hosts: dict[str, dict[str, Any]] | None = None) -> tuple[str, str, str]:
    roster = hosts or load_hosts()
    host = roster.get(host_key, {})
    wav = str(host.get("wav_path") or host.get("wav_output_path") or "").strip()
    cart = str(host.get("cart_id") or host.get("radiodj_cart_id") or "").strip()
    formats = host.get("formats") or []
    default_format = str(formats[0]).strip() if formats else ""
    return default_format, wav, cart


def time_options_15min() -> list[str]:
    return [f"{hour:02d}:{minute:02d}" for hour in range(24) for minute in (0, 15, 30, 45)]


def parse_time(value: str) -> str:
    text = str(value or "").strip().upper().replace(".", ":")
    if not text:
        raise ValueError("Time is required.")
    match = re.match(r"^(\d{1,2}):(\d{2})(?:\s*(AM|PM))?$", text)
    if not match:
        raise ValueError(f"'{value}' is not a valid time. Use HH:MM or 7:30 AM.")
    hour = int(match.group(1))
    minute = int(match.group(2))
    meridiem = match.group(3)
    if meridiem == "PM" and hour < 12:
        hour += 12
    if meridiem == "AM" and hour == 12:
        hour = 0
    if hour > 23 or minute > 59:
        raise ValueError(f"'{value}' is not a valid time.")
    return f"{hour:02d}:{minute:02d}"


def format_time_friendly(value: str) -> str:
    try:
        hour, minute = map(int, parse_time(value).split(":"))
    except ValueError:
        return value
    meridiem = "AM" if hour < 12 else "PM"
    display_hour = hour % 12 or 12
    return f"{display_hour}:{minute:02d} {meridiem}"


def suggest_next_time(current_time: str, *, offset_minutes: int = 30) -> str:
    try:
        hour, minute = map(int, parse_time(current_time).split(":"))
    except ValueError:
        return "07:00"
    base = datetime(2000, 1, 1, hour, minute) + timedelta(minutes=offset_minutes)
    minute_slot = ((base.minute + 14) // 15) * 15
    if minute_slot >= 60:
        base = base.replace(minute=0) + timedelta(hours=1)
        minute_slot = 0
    return base.replace(minute=minute_slot).strftime("%H:%M")


def suggest_round_time_after(current_time: str) -> str:
    try:
        hour, minute = map(int, parse_time(current_time).split(":"))
    except ValueError:
        return "10:00"
    if minute == 0:
        return f"{hour:02d}:00"
    if minute < 30:
        return f"{hour:02d}:30"
    return f"{(hour + 1) % 24:02d}:00"


def suggest_format(previous_row: dict[str, str] | None, next_row: dict[str, str] | None) -> str:
    if previous_row and str(previous_row.get("Format") or "").strip():
        return str(previous_row.get("Format") or "").strip()
    if next_row and str(next_row.get("Format") or "").strip():
        return str(next_row.get("Format") or "").strip()
    return ""


def suggest_event_type(previous_row: dict[str, str] | None, new_format: str) -> str:
    prev_format = str(previous_row.get("Format") or "").strip() if previous_row else ""
    if prev_format and new_format and prev_format != new_format:
        return "Format Change"
    return "Check-In"


def load_mission_presets() -> dict[str, Any]:
    if not _PRESETS_FILE.is_file():
        return {"presets": {}}
    return _read_json(_PRESETS_FILE)


def mission_preset_options(event_type: str) -> list[tuple[str, str]]:
    data = load_mission_presets()
    presets = data.get("presets", {})
    options: list[tuple[str, str]] = [("Custom Mission", "")]
    for item in presets.get(event_type.strip(), []):
        if isinstance(item, dict):
            label = str(item.get("label") or item.get("text") or "Preset").strip()
            text = str(item.get("text") or "").strip()
            if text:
                options.append((label, text))
    _schedule, events = _engine()
    default = events.default_mission_for_event_type(event_type)
    if default:
        options.insert(1, ("Default objective", default))
    return options


def backup_schedule_file(path: Path | None = None) -> Path | None:
    source = path or schedule_file_path()
    if not source.is_file():
        return None
    _BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = _BACKUP_DIR / f"weekday_schedule_{stamp}.csv"
    shutil.copy2(source, target)
    backups = sorted(_BACKUP_DIR.glob("weekday_schedule_*.csv"), key=lambda item: item.stat().st_mtime, reverse=True)
    for old in backups[_MAX_BACKUPS:]:
        try:
            old.unlink()
        except OSError:
            pass
    return target


def list_schedule_backups(limit: int = 20) -> list[Path]:
    if not _BACKUP_DIR.is_dir():
        return []
    backups = sorted(_BACKUP_DIR.glob("weekday_schedule_*.csv"), key=lambda item: item.stat().st_mtime, reverse=True)
    return backups[:limit]


def restore_schedule_backup(backup_path: Path) -> SaveScheduleResult:
    if not backup_path.is_file():
        return SaveScheduleResult(success=False, message="Backup file was not found.")
    target = schedule_file_path()
    current_backup = backup_schedule_file(target)
    shutil.copy2(backup_path, target)
    return SaveScheduleResult(
        success=True,
        message="Schedule restored from backup.",
        backup_path=str(current_backup or backup_path),
    )


def write_all_rows(rows: list[dict[str, str]], *, day: str = "") -> SaveScheduleResult:
    schedule, _events = _engine()
    path = schedule_file_path()
    backup = backup_schedule_file(path)
    try:
        schedule.write_schedule_file(path, rows)
    except OSError as exc:
        return SaveScheduleResult(success=False, message=f"Could not save schedule: {exc}")
    day_rows = rows_for_day(rows, day) if day else []
    warnings: list[str] = []
    hosts = load_hosts()
    for index, row in enumerate(day_rows):
        warnings.extend(validate_break_row(row, hosts=hosts, day_rows=day_rows, row_index=index))
    return SaveScheduleResult(
        success=True,
        message=f"Schedule saved successfully{f' for {day}' if day else ''}.",
        backup_path=str(backup or ""),
        entry_count=len(day_rows) if day else len(rows),
        warning_count=len(warnings),
        warnings=warnings,
    )


def row_status(row: dict[str, str], hosts: dict[str, dict[str, Any]] | None = None, day_rows: list[dict[str, str]] | None = None) -> str:
    roster = hosts or load_hosts()
    if not str(row.get("Mission") or "").strip():
        return STATUS_MISSING_MISSION
    host_key = str(row.get("Host") or "").strip()
    host = roster.get(host_key, {})
    if host and host_is_setup_required(host):
        return STATUS_SETUP_REQUIRED
    voice = str(host.get("voice_id") or host.get("voicebox_voice_id") or "").strip()
    if host_key and not voice:
        return STATUS_MISSING_VOICE
    if day_rows:
        time_value = str(row.get("Time") or "").strip()
        if time_value and sum(1 for item in day_rows if str(item.get("Time") or "").strip() == time_value) > 1:
            return STATUS_DUPLICATE_TIME
    event_type = str(row.get("EventType") or "").strip()
    schedule_type = str(row.get("Type") or "").strip()
    expected = schedule_type_for_event(event_type) if event_type else ""
    if event_type and schedule_type and expected and schedule_type != expected:
        return STATUS_FORMAT_MISMATCH
    return STATUS_VALID


def validate_break_row(
    row: dict[str, str],
    *,
    hosts: dict[str, dict[str, Any]] | None = None,
    day_rows: list[dict[str, str]] | None = None,
    row_index: int | None = None,
    exclude_index: int | None = None,
) -> list[str]:
    messages: list[str] = []
    roster = hosts or load_hosts()
    try:
        parse_time(str(row.get("Time") or ""))
    except ValueError as exc:
        messages.append(str(exc))

    host_key = resolve_host_key(str(row.get("Host") or ""), roster)
    if not host_key or host_key not in roster:
        messages.append("Choose a valid DJ from the personality list.")
    elif host_is_setup_required(roster[host_key]):
        messages.append(f"{host_label_for_key(host_key, roster)} is marked SETUP REQUIRED and may not generate audio.")

    event_type = str(row.get("EventType") or "").strip()
    if not event_type:
        messages.append("Select an event type.")
    elif event_type not in event_types():
        messages.append(f"Event type '{event_type}' is not recognized.")

    if not str(row.get("Mission") or "").strip():
        messages.append("This row has no mission. Add a mission before saving.")

    if not str(row.get("Format") or "").strip():
        messages.append("Select a format.")

    time_value = str(row.get("Time") or "").strip()
    if day_rows and time_value:
        for index, item in enumerate(day_rows):
            if exclude_index is not None and index == exclude_index:
                continue
            if str(item.get("Time") or "").strip() == time_value:
                messages.append(f"There is already an event scheduled at {format_time_friendly(time_value)}.")
                break

    if event_type:
        expected = schedule_type_for_event(event_type)
        actual = str(row.get("Type") or "").strip()
        if actual and actual != expected:
            messages.append(f"Schedule type '{actual}' does not match event type '{event_type}'.")

    if event_type in {"Handoff", "Show Close"} and not str(row.get("NextHost") or "").strip():
        messages.append("Handoff and show close breaks should name the next host when possible.")

    return messages


def build_row_from_form(
    *,
    day: str,
    time_value: str,
    host_key: str,
    event_type: str,
    mission: str,
    format_name: str,
    schedule_type: str = "",
    next_host: str = "",
    wav_path: str = "",
    cart_id: str = "",
    hosts: dict[str, dict[str, Any]] | None = None,
) -> dict[str, str]:
    roster = hosts or load_hosts()
    host_key = resolve_host_key(host_key, roster)
    default_format, default_wav, default_cart = host_defaults(host_key, roster)
    row = {field: "" for field in SCHEDULE_FIELDS}
    row["day_of_week"] = day
    row["Time"] = parse_time(time_value)
    row["Host"] = host_key
    row["EventType"] = event_type.strip()
    row["Mission"] = mission.strip()
    row["Format"] = format_name.strip() or default_format
    row["Type"] = schedule_type.strip() or schedule_type_for_event(row["EventType"])
    row["NextHost"] = resolve_host_key(next_host, roster) if next_host else ""
    row["TargetWav"] = wav_path.strip() or default_wav
    row["CartId"] = cart_id.strip() or default_cart
    row["Enabled"] = "1"
    return finalize_row(row)


def filter_day_rows(day_rows: list[dict[str, str]], filter_name: str, hosts: dict[str, dict[str, Any]] | None = None) -> list[dict[str, str]]:
    spec = EVENT_FILTER_MAP.get(filter_name, None)
    if spec is None:
        return list(day_rows)
    if spec == "errors":
        roster = hosts or load_hosts()
        return [row for row in day_rows if row_status(row, roster, day_rows) != STATUS_VALID]
    allowed = set(spec)
    return [row for row in day_rows if str(row.get("EventType") or "").strip() in allowed]


def preview_break(row: dict[str, str], hosts: dict[str, dict[str, Any]] | None = None) -> dict[str, str]:
    roster = hosts or load_hosts()
    host_key = str(row.get("Host") or "").strip()
    host = roster.get(host_key, {})
    voice = str(host.get("voice_id") or host.get("voicebox_voice_id") or "—")
    wav = str(row.get("TargetWav") or host.get("wav_path") or host.get("wav_output_path") or "—")
    return {
        "day": str(row.get("day_of_week") or ""),
        "time": format_time_friendly(str(row.get("Time") or "")),
        "time_internal": str(row.get("Time") or ""),
        "dj": host_label_for_key(host_key, roster),
        "host_key": host_key,
        "event_type": str(row.get("EventType") or ""),
        "format": str(row.get("Format") or ""),
        "mission": str(row.get("Mission") or ""),
        "schedule_type": str(row.get("Type") or ""),
        "voicebox_profile": voice or "—",
        "output_path": wav,
        "cart_id": str(row.get("CartId") or host.get("cart_id") or "—"),
        "next_host": str(row.get("NextHost") or "—"),
        "generation_plan": f"LiveDJ break for {host_key} at {row.get('Time', '')} — {row.get('EventType', '')}",
    }


def insert_row_sorted(day_rows: list[dict[str, str]], row: dict[str, str]) -> list[dict[str, str]]:
    merged = [dict(item) for item in day_rows]
    merged.append(dict(row))
    merged.sort(key=lambda item: item.get("Time", "99:99"))
    return merged


def replace_row_at(day_rows: list[dict[str, str]], index: int, row: dict[str, str]) -> list[dict[str, str]]:
    merged = [dict(item) for item in day_rows]
    if 0 <= index < len(merged):
        merged[index] = dict(row)
    merged.sort(key=lambda item: item.get("Time", "99:99"))
    return merged


def delete_row_at(day_rows: list[dict[str, str]], index: int) -> list[dict[str, str]]:
    return [dict(item) for offset, item in enumerate(day_rows) if offset != index]

"""Rotate same-day fun days so each LiveDJ break gets one.

When several observances fall on the same date, the prompt used to list every
one of them on every break. Breaks now take turns: the first break of the day
gets the first fun day, the next break gets the next, and so on. The same
break time and host always get the same fun day if the prompt is rebuilt.
A single fun day still goes on every break.
Category on Edit Fun Day is Funny, Regular, or Serious. Saved values stay
fun, regular, or serious. Breast Cancer Awareness Month with no saved
category loads as serious.

The Fun / National Days list can still show every observance for today.
The preview panel should call preview_prompt_payload() so it shows the
next break's one fun day and whose turn is next.

Deploy to D:\\MPR\\Engines\\LiveDJ\\Scripts\\FunDays.py
"""

from __future__ import annotations

import calendar
import re
from datetime import date, datetime, time, timedelta

# Casey and Mo Blues stay out of "Each DJ" unless a fun day names them.
_EXCLUDED_FROM_EACH = {
    "casey",
    "mo blues",
    "mo's blues",
    "mos blues",
    "moblues",
}

_MONTHS = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

_WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

_NTH_WORDS = {
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "last": -1,
}

_NTH_RE = re.compile(
    r"(?i)\b(?P<nth>\d{1,2}(?:st|nd|rd|th)?|first|second|third|fourth|fifth|last)\s+"
    r"(?P<weekday>monday|tuesday|wednesday|thursday|friday|saturday|sunday)s?\s+of\s+"
    r"(?P<month>january|february|march|april|may|june|july|august|september|"
    r"october|november|december)\b"
)

# Stored on the observance. The Edit Fun Day combobox shows the labels.
FUNNY = "fun"
REGULAR = "regular"
SERIOUS = "serious"
CATEGORY_LABELS = ("Funny", "Regular", "Serious")
_LABEL_FOR_TOKEN = {FUNNY: "Funny", REGULAR: "Regular", SERIOUS: "Serious"}

# One line in the break prompt for each tone.
FUNNY_PROMPT_LINE = "Mention it lightly. A joke is fine if it fits the operator note."
REGULAR_PROMPT_LINE = "Mention it in a normal conversational way. Do not force a joke."
SERIOUS_PROMPT_LINE = (
    "Mention it once in one short respectful sentence. Do not joke. "
    "Do not say you do not know what it means. Do not say you like it. "
    "Do not make fun of illness, survivors, or people who have died. "
    "The station name is Mo's Place Radio."
)

# Saved before the category existed. Load it as serious until the operator picks one.
_SERIOUS_TITLES = {"breast cancer awareness month"}

_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})\s*(am|pm)?$")
_ISO_RE = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")
_SLASH_RE = re.compile(r"^(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?$")
_DAY_TOKEN_RE = re.compile(r"^(\d{1,2})(?:st|nd|rd|th)?$")


def station_day(when: date | datetime | None = None) -> date | None:
    """Calendar day used for 'is this fun day on?' None means the caller already filtered."""
    if isinstance(when, datetime):
        return when.date()
    if isinstance(when, date):
        return when
    return None


def normalize_host(host: str) -> str:
    text = str(host or "").strip().lower()
    text = text.replace("_", " ").replace("-", " ")
    text = re.sub(r"\s+", " ", text).strip()
    if text.startswith("dj "):
        text = text[3:].strip()
    aliases = {
        "mo blues": "mo blues",
        "moblues": "mo blues",
        "mo's blues": "mo blues",
        "mos blues": "mo blues",
    }
    return aliases.get(text, text)


def _collapse(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on", "aired", "already aired"}


def _enabled_flag(raw: dict) -> bool:
    for key in ("enabled", "Enabled", "on", "On"):
        if key not in raw:
            continue
        value = raw.get(key)
        if value is None or str(value).strip() == "":
            continue
        return _truthy(value)
    return True


def _aired_flag(raw: dict) -> bool:
    for key in ("already_aired", "aired", "AlreadyAired", "past"):
        if key not in raw:
            continue
        value = raw.get(key)
        if value is None or str(value).strip() == "":
            continue
        return _truthy(value)
    status = str(raw.get("status") or raw.get("Status") or "").strip().lower()
    return status in {"aired", "already aired", "already_aired"}


def _stored_category(raw: dict) -> str:
    for key in ("category", "Category"):
        if key not in raw:
            continue
        value = raw.get(key)
        if value is None:
            continue
        text = _collapse(value)
        if text:
            return text
    return ""


def stored_category_token(value: str) -> str | None:
    """Map a combobox label or an older saved category onto fun, regular, or serious."""
    text = _collapse(value).lower()
    if not text:
        return None
    if text in {"serious", "serious day"}:
        return SERIOUS
    if text in {"regular"}:
        return REGULAR
    if text in {"fun", "fun day", "funny"}:
        return FUNNY
    if "serious" in text:
        return SERIOUS
    if "regular" in text:
        return REGULAR
    if "funny" in text or text == "fun" or text.startswith("fun "):
        return FUNNY
    return None


def category_label(token: str) -> str:
    """Operator label for a stored category. fun and Fun Day show as Funny."""
    canonical = stored_category_token(token) or FUNNY
    return _LABEL_FOR_TOKEN[canonical]


def category_for(raw: dict, title: str) -> str:
    """fun, regular, or serious. Blank stays fun, except Breast Cancer Awareness Month."""
    token = stored_category_token(_stored_category(raw))
    if token:
        return token
    if _collapse(title).lower().rstrip(".") in _SERIOUS_TITLES:
        return SERIOUS
    return FUNNY


def prompt_line_for_category(token: str) -> str:
    """The one tone line for this observance."""
    if token == SERIOUS:
        return SERIOUS_PROMPT_LINE
    if token == REGULAR:
        return REGULAR_PROMPT_LINE
    return FUNNY_PROMPT_LINE


def normalize_day(raw: object) -> dict:
    """One observance with the Edit Fun Day fields, including Category."""
    if isinstance(raw, str):
        raw = {"title": raw}
    if not isinstance(raw, dict):
        raw = {}
    who = _collapse(raw.get("who") or raw.get("dj") or raw.get("DJ") or raw.get("audience") or "Each DJ")
    selected = _collapse(
        raw.get("selected_djs")
        or raw.get("SelectedDJs")
        or raw.get("djs")
        or raw.get("DJs")
        or ""
    )
    title = _collapse(raw.get("title") or raw.get("Title") or "")
    return {
        "title": title,
        "category": category_for(raw, title),
        "enabled": _enabled_flag(raw),
        "already_aired": _aired_flag(raw),
        "aired_on": _collapse(raw.get("aired_on") or raw.get("last_aired") or ""),
        "who": who or "Each DJ",
        "selected_djs": selected,
        "read_by": _collapse(raw.get("read_by") or raw.get("ReadBy") or raw.get("read") or ""),
        "note": _collapse(raw.get("note") or raw.get("notes") or raw.get("Note") or raw.get("Notes") or ""),
        "when": _collapse(raw.get("when") or raw.get("When") or ""),
        "date": _collapse(raw.get("date") or raw.get("Date") or raw.get("date_or_month") or ""),
        "days_of_month": _collapse(raw.get("days_of_month") or raw.get("Days") or raw.get("days") or ""),
    }


def _nth_number(token: str) -> int | None:
    word = token.strip().lower()
    if word in _NTH_WORDS:
        return _NTH_WORDS[word]
    match = _DAY_TOKEN_RE.fullmatch(word)
    if not match:
        return None
    return int(match.group(1))


def parse_nth_weekday(text: str) -> tuple[int, int, int] | None:
    """Return (nth, weekday, month). nth is -1 for 'last'."""
    match = _NTH_RE.search(str(text or ""))
    if not match:
        return None
    nth = _nth_number(match.group("nth"))
    weekday = _WEEKDAYS.get(match.group("weekday").lower())
    month = _MONTHS.get(match.group("month").lower())
    if nth is None or weekday is None or month is None:
        return None
    return nth, weekday, month


def _nth_date(year: int, month: int, weekday: int, nth: int) -> date | None:
    if nth == -1:
        cursor = date(year, month, calendar.monthrange(year, month)[1])
        while cursor.weekday() != weekday:
            cursor -= timedelta(days=1)
        return cursor
    if nth < 1:
        return None
    first = date(year, month, 1)
    delta = (weekday - first.weekday()) % 7
    day_num = 1 + delta + (nth - 1) * 7
    if day_num > calendar.monthrange(year, month)[1]:
        return None
    return date(year, month, day_num)


def parse_month_day(text: str) -> tuple[int, int] | None:
    """Month and day from 'October 14', '2026-10-14', or '10/14'. Not an nth-weekday phrase."""
    raw = _collapse(text)
    if not raw or parse_nth_weekday(raw):
        return None
    iso = _ISO_RE.fullmatch(raw)
    if iso:
        return int(iso.group(2)), int(iso.group(3))
    slash = _SLASH_RE.fullmatch(raw)
    if slash:
        return int(slash.group(1)), int(slash.group(2))
    month = None
    day_num = None
    for part in raw.lower().replace(",", " ").split():
        if part in _MONTHS and month is None:
            month = _MONTHS[part]
            continue
        match = _DAY_TOKEN_RE.fullmatch(part)
        if match and day_num is None:
            day_num = int(match.group(1))
    if month and day_num and 1 <= day_num <= 31:
        return month, day_num
    return None


def parse_month_name(text: str) -> int | None:
    raw = _collapse(text).lower()
    if not raw or parse_month_day(raw) or parse_nth_weekday(raw):
        return None
    for part in raw.replace(",", " ").split():
        if part in _MONTHS:
            return _MONTHS[part]
    return None


def _parse_day_list(text: str) -> set[int]:
    days: set[int] = set()
    for token in re.split(r"[,;\s]+", str(text or "").strip()):
        match = _DAY_TOKEN_RE.fullmatch(token)
        if match:
            number = int(match.group(1))
            if 1 <= number <= 31:
                days.add(number)
    return days


def _parse_iso_date(text: str) -> date | None:
    match = _ISO_RE.fullmatch(_collapse(text))
    if not match:
        return None
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def _is_whole_month(when_mode: str) -> bool:
    mode = when_mode.strip().lower()
    if "selected" in mode:
        return False
    if mode in {"month", "whole month", "all month", "every day", "all the days", "all days"}:
        return True
    return "whole month" in mode or "all month" in mode or "every day" in mode


def occurs_on(day: dict, on: date | None) -> bool:
    """True when this fun day is scheduled for the calendar day.

    Records with no date are kept. Callers that already chose today's rows
    can pass them through unchanged.
    """
    if on is None:
        return True
    when_mode = str(day.get("when") or "").strip().lower()
    date_text = str(day.get("date") or "").strip()
    days_text = str(day.get("days_of_month") or "").strip()

    nth = parse_nth_weekday(date_text) or parse_nth_weekday(when_mode)
    if nth:
        number, weekday, month = nth
        if month != on.month:
            return False
        scheduled = _nth_date(on.year, month, weekday, number)
        return scheduled == on

    if "selected" in when_mode:
        month = parse_month_name(date_text) or parse_month_name(when_mode)
        if month and month != on.month:
            return False
        days = _parse_day_list(days_text)
        return on.day in days if days else False

    if _is_whole_month(when_mode):
        month = parse_month_name(date_text) or parse_month_name(when_mode)
        if month:
            return month == on.month
        parsed = parse_month_day(date_text)
        return bool(parsed) and parsed[0] == on.month

    parsed = parse_month_day(date_text)
    if parsed:
        return parsed == (on.month, on.day)

    month = parse_month_name(date_text)
    if month:
        return month == on.month

    if not date_text and not days_text:
        return when_mode in {"", "one-day", "one day", "today", "single"}
    return False


def _display_names(text: str) -> list[str]:
    names: list[str] = []
    for part in re.split(r"\s*(?:,|;|/|&|\band\b)\s*", str(text or ""), flags=re.I):
        display = _collapse(part)
        if display.lower().startswith("dj "):
            display = display[3:].strip()
        key = normalize_host(display)
        if key and key not in {"any", "any dj", "(any dj)", "each dj"}:
            names.append(display)
    return names


def _split_names(text: str) -> list[str]:
    return [normalize_host(name) for name in _display_names(text)]


def _audience_mode(day: dict) -> str:
    who = str(day.get("who") or "").strip().lower()
    if "selected" in who or who.startswith("only "):
        return "selected"
    if who.startswith("each") or who in {"", "any", "any dj", "(any dj)", "all", "all djs"}:
        return "each"
    return "named"


def _read_by_names(day: dict) -> list[str]:
    return _split_names(str(day.get("read_by") or ""))


def host_allowed(day: dict, host: str | None) -> bool:
    """Selected-DJ filter. Each DJ includes everyone except Casey and Mo Blues."""
    if host is None:
        return True
    name = normalize_host(host)
    if not name:
        return _audience_mode(day) != "selected"

    readers = _read_by_names(day)
    if readers and name not in readers:
        return False

    mode = _audience_mode(day)
    if mode == "selected":
        allowed = _split_names(str(day.get("selected_djs") or ""))
        return name in allowed
    if mode == "named":
        return name == normalize_host(str(day.get("who") or ""))
    return name not in _EXCLUDED_FROM_EACH


def read_by_label(day: dict) -> str:
    readers = _display_names(str(day.get("read_by") or ""))
    if readers:
        return ", ".join(readers)
    mode = _audience_mode(day)
    if mode == "selected":
        names = _display_names(str(day.get("selected_djs") or ""))
        return ", ".join(names) if names else "(selected DJs)"
    if mode == "named":
        return _collapse(day.get("who")) or "(any DJ)"
    return "(any DJ)"


def is_already_aired(day: dict, on: date | None) -> bool:
    if day.get("already_aired"):
        return True
    aired_on = str(day.get("aired_on") or "").strip()
    if not aired_on or on is None:
        return False
    full = _parse_iso_date(aired_on)
    if full:
        return full == on
    parsed = parse_month_day(aired_on)
    return bool(parsed) and parsed == (on.month, on.day)


def is_eligible(day: dict, on: date | None, host: str | None) -> bool:
    if not str(day.get("title") or "").strip():
        return False
    if not day.get("enabled", True):
        return False
    if is_already_aired(day, on):
        return False
    if not occurs_on(day, on):
        return False
    return host_allowed(day, host)


def fun_days_for_date(fun_days: list | None, when: date | datetime | None = None) -> list[dict]:
    """Every fun day the editor should still list for this date, including disabled ones."""
    on = station_day(when)
    listed: list[dict] = []
    for raw in fun_days or []:
        day = normalize_day(raw)
        if day["title"] and occurs_on(day, on):
            listed.append(day)
    return listed


def active_fun_days(
    fun_days: list | None,
    *,
    when: date | datetime | None = None,
    host: str | None = None,
) -> list[dict]:
    """Fun days a break may say: on, scheduled today, not already aired, allowed for this DJ."""
    on = station_day(when)
    active: list[dict] = []
    for raw in fun_days or []:
        day = normalize_day(raw)
        if is_eligible(day, on, host):
            active.append(day)
    return active


def _time_minutes(row: dict | None) -> int | None:
    if not row:
        return None
    raw = row.get("Time") or row.get("time") or row.get("break_time") or ""
    match = _TIME_RE.fullmatch(str(raw).strip().lower().replace(".", ""))
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2))
    suffix = match.group(3)
    if suffix == "pm" and hour < 12:
        hour += 12
    if suffix == "am" and hour == 12:
        hour = 0
    if hour > 23 or minute > 59:
        return None
    return hour * 60 + minute


def _explicit_index(row: dict | None) -> int | None:
    if not row:
        return None
    for key in ("index", "Index", "BreakIndex", "break_index"):
        if key not in row or row.get(key) in (None, ""):
            continue
        try:
            return int(row.get(key))
        except (TypeError, ValueError):
            continue
    return None


def _host_of(row: dict | None) -> str:
    if not row:
        return ""
    return str(row.get("Host") or row.get("host") or row.get("DJ") or "").strip()


def format_clock(minutes: int) -> str:
    hour, minute = divmod(minutes, 60)
    suffix = "AM" if hour < 12 else "PM"
    hour12 = hour % 12 or 12
    return f"{hour12}:{minute:02d} {suffix}"


def order_breaks(day_breaks: list | None) -> list[dict]:
    """Breaks in the order they air: clock time, then schedule order."""
    decorated: list[tuple[tuple[int, int, int], dict]] = []
    for position, row in enumerate(day_breaks or []):
        if not isinstance(row, dict):
            continue
        minutes = _time_minutes(row)
        explicit = _explicit_index(row)
        # Missing times sort after timed breaks and keep the order they were given.
        time_key = minutes if minutes is not None else 24 * 60 + position
        tie = explicit if explicit is not None else position
        decorated.append(((time_key, tie, position), row))
    decorated.sort(key=lambda item: item[0])
    return [row for _, row in decorated]


def _same_break(left: dict, right: dict) -> bool:
    left_time = _time_minutes(left)
    right_time = _time_minutes(right)
    if left_time is None or right_time is None or left_time != right_time:
        return False
    if normalize_host(_host_of(left)) != normalize_host(_host_of(right)):
        return False
    left_index = _explicit_index(left)
    right_index = _explicit_index(right)
    if left_index is not None and right_index is not None and left_index != right_index:
        return False
    return True


def rotation_slot(break_row: dict | None, day_breaks: list | None) -> int:
    """Stable position of this break among the day's breaks.

    Sorting by air time means a rebuilt prompt for 2:30 PM still lands on the
    same turn even if the schedule list was shuffled.
    """
    ordered = order_breaks(day_breaks if day_breaks else ([break_row] if break_row else []))
    if break_row is None:
        return 0
    for position, row in enumerate(ordered):
        if row is break_row:
            return position
    matches = [position for position, row in enumerate(ordered) if _same_break(row, break_row)]
    if len(matches) == 1:
        return matches[0]
    explicit = _explicit_index(break_row)
    if explicit is not None and matches:
        for position in matches:
            if _explicit_index(ordered[position]) == explicit:
                return position
    if matches:
        return matches[0]
    if explicit is not None:
        return explicit
    return 0


def chosen_fun_day(
    fun_days: list | None,
    break_row: dict | None = None,
    day_breaks: list | None = None,
    *,
    when: date | datetime | None = None,
    host: str | None = None,
) -> dict | None:
    """The one fun day this break should say, or None."""
    host_name = host if host is not None else _host_of(break_row)
    eligible = active_fun_days(fun_days, when=when, host=host_name)
    if not eligible:
        return None
    if len(eligible) == 1:
        return eligible[0]
    slot = rotation_slot(break_row, day_breaks)
    return eligible[slot % len(eligible)]


def format_prompt_payload(days: list | None) -> str:
    """Prompt text for the fun days in `days`. Pass one day for a break."""
    lines = ["Today's fun / national days:", "fun days:"]
    wrote = False
    for raw in days or []:
        day = normalize_day(raw)
        if not day["title"]:
            continue
        wrote = True
        lines.append(f"- title: {day['title']}")
        lines.append(f"  read by: {read_by_label(day)}")
        if day["note"]:
            lines.append(f"  notes: {day['note']}")
        lines.append(f"  {prompt_line_for_category(day.get('category') or FUNNY)}")
    if not wrote:
        return ""
    return "\n".join(lines)


def prompt_payload_for_break(
    fun_days: list | None,
    break_row: dict | None = None,
    day_breaks: list | None = None,
    *,
    when: date | datetime | None = None,
    host: str | None = None,
) -> str:
    """Prompt block for one break. Never stacks every same-day fun day."""
    chosen = chosen_fun_day(fun_days, break_row, day_breaks, when=when, host=host)
    if not chosen:
        return ""
    return format_prompt_payload([chosen])


def _clock_minutes(now: date | datetime | time | int | None) -> int | None:
    if isinstance(now, datetime):
        return now.hour * 60 + now.minute
    if isinstance(now, time):
        return now.hour * 60 + now.minute
    if isinstance(now, int):
        return now
    return None


def select_preview_break(day_breaks: list | None, now: datetime | time | int | None = None) -> dict | None:
    """The break the preview should speak for: the next one at or after `now`."""
    ordered = order_breaks(day_breaks)
    if not ordered:
        return None
    now_minutes = _clock_minutes(now)
    if now_minutes is None:
        return ordered[0]
    for row in ordered:
        minutes = _time_minutes(row)
        if minutes is not None and minutes >= now_minutes:
            return row
    return ordered[-1]


def _break_label(row: dict) -> str:
    minutes = _time_minutes(row)
    clock = format_clock(minutes) if minutes is not None else ""
    host = _host_of(row)
    if clock and host:
        return f"{clock}, {host}"
    return clock or host or "this break"


def _next_ordered_break(ordered: list[dict], current: dict) -> dict | None:
    for position, row in enumerate(ordered):
        if row is current or _same_break(row, current):
            if position + 1 < len(ordered):
                return ordered[position + 1]
            return None
    return None


def preview_prompt_payload(
    fun_days: list | None,
    day_breaks: list | None = None,
    *,
    when: date | datetime | None = None,
    now: datetime | time | int | None = None,
) -> str:
    """What the Fun Days preview should show for the next break.

    One fun day, same as that break's prompt. When several days share the date,
    a short note names the fun day the following break will get.
    """
    ordered = order_breaks(day_breaks)
    current = select_preview_break(ordered, now)
    if current is None:
        current = {"Host": "Mo", "Time": "00:00", "index": 0}
        ordered = [current]

    payload = prompt_payload_for_break(fun_days, current, ordered, when=when)
    scheduled = [
        day
        for day in fun_days_for_date(fun_days, when)
        if day.get("enabled", True) and not is_already_aired(day, station_day(when))
    ]
    if len(scheduled) <= 1:
        return payload

    following = _next_ordered_break(ordered, current)
    next_day = chosen_fun_day(fun_days, following, ordered, when=when) if following else None
    current_day = chosen_fun_day(fun_days, current, ordered, when=when)
    note = ""
    if next_day and (not current_day or next_day["title"] != current_day["title"]):
        note = f"\n\nNext up: {next_day['title']}"
    if not payload and not note:
        return ""
    return f"This break: {_break_label(current)}\n{payload}{note}"

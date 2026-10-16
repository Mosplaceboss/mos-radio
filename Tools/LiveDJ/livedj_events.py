"""LiveDJ schedule event types and mission coaching (event-driven breaks)."""

from __future__ import annotations

import json
import re
from pathlib import Path

_MPR_ROOT = Path(__file__).resolve().parents[3]
STATION_FORMATS_FILE = _MPR_ROOT / "Config" / "station_formats.json"

# Only these event types may close a shift or name a next host.
HANDOFF_EVENT_TYPES: frozenset[str] = frozenset({"Handoff", "Show Close"})

# Known on-air host names used to catch invented handoffs in generated scripts.
KNOWN_HOST_NAMES: tuple[str, ...] = (
    "Mo",
    "Casey",
    "Kathy",
    "Johnny",
    "Dave",
    "LB",
    "Piper",
)

_HANDOFF_PHRASE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.I)
    for pattern in (
        r"\bhand(?:ing)?\s+(?:it|you|the\s+show)\s+over\b",
        r"\bhand(?:ing)?\s+off\b",
        r"\bhandoff\b",
        r"\bturn(?:ing)?\s+(?:it|things|the\s+show)\s+over\s+to\b",
        r"\bsign(?:ing)?\s+off\b",
        r"\bclos(?:e|ing)\s+out\s+(?:the\s+)?(?:show|shift)\b",
        r"\bwrap(?:ping)?\s+up\s+(?:the\s+)?(?:show|shift)\b",
        r"\bthat(?:'s| is)\s+(?:gonna|going\s+to)\s+be\s+it\s+for\s+(?:me|us)\b",
        r"\btake\s+it\s+away\b",
        r"\bpass(?:ing)?\s+(?:the\s+)?(?:mic|baton)\s+to\b",
        r"\bover\s+to\s+(?:my\s+friend\s+)?(?:"
        + "|".join(re.escape(name) for name in KNOWN_HOST_NAMES)
        + r")\b",
        r"\b(?:"
        + "|".join(re.escape(name) for name in KNOWN_HOST_NAMES)
        + r")\s+is\s+(?:up\s+next|taking\s+over|coming\s+on|coming\s+up\s+next)\b",
    )
)

_SHOW_OPEN_CLOSER_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.I)
    for pattern in (
        r"\bthanks?\s+for\s+(?:listening|tuning\s+in)\b.*\b(?:next|handoff|hand\s+off|over\s+to)\b",
        r"\bclosing\s+(?:out\s+)?(?:the\s+)?show\b",
        r"\bend(?:ing)?\s+(?:my|the)\s+(?:show|shift)\b",
        r"\bsee\s+you\s+(?:next\s+time|tomorrow)\b",
        r"\bgoodbye\b",
        r"\bso\s+long\b",
    )
)

EVENT_TYPES: tuple[str, ...] = (
    "Show Open",
    "Check-In",
    "Artist Spotlight",
    "Music Story",
    "This Day in Music History",
    "On This Day in the 70s",
    "Coming Up",
    "Coming Up Next",
    "Today's Countdown",
    "Final Half Hour",
    "Listener Memory",
    "Weekend Check-In",
    "Format Change",
    "Handoff",
    "Show Close",
)

DEFAULT_STATION_FORMATS: tuple[str, ...] = (
    "Daily Mix",
    "Classic Rock",
    "Trop Rock",
    "Blues",
    "Casey 70's",
    "Country",
    "Soft Rock",
    "Yacht Rock",
)

_NO_HANDOFF_COACHING = """
Do not close the show, sign off, wrap up the shift, or hand off to another host.
Ignore any Next host field in schedule context for this break.
Never invent a next host (including Kathy, Mo, Casey, Johnny, Dave, or LB).
""".strip()

EVENT_COACHING: dict[str, str] = {
    "Show Open": f"""
Welcome listeners.
Mention the day and time naturally.
Mention the show's format.
Tease two or three upcoming artists from the supplied music context.
Sound like the host's personality profile — never read like a generic announcer.
Do not invent countdown rankings, chart positions, or "#1 song" claims unless explicitly supplied.
This is a show OPEN — start the shift with energy. Never use closer or handoff language.
{_NO_HANDOFF_COACHING}
""".strip(),
    "Check-In": f"""
Mention the current time of day.
Comment on the mood that fits this daypart.
Reference a previous or upcoming song when it feels natural.
Keep it conversational.
{_NO_HANDOFF_COACHING}
""".strip(),
    "Weekend Check-In": f"""
Mention the current time of day.
Comment on the weekend mood naturally using the CURRENT calendar in STATION CONTEXT.
If today is Saturday or Sunday, we are already in the weekend — never say "this coming weekend".
Reference a previous or upcoming song when it feels natural.
Keep it relaxed and conversational.
{_NO_HANDOFF_COACHING}
""".strip(),
    "Artist Spotlight": f"""
Share one verified fact about the next artist using only supplied context.
Do not invent biographical details.
Transition naturally into the next song.
{_NO_HANDOFF_COACHING}
""".strip(),
    "Music Story": f"""
Share a brief music-related observation tied to an upcoming song or artist.
Use only supplied context — do not invent facts.
Keep it conversational, not encyclopedic.
{_NO_HANDOFF_COACHING}
""".strip(),
    "This Day in Music History": f"""
Open warmly and personally — something in the spirit of: you're sitting there thinking back on music history and you'd like to share a few with the listener.
Keep that intro fun and engaging; vary the wording so it does not sound identical every day.
Then share three This Day in Music History moments using ONLY the supplied music-history source facts.
Do not invent dates, chart claims, album titles, birthdays, or other history.
Invite listeners to jump into the conversation on Facebook at Mo's Place Radio Boston — ask what memory or favorite moment these bring up.
Keep it conversational, then return to the music.
{_NO_HANDOFF_COACHING}
""".strip(),
    "On This Day in the 70s": f"""
Open like a warm 1970s radio host looking back on this calendar date in the seventies.
Share three On This Day moments using ONLY the supplied 1970-1979 source facts.
Topics can be music, movies, TV, sports, pop culture, or other popular 1970s moments — stay inside 1970-1979.
Do not invent dates, titles, scores, or other history.
Keep it nostalgic and conversational, then return to the music.
{_NO_HANDOFF_COACHING}
""".strip(),
    "Coming Up": f"""
Tease several upcoming artists or songs from the supplied list.
Do not sound repetitive or like a laundry list.
Do not promise exact timing or order.
{_NO_HANDOFF_COACHING}
""".strip(),
    "Coming Up Next": f"""
Tease what is coming up next on the show from the supplied music context.
Mention the time of day when natural (for example noon or the final hour).
Keep it conversational and avoid promising exact song order.
{_NO_HANDOFF_COACHING}
""".strip(),
    "Today's Countdown": f"""
Talk about why this era of music remains memorable.
Reference the show format naturally.
Tease the next song or artist from the supplied queue without inventing chart ranks.
{_NO_HANDOFF_COACHING}
""".strip(),
    "Final Half Hour": f"""
Preview the final half hour of the show.
Tease upcoming music from the supplied queue.
Keep energy appropriate for winding down while still sounding engaged.
{_NO_HANDOFF_COACHING}
""".strip(),
    "Listener Memory": f"""
Connect with listeners in a warm, personal way when appropriate.
Do not invent caller names, dedications, or request details unless supplied.
{_NO_HANDOFF_COACHING}
""".strip(),
    "Format Change": f"""
Acknowledge the shift in format or show direction naturally.
Set expectations for what listeners will hear next.
Keep it brief.
{_NO_HANDOFF_COACHING}
""".strip(),
    "Handoff": """
Wrap up briefly.
Thank listeners if natural.
Clearly identify who is leaving and who is taking over.
Hand off ONLY to the Next host named in the schedule context.
If Next host is blank, thank listeners without naming a replacement.
Never invent a next host and never default to Mo or Kathy unless Next host is that person.
""".strip(),
    "Show Close": """
Wrap up the shift.
Thank listeners sincerely.
If a Next host is named in the schedule context, hand off to that host by name.
If Next host is blank, close without naming a replacement host.
Never invent a next host and never default to Mo or Kathy unless Next host is that person.
""".strip(),
}

LEGACY_MISSION_MAP: dict[str, str] = {
    "welcome": "Show Open",
    "drive_home_welcome": "Show Open",
    "daily_mix_welcome": "Show Open",
    "lunchtime_welcome": "Show Open",
    "music_story": "Music Story",
    "personality": "Check-In",
    "current_or_facebook": "Check-In",
    "current_item": "Check-In",
    "pre_handoff_lunch": "Handoff",
    "signoff_to_johnny": "Handoff",
    "signoff": "Handoff",
    "handoff": "Handoff",
    "format_transition": "Format Change",
    "daily_mix_return": "Format Change",
    "saturday_show_open": "Show Open",
}

LEGACY_MISSION_TEXT: dict[str, str] = {
    "welcome": (
        "Welcome listeners, mention the day, introduce the format, and tease upcoming music. "
        "Do not close the show or hand off to another host."
    ),
    "drive_home_welcome": (
        "Welcome listeners to the drive-home show and tease upcoming music. "
        "Do not close the show or hand off to another host."
    ),
    "daily_mix_welcome": (
        "Welcome listeners to the Daily Mix and tease upcoming artists. "
        "Do not close the show or hand off to another host."
    ),
    "lunchtime_welcome": (
        "Welcome listeners to the lunchtime show and set a relaxed mood. "
        "Do not close the show or hand off to another host."
    ),
    "music_story": "Share a brief music-related observation tied to an upcoming song or artist.",
    "personality": "Check in with listeners in the host's natural voice.",
    "current_or_facebook": "Check in with listeners and reference the current daypart naturally.",
    "current_item": "Check in with listeners and reference the current song or daypart.",
    "pre_handoff_lunch": "Wrap up briefly and hand off only to the Next host named in the schedule.",
    "signoff_to_johnny": "Thank listeners and hand off only to the Next host named in the schedule.",
    "signoff": "Thank listeners and hand off only if a Next host is named; never invent a replacement.",
    "handoff": "Wrap up briefly and hand off only to the Next host named in the schedule.",
    "format_transition": "Acknowledge the format change and set expectations for what is coming next.",
    "daily_mix_return": "Acknowledge the return to Daily Mix and tease upcoming music.",
    "saturday_show_open": (
        "Welcome listeners, mention Saturday morning, introduce Casey 70's, and tease upcoming artists. "
        "Do not close the show or hand off to another host."
    ),
}

DEFAULT_MISSIONS: dict[str, str] = {
    "Show Open": (
        "Welcome listeners, mention the day, introduce the format, and tease upcoming music. "
        "Do not close the show or hand off to another host."
    ),
    "Check-In": "Check in with listeners and reference the current daypart naturally.",
    "Weekend Check-In": "Weekend check-in and mention two upcoming artists.",
    "Artist Spotlight": "Share one brief verified fact about an upcoming artist.",
    "Music Story": "Share a brief music-related observation tied to an upcoming song or artist.",
    "This Day in Music History": (
        "Open like you're sitting there thinking back on music history and want to share a few "
        "fun facts with the listener. Share three facts from the supplied factual source only — "
        "do not invent history. Invite conversation on Facebook at Mo's Place Radio Boston."
    ),
    "On This Day in the 70s": (
        "Look back on this calendar date in the 1970s. Share three facts from the supplied "
        "1970-1979 source only — music, movies, sports, pop culture, or other popular moments. "
        "Do not invent history."
    ),
    "Coming Up": "Tease upcoming music without promising exact timing or order.",
    "Coming Up Next": "Preview what is coming up next and set expectations for the rest of the show.",
    "Today's Countdown": "Talk about why this era of music remains memorable and tease the next song.",
    "Final Half Hour": "Preview the final half hour and tease upcoming music.",
    "Listener Memory": "Connect with listeners in a warm, personal way when appropriate.",
    "Format Change": "Acknowledge the format change and set expectations for what is coming next.",
    "Handoff": "Wrap up briefly and hand off only to the Next host named in the schedule.",
    "Show Close": (
        "Thank listeners and close the show. Hand off only if a Next host is named; "
        "never invent a replacement host."
    ),
}

LEGACY_TYPE_MAP: dict[str, str] = {
    "clock_in": "Show Open",
    "check_in": "Check-In",
    "format_change": "Format Change",
    "handoff": "Handoff",
    "close": "Show Close",
}

EVENT_TO_TYPE: dict[str, str] = {
    "Show Open": "clock_in",
    "Check-In": "check_in",
    "Weekend Check-In": "check_in",
    "Artist Spotlight": "check_in",
    "Music Story": "check_in",
    "This Day in Music History": "check_in",
    "On This Day in the 70s": "check_in",
    "Coming Up": "check_in",
    "Coming Up Next": "check_in",
    "Today's Countdown": "check_in",
    "Final Half Hour": "check_in",
    "Listener Memory": "check_in",
    "Format Change": "format_change",
    "Handoff": "handoff",
    "Show Close": "close",
}


def _load_station_formats_file() -> list[str]:
    if not STATION_FORMATS_FILE.is_file():
        return []
    try:
        data = json.loads(STATION_FORMATS_FILE.read_text(encoding="utf-8-sig"))
    except Exception:
        return []
    values = data.get("formats", data if isinstance(data, list) else [])
    return [str(item).strip() for item in values if str(item).strip()]


def station_format_choices(hosts: dict | None = None) -> list[str]:
    choices = set(DEFAULT_STATION_FORMATS)
    choices.update(_load_station_formats_file())
    for host in (hosts or {}).values():
        for fmt in host.get("formats") or []:
            text = str(fmt or "").strip()
            if text:
                choices.add(text)
    return sorted(choices, key=str.lower)


def normalize_event_type(value: str, break_type: str = "") -> str:
    text = str(value or "").strip()
    if text in EVENT_TYPES:
        return text
    key = text.lower().replace(" ", "_").replace("-", "_")
    if key in LEGACY_MISSION_MAP:
        return LEGACY_MISSION_MAP[key]
    if text:
        for event in EVENT_TYPES:
            if event.lower() == text.lower():
                return event
    type_key = str(break_type or "").strip().lower()
    if type_key in LEGACY_TYPE_MAP:
        return LEGACY_TYPE_MAP[type_key]
    if text:
        return text
    return "Check-In"


def _legacy_mission_key(value: str) -> str:
    return str(value or "").strip().lower().replace(" ", "_").replace("-", "_")


def _mission_is_event_type_name(mission: str, event_type: str) -> bool:
    text = str(mission or "").strip()
    if not text:
        return False
    if text in EVENT_TYPES:
        return True
    return normalize_event_type(text) == event_type and len(text) <= 40


def default_mission_for_event_type(event_type: str) -> str:
    normalized = normalize_event_type(event_type)
    return DEFAULT_MISSIONS.get(normalized, DEFAULT_MISSIONS["Check-In"])


def _infer_event_type_from_mission_text(mission: str) -> str | None:
    lower = str(mission or "").strip().lower()
    hints = (
        ("weekend check-in", "Weekend Check-In"),
        ("weekend check in", "Weekend Check-In"),
        ("preview the final hour", "Coming Up Next"),
        ("preview the final half hour", "Final Half Hour"),
        ("70's music remains memorable", "Today's Countdown"),
        ("why 70's music remains memorable", "Today's Countdown"),
        ("verified fact about an upcoming", "Artist Spotlight"),
        ("verified fact about an upcoming 70's artist", "Artist Spotlight"),
        ("thank listeners, close the show", "Show Close"),
        ("welcome listeners, mention saturday morning", "Show Open"),
        ("this day in music history", "This Day in Music History"),
        ("this day in music", "This Day in Music History"),
        ("on this day in the 1970s", "On This Day in the 70s"),
        ("on this day in the 70s", "On This Day in the 70s"),
        ("70s on this day", "On This Day in the 70s"),
    )
    for needle, event_type in hints:
        if needle in lower:
            return event_type
    return None


def event_type_for_row(row: dict) -> str:
    explicit = str(row.get("EventType") or row.get("event_type") or "").strip()
    if explicit:
        return normalize_event_type(explicit)

    mission = str(row.get("Mission") or row.get("mission") or "").strip()
    break_type = str(row.get("Type") or row.get("type") or "").strip()
    legacy_key = _legacy_mission_key(mission)
    if legacy_key in LEGACY_MISSION_MAP or mission in EVENT_TYPES:
        return normalize_event_type(mission, break_type)

    inferred = _infer_event_type_from_mission_text(mission)
    if inferred:
        return inferred

    if break_type:
        return normalize_event_type("", break_type)
    return "Check-In"


def allows_host_handoff(row: dict) -> bool:
    """True only for Handoff / Show Close breaks."""
    return event_type_for_row(row) in HANDOFF_EVENT_TYPES


def row_next_host(row: dict) -> str:
    return str(row.get("NextHost") or row.get("next_host") or "").strip()


def prompt_next_host(row: dict) -> str:
    """Next host name for generation prompts — blank unless this break may hand off."""
    if not allows_host_handoff(row):
        return ""
    return row_next_host(row)


def handoff_mission_hint(row: dict) -> str:
    """Short mission/coaching reminder so opens never close or invent a next host."""
    event_type = event_type_for_row(row)
    next_host = row_next_host(row)
    if event_type == "Show Open":
        return (
            "Show Open only: welcome and start the show — do not close, sign off, "
            "or hand off to another host. Ignore any Next host field."
        )
    if event_type not in HANDOFF_EVENT_TYPES:
        return "Do not close the show or hand off to another host on this break."
    if next_host:
        return f"Hand off only to {next_host}. Do not invent a different next host."
    return "No Next host is scheduled — thank listeners without naming a replacement host."


def apply_handoff_rules_to_mission(row: dict, mission: str) -> str:
    hint = handoff_mission_hint(row)
    text = str(mission or "").strip()
    if not text:
        return hint

    lower = text.lower()
    hint_lower = hint.lower()
    # Avoid stacking an identical / overlapping guard.
    if hint_lower in lower:
        return text
    if event_type_for_row(row) == "Show Open":
        if "ignore any next host" in lower and "do not close" in lower:
            return text
    elif event_type_for_row(row) in HANDOFF_EVENT_TYPES:
        if ("hand off only to" in lower or "without naming a replacement" in lower) and (
            "hand off only to" in hint_lower or "without naming a replacement" in hint_lower
        ):
            return text
    elif "do not close the show or hand off to another host on this break" in lower:
        return text

    return f"{text} {hint}".strip()


def _host_mentioned_as_takeover(script: str, host_name: str) -> bool:
    name = re.escape(str(host_name or "").strip())
    if not name:
        return False
    patterns = (
        rf"\bover\s+to\s+(?:my\s+friend\s+)?{name}\b",
        rf"\bhand(?:ing)?\s+(?:it|you|the\s+show)\s+over\s+to\s+{name}\b",
        rf"\bturn(?:ing)?\s+(?:it|things|the\s+show)\s+over\s+to\s+{name}\b",
        rf"\b{name}\s+is\s+(?:up\s+next|taking\s+over|coming\s+on|coming\s+up\s+next)\b",
        rf"\btake\s+it\s+away,?\s+{name}\b",
    )
    return any(re.search(pattern, script or "", flags=re.I) for pattern in patterns)


def banned_closer_or_handoff_in_text(row: dict, script: str) -> list[str]:
    """Return closer/handoff problems found in a generated script for this row."""
    text = str(script or "").strip()
    if not text:
        return []

    findings: list[str] = []
    event_type = event_type_for_row(row)
    allowed_next = prompt_next_host(row)
    allowed_key = re.sub(r"[\s_\-]+", "", allowed_next.lower())

    if not allows_host_handoff(row):
        for pattern in _HANDOFF_PHRASE_PATTERNS:
            if pattern.search(text):
                findings.append("handoff_language")
                break
        if event_type == "Show Open":
            for pattern in _SHOW_OPEN_CLOSER_PATTERNS:
                if pattern.search(text):
                    findings.append("show_open_closer_language")
                    break
        for host_name in KNOWN_HOST_NAMES:
            host_key = re.sub(r"[\s_\-]+", "", host_name.lower())
            current_host = re.sub(
                r"[\s_\-]+",
                "",
                str(row.get("Host") or row.get("host") or "").strip().lower(),
            )
            if host_key and host_key == current_host:
                continue
            if _host_mentioned_as_takeover(text, host_name):
                findings.append(f"invented_next_host:{host_name}")
        return findings

    # Handoff / Show Close: allow the scheduled Next host only.
    for host_name in KNOWN_HOST_NAMES:
        host_key = re.sub(r"[\s_\-]+", "", host_name.lower())
        if allowed_key and host_key == allowed_key:
            continue
        if _host_mentioned_as_takeover(text, host_name):
            if not allowed_key:
                findings.append(f"invented_next_host:{host_name}")
            else:
                findings.append(f"wrong_next_host:{host_name}")
    return findings


def mission_text_for_row(row: dict) -> str:
    mission = str(row.get("Mission") or row.get("mission") or "").strip()
    event_type = event_type_for_row(row)
    if not mission:
        mission = default_mission_for_event_type(event_type)
    else:
        legacy_key = _legacy_mission_key(mission)
        if legacy_key in LEGACY_MISSION_TEXT:
            mission = LEGACY_MISSION_TEXT[legacy_key]
        elif legacy_key in LEGACY_MISSION_MAP and _mission_is_event_type_name(mission, event_type):
            mission = LEGACY_MISSION_TEXT.get(legacy_key, default_mission_for_event_type(event_type))
        elif _mission_is_event_type_name(mission, event_type):
            mission = default_mission_for_event_type(event_type)

    return apply_handoff_rules_to_mission(row, mission)


def finalize_schedule_row(row: dict[str, str]) -> dict[str, str]:
    result = dict(row)
    mission = str(result.get("Mission") or "").strip()
    break_type = str(result.get("Type") or "").strip()
    event_type = str(result.get("EventType") or "").strip()

    if not event_type:
        legacy_key = _legacy_mission_key(mission)
        if legacy_key in LEGACY_MISSION_MAP or mission in EVENT_TYPES:
            event_type = normalize_event_type(mission, break_type)
        else:
            inferred = _infer_event_type_from_mission_text(mission)
            event_type = inferred or normalize_event_type("", break_type)

    legacy_key = _legacy_mission_key(mission)
    if legacy_key in LEGACY_MISSION_MAP:
        if legacy_key in LEGACY_MISSION_TEXT:
            mission = LEGACY_MISSION_TEXT[legacy_key]
        elif _mission_is_event_type_name(mission, event_type):
            mission = default_mission_for_event_type(event_type)
    elif _mission_is_event_type_name(mission, event_type):
        mission = default_mission_for_event_type(event_type)
    elif not mission:
        mission = default_mission_for_event_type(event_type)

    result["EventType"] = normalize_event_type(event_type)
    result["Mission"] = apply_handoff_rules_to_mission(result, mission)
    if not break_type:
        result["Type"] = schedule_type_for_event(result["EventType"])
    return result


def schedule_type_for_event(event_type: str) -> str:
    return EVENT_TO_TYPE.get(event_type, "check_in")


def event_coaching(event_type: str) -> str:
    normalized = normalize_event_type(event_type)
    return EVENT_COACHING.get(normalized, EVENT_COACHING["Check-In"])


def event_coaching_for_row(row: dict) -> str:
    """Coaching for a schedule row, including open/close handoff guards."""
    base = event_coaching(event_type_for_row(row))
    hint = handoff_mission_hint(row)
    if not hint or hint.lower() in base.lower():
        return base
    return f"{base}\n{hint}".strip()

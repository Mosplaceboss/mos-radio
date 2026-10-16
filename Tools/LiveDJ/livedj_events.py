"""LiveDJ schedule event types and mission coaching (event-driven breaks)."""

from __future__ import annotations

import json
from pathlib import Path

_MPR_ROOT = Path(__file__).resolve().parents[3]
STATION_FORMATS_FILE = _MPR_ROOT / "Config" / "station_formats.json"

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

# DJs were stacking Request Song and Community in one cart. One listener CTA per
# break is enough — alternate across breaks. Applies to every host.
_LISTENER_CTA_COACHING = """
Never mention both song requests and Community in the same break.
Pick one listener CTA per break — Request Song or Community — and save the other for a later break.
Alternating across breaks is fine. This applies to every host/DJ.
Do not repeat the same CTA or closer line twice inside one break.
""".strip()

_LISTENER_CTA_EVENT_TYPES = frozenset(
    {
        "Show Open",
        "Check-In",
        "Weekend Check-In",
        "Artist Spotlight",
        "Music Story",
        "Coming Up",
        "Coming Up Next",
        "Today's Countdown",
        "Final Half Hour",
        "Listener Memory",
        "Format Change",
    }
)

EVENT_COACHING: dict[str, str] = {
    "Show Open": f"""
Welcome listeners.
Mention the day and time naturally.
Mention the show's format.
Tease two or three upcoming artists from the supplied music context.
Sound like the host's personality profile — never read like a generic announcer.
Do not invent countdown rankings, chart positions, or "#1 song" claims unless explicitly supplied.
{_LISTENER_CTA_COACHING}
""".strip(),
    "Check-In": f"""
Mention the current time of day.
Comment on the mood that fits this daypart.
Reference a previous or upcoming song when it feels natural.
Keep it conversational.
{_LISTENER_CTA_COACHING}
""".strip(),
    "Weekend Check-In": f"""
Mention the current time of day.
Comment on the weekend mood naturally using the CURRENT calendar in STATION CONTEXT.
If today is Saturday or Sunday, we are already in the weekend — never say "this coming weekend".
Reference a previous or upcoming song when it feels natural.
Keep it relaxed and conversational.
{_LISTENER_CTA_COACHING}
""".strip(),
    "Artist Spotlight": f"""
Share one verified fact about the next artist using only supplied context.
Do not invent biographical details.
Transition naturally into the next song.
{_LISTENER_CTA_COACHING}
""".strip(),
    "Music Story": f"""
Share a brief music-related observation tied to an upcoming song or artist.
Use only supplied context — do not invent facts.
Keep it conversational, not encyclopedic.
{_LISTENER_CTA_COACHING}
""".strip(),
    "This Day in Music History": """
Open warmly and personally — something in the spirit of: you're sitting there thinking back on music history and you'd like to share a few with the listener.
Keep that intro fun and engaging; vary the wording so it does not sound identical every day.
Then share three This Day in Music History moments using ONLY the supplied music-history source facts.
Do not invent dates, chart claims, album titles, birthdays, or other history.
Invite listeners to jump into the conversation on Facebook at Mo's Place Radio Boston — ask what memory or favorite moment these bring up.
Keep it conversational, then return to the music.
""".strip(),
    "On This Day in the 70s": """
Open like a warm 1970s radio host looking back on this calendar date in the seventies.
Share three On This Day moments using ONLY the supplied 1970-1979 source facts.
Topics can be music, movies, TV, sports, pop culture, or other popular 1970s moments — stay inside 1970-1979.
Do not invent dates, titles, scores, or other history.
Keep it nostalgic and conversational, then return to the music.
""".strip(),
    "Coming Up": f"""
Tease several upcoming artists or songs from the supplied list.
Do not sound repetitive or like a laundry list.
Do not promise exact timing or order.
{_LISTENER_CTA_COACHING}
""".strip(),
    "Coming Up Next": f"""
Tease what is coming up next on the show from the supplied music context.
Mention the time of day when natural (for example noon or the final hour).
Keep it conversational and avoid promising exact song order.
{_LISTENER_CTA_COACHING}
""".strip(),
    "Today's Countdown": f"""
Talk about why this era of music remains memorable.
Reference the show format naturally.
Tease the next song or artist from the supplied queue without inventing chart ranks.
{_LISTENER_CTA_COACHING}
""".strip(),
    "Final Half Hour": f"""
Preview the final half hour of the show.
Tease upcoming music from the supplied queue.
Keep energy appropriate for winding down while still sounding engaged.
{_LISTENER_CTA_COACHING}
""".strip(),
    "Listener Memory": f"""
Connect with listeners in a warm, personal way when appropriate.
Do not invent caller names, dedications, or request details unless supplied.
{_LISTENER_CTA_COACHING}
""".strip(),
    "Format Change": f"""
Acknowledge the shift in format or show direction naturally.
Set expectations for what listeners will hear next.
Keep it brief.
{_LISTENER_CTA_COACHING}
""".strip(),
    "Handoff": """
Wrap up briefly.
Thank listeners if natural.
Clearly identify who is leaving and who is taking over.
Hand off ONLY to the Next host named in the schedule context.
Never invent a next host and never default to Mo unless Next host is Mo.
""".strip(),
    "Show Close": """
Wrap up the shift.
Thank listeners sincerely.
If a Next host is named in the schedule context, hand off to that host by name.
Never invent a next host and never default to Mo unless Next host is Mo.
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
    "welcome": "Welcome listeners, mention the day, introduce the format, and tease upcoming music.",
    "drive_home_welcome": "Welcome listeners to the drive-home show and tease upcoming music.",
    "daily_mix_welcome": "Welcome listeners to the Daily Mix and tease upcoming artists.",
    "lunchtime_welcome": "Welcome listeners to the lunchtime show and set a relaxed mood.",
    "music_story": "Share a brief music-related observation tied to an upcoming song or artist.",
    "personality": (
        "Check in with listeners in the host's natural voice. "
        "Mention Request Song or Community in this break, not both."
    ),
    "current_or_facebook": (
        "Check in with listeners and reference the current daypart naturally. "
        "Mention Request Song or Community in this break, not both."
    ),
    "current_item": (
        "Check in with listeners and reference the current song or daypart. "
        "Mention Request Song or Community in this break, not both."
    ),
    "pre_handoff_lunch": "Wrap up briefly and hand off to the next host.",
    "signoff_to_johnny": "Thank listeners and hand off to the next host.",
    "signoff": "Thank listeners and hand off to the next format or host.",
    "handoff": "Wrap up briefly and hand off to the next host.",
    "format_transition": "Acknowledge the format change and set expectations for what is coming next.",
    "daily_mix_return": "Acknowledge the return to Daily Mix and tease upcoming music.",
    "saturday_show_open": "Welcome listeners, mention Saturday morning, introduce Casey 70's, and tease upcoming artists.",
}

DEFAULT_MISSIONS: dict[str, str] = {
    "Show Open": "Welcome listeners, mention the day, introduce the format, and tease upcoming music.",
    "Check-In": (
        "Check in with listeners and reference the current daypart naturally. "
        "Mention Request Song or Community in this break, not both — alternating later is fine."
    ),
    "Weekend Check-In": (
        "Weekend check-in and mention two upcoming artists. "
        "Mention Request Song or Community in this break, not both."
    ),
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
    "Handoff": "Wrap up briefly and hand off to the next host.",
    "Show Close": "Thank listeners, close the show, and hand off to the next host or format.",
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


def listener_cta_mission_hint(row: dict) -> str:
    """Remind speaking breaks: Request Song or Community — not both in one cart."""
    event_type = event_type_for_row(row)
    if event_type not in _LISTENER_CTA_EVENT_TYPES:
        return ""
    return (
        "Mention Request Song or Community in this break, not both — "
        "alternating across breaks is fine for every DJ."
    )


def apply_listener_cta_rules_to_mission(row: dict, mission: str) -> str:
    hint = listener_cta_mission_hint(row)
    text = str(mission or "").strip()
    if not hint:
        return text
    lower = text.lower()
    if "request song or community" in lower and "not both" in lower:
        return text
    if not text:
        return hint
    return f"{text} {hint}".strip()


def _script_mentions_song_request(script: str) -> bool:
    lower = str(script or "").lower()
    needles = (
        "request song",
        "song request",
        "request a song",
        "requests are open",
        "submit a request",
        "send a request",
        "make a request",
        "listener request",
    )
    return any(needle in lower for needle in needles)


def _script_mentions_community(script: str) -> bool:
    lower = str(script or "").lower()
    needles = (
        "click community",
        "community to share",
        "through community",
        "on community",
        " community ",
        "community.",
        "community!",
        "community,",
    )
    if "community" not in lower:
        return False
    # Avoid false hits on "community radio" style phrases without a CTA.
    return any(needle in lower for needle in needles) or lower.strip().startswith("community")


def dual_listener_cta_symptoms(script: str) -> list[str]:
    """Flag scripts that mention both song requests and Community in one break."""
    text = str(script or "").strip()
    if not text:
        return []
    symptoms: list[str] = []
    has_request = _script_mentions_song_request(text)
    has_community = _script_mentions_community(text)
    if has_request and has_community:
        symptoms.append("request_and_community_same_break")
    return symptoms


def script_mentions_request_and_community(script: str) -> bool:
    """True when one break pitches both Request Song and Community."""
    return "request_and_community_same_break" in dual_listener_cta_symptoms(script)


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

    return apply_listener_cta_rules_to_mission(row, mission)


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
    result["Mission"] = apply_listener_cta_rules_to_mission(result, mission)
    if not break_type:
        result["Type"] = schedule_type_for_event(result["EventType"])
    return result


def schedule_type_for_event(event_type: str) -> str:
    return EVENT_TO_TYPE.get(event_type, "check_in")


def event_coaching(event_type: str) -> str:
    normalized = normalize_event_type(event_type)
    return EVENT_COACHING.get(normalized, EVENT_COACHING["Check-In"])


def event_coaching_for_row(row: dict) -> str:
    """Coaching for a schedule row, including Request Song / Community alternate rules."""
    base = event_coaching(event_type_for_row(row))
    hint = listener_cta_mission_hint(row)
    if not hint or hint.lower() in base.lower():
        return base
    return f"{base}\n{hint}".strip()
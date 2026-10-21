
import argparse
import csv
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from openai import OpenAI

from content_db import eligible_items, init_db, mark_used as mark_content_used
import community_announcements as community_ann
import facebook_birthdays as fb_birthdays
import fun_days as fun_days_module
import question_of_the_day as question_module

from daily_content_policy import (
    daily_content_priority_rules,
    fun_days_share_this_break,
    host_can_use_daily_content,
    infer_used_entry_ids,
    names_present_in_script,
    pending_daily_mentions,
    record_daily_content_break,
    record_daily_mentions,
    station_mention_rules,
)

from platform_paths import LIVE_BASE as BASE

from livedj_personalities import (
    ensure_host_active as _ensure_host_active,
    get_host,
    load_personalities,
    personality_file_path,
    resolve_host_key,
)
import bailey_books
import bailey_dogs
import bailey_friends_episodes as bailey_friends
import kathy_farmstand
import personality_topics
import listener_engagement
import local_talking_points
import check_in_openers
import mo_trop_rock_color
import moblues_blues_color
import personality_color
import catchphrase_shift
import rss_rotation
from livedj_context import build_break_context, format_context_block, format_local_detail_notes_block, load_music_context
import beverage_rules
from livedj_human_dj_rules import (
    cta_prompt_line,
    human_dj_final_checklist,
    pick_break_cta,
    repair_human_dj_script,
)
import break_structure
from livedj_daypart import daypart_phrase, format_clock, station_now
from livedj_events import (
    boundary_event_coaching,
    event_coaching,
    event_type_for_row,
    mission_text_for_row,
    schedule_type_for_event,
    suppress_song_teases_for_break,
)
from livedj_schedule import current_day_time, get_event_at, schedule_path
from new_music_tracker import (
    format_prompt_block as format_new_music_prompt_block,
    mark_announced_if_mentioned,
    select_new_music_additions,
)
from QueueEngine import refresh_upcoming_songs
from RSSReader import refresh_rss_headlines
from MusicHistory import (
    format_prompt_block as format_music_history_block,
    load_music_history_facts,
    refresh_music_history,
    wants_music_history,
)
from SeventiesOnThisDay import (
    format_prompt_block as format_seventies_block,
    load_seventies_facts,
    refresh_seventies_on_this_day,
    wants_seventies_on_this_day,
)
from track_facts import format_prompt_block as format_track_facts_block, track_facts_rules

_LARRY_HOSTS = frozenset({"moblues", "larry", "lowdown larry"})


def _is_larry_host(host: str) -> bool:
    return str(host or "").strip().lower() in _LARRY_HOSTS


def _blues_talk_module():
    """Larry-only. Other hosts must never import BluesTalk."""
    if "BluesTalk" in sys.modules:
        return sys.modules["BluesTalk"]
    import BluesTalk

    return BluesTalk


def _safe_print(message: str) -> None:
    """Log lines must not crash scheduled generation when RSS/titles have emoji."""
    text = str(message)
    try:
        print(text)
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, "encoding", None) or "ascii"
        print(text.encode(encoding, errors="replace").decode(encoding, errors="replace"))


SCHEDULE = schedule_path(BASE)
KNOWLEDGE = BASE / "Knowledge"
RSS_HEADLINES = KNOWLEDGE / "RSSHeadlines.json"
RULES = BASE / "Rules"
MISSIONS = BASE / "Missions"
AIRSTAFF = BASE / "AirStaff"
PROGRAMS = BASE / "Programs"

HOST_ALIASES = {
    "djmo": "mo",
    "djbailey": "bailey",
    "djjohnny": "johnnyj",
    "djjohnnyj": "johnnyj",
}


def normalize_host(host_key: str) -> str:
    host = resolve_host_key(host_key, aliases=HOST_ALIASES)
    if host:
        return host
    print(f"Unknown host: {host_key}")
    raise SystemExit(1)


def spoken_host_name(host_key: str, fallback: str = "") -> str:
    """On-air name from Personality Manager display_name."""
    try:
        host = get_host(host_key, aliases=HOST_ALIASES) or {}
        name = str(host.get("display_name") or "").strip()
        if name:
            return name
    except Exception:
        pass
    return fallback or host_key


def ensure_host_active(host_key: str) -> None:
    try:
        _ensure_host_active(host_key, aliases=HOST_ALIASES)
    except KeyError:
        print(f"Unknown host: {host_key}")
        raise SystemExit(1) from None
    except RuntimeError as exc:
        print(str(exc))
        raise SystemExit(1) from None


def build_scheduled_row(
    host: str,
    *,
    when: datetime,
    event_type: str,
    mission: str,
    format_name: str,
    schedule_type: str = "",
    next_host: str = "",
) -> dict[str, str]:
    host = normalize_host(host)
    next_key = normalize_host(next_host) if str(next_host or "").strip() else ""
    return {
        "day_of_week": when.strftime("%A"),
        "Time": when.strftime("%H:%M"),
        "Host": host,
        "Type": schedule_type or schedule_type_for_event(event_type),
        "EventType": event_type,
        "Mission": mission,
        "Format": format_name,
        "NextHost": next_key,
        "TargetWav": "",
        "CartId": "",
    }


def build_manual_row(host: str, *, now: datetime | None = None) -> dict[str, str]:
    when = now or station_now()
    format_name = "Daily Mix"
    try:
        host_settings = get_host(host, aliases=HOST_ALIASES)
        formats = host_settings.get("formats") or []
        if formats:
            format_name = str(formats[0])
    except KeyError:
        pass
    return {
        "Host": host,
        "day_of_week": when.strftime("%A"),
        "Time": when.strftime("%H:%M"),
        "Type": schedule_type_for_event("Check-In"),
        "Mission": "Check-In",
        "Format": format_name,
        "NextHost": "",
        "TargetWav": "",
        "CartId": "",
    }


def producer_host_cli_key(host_key: str) -> str:
    from livedj_personalities import producer_cli_host_key

    return producer_cli_host_key(host_key, aliases=HOST_ALIASES)


def resolve_manual_row(host_key: str, *, now: datetime | None = None) -> dict[str, str]:
    host = normalize_host(host_key)
    ensure_host_active(host)
    return build_manual_row(host, now=now)


def resolve_scheduled_row(now: datetime) -> dict[str, str]:
    current_day, current_time = current_day_time(now)
    row = get_event(now)
    if not row:
        print(f"No scheduled event found for {current_day} {current_time}.")
        raise SystemExit(1)
    ensure_host_active(row["Host"])
    return row


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a LiveDJ spoken break script.")
    parser.add_argument(
        "event_time",
        nargs="?",
        help="Scheduled event datetime (automatic mode only; prefer --event-time)",
    )
    parser.add_argument(
        "--event-time",
        dest="event_time",
        help="Scheduled event datetime for automatic generation (yyyy-MM-dd HH:mm:ss)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Manual generation for the selected host without a live schedule match",
    )
    parser.add_argument(
        "--host",
        dest="host_key",
        help="Host key for manual generation (for example: djmo, bailey, johnnyj)",
    )
    parser.add_argument(
        "--script-only",
        action="store_true",
        help="Generate script text only; do not require an active schedule slot",
    )
    parser.add_argument(
        "--scheduled-host",
        help="Explicit scheduled host key from the saved schedule row",
    )
    parser.add_argument(
        "--event-type",
        help="Explicit EventType column from the saved schedule row",
    )
    parser.add_argument(
        "--mission",
        help="Explicit mission text from the saved schedule row",
    )
    parser.add_argument(
        "--format",
        dest="format_name",
        help="Explicit Format column from the saved schedule row",
    )
    parser.add_argument(
        "--schedule-type",
        help="Explicit Type column from the saved schedule row (for example check_in)",
    )
    parser.add_argument(
        "--schedule-payload-file",
        help="JSON file with host, scheduled_time, event_type, mission, format, schedule_type, next_host",
    )
    parser.add_argument(
        "--next-host",
        help="Explicit NextHost key from the saved schedule row",
    )
    return parser.parse_args()


def read_text(path):
    path = Path(path)
    return path.read_text(encoding="utf-8-sig").strip() if path.exists() else ""


def load_json(path):
    path = Path(path)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def get_event(now):
    return get_event_at(now, SCHEDULE)



def _prompt_catchphrases(host_key: str, catchphrases, *, limit: int = 1) -> list[str]:
    """Shuffle one unused-today catchphrase from this host's personality list."""
    return catchphrase_shift.select_prompt_catchphrases(host_key, catchphrases, limit=limit)


def read_personality(host_key):
    try:
        host = get_host(host_key, aliases=HOST_ALIASES)
    except KeyError:
        return ""

    def list_block(label, values):
        values = [str(v).strip() for v in (values or []) if str(v).strip()]
        if not values:
            return ""
        return f"{label}:\\n" + "\\n".join(f"- {value}" for value in values)

    parts = []

    for label, key in (
        ("Display Name", "display_name"),
        ("Inspired By", "inspired_by"),
        ("Personality", "personality"),
        ("Voice Style", "voice_style"),
        ("Opening Style", "opening_style"),
        ("Closing Style", "closing_style"),
    ):
        value = str(host.get(key, "") or "").strip()
        if value:
            parts.append(f"{label}:\\n{value}")

    prompt_catchphrases = _prompt_catchphrases(host_key, host.get("catchphrases") or [])
    catchphrase_block = list_block(
        "Catchphrases (optional — shuffle one unused line from this host's personality list, or skip; never stack)",
        prompt_catchphrases,
    )
    if catchphrase_block:
        total = len(catchphrase_shift.host_profile_catchphrases(host_key, extra=host.get("catchphrases") or []))
        if total > len(prompt_catchphrases):
            catchphrase_block += (
                f"\\n(Shuffled 1 of {total} personality catchphrases — "
                "use this one if you use a catchphrase, or skip. Add new lines to the profile list anytime.)"
            )
        parts.append(catchphrase_block)

    for label, key in (
        ("Always", "always"),
        ("Never", "never"),
        ("Likes / Interests", "likes"),
        ("Avoid Topics", "avoid_topics"),
    ):
        block = list_block(label, host.get(key, []))
        if block:
            parts.append(block)

    notes = str(host.get("notes", "") or "").strip()
    if notes:
        parts.append(f"Additional Notes:\\n{notes}")

    return "\\n\\n".join(parts)


def read_profile(host):
    try:
        settings = get_host(host, aliases=HOST_ALIASES)
    except KeyError:
        settings = {}

    folder = str(settings.get("profile_folder", host) or host)
    file_profile = read_text(AIRSTAFF / folder / "Profile.md")
    bio = str(settings.get("bio", "") or "").strip()

    return "\n\n".join(
        part for part in (file_profile.strip(), bio) if part
    )



_CONVERSATIONAL_RSS_CATEGORIES = frozenset(
    {"travel", "music", "food", "beer", "sports", "general"}
)
_HEAVY_RSS_CATEGORIES = frozenset({"crime", "traffic", "national_news"})


def _rss_item_rank(item):
    category = str(item.get("category", "") or "").strip().lower()
    if category in _CONVERSATIONAL_RSS_CATEGORIES:
        return 0
    if category in _HEAVY_RSS_CATEGORIES:
        return 2
    return 1


def read_rss_for_host(host_key, limit=1, when=None):
    # Music-first specialty shows — no feed background knowledge.
    if str(host_key or "").strip().lower() in {"moblues", "mo_blues", "casey"}:
        return "", [], []

    if not RSS_HEADLINES.exists():
        return "", [], []

    try:
        data = json.loads(RSS_HEADLINES.read_text(encoding="utf-8-sig"))
    except Exception:
        return "", [], []

    host = str(host_key or "").strip().lower()
    eligible = []

    for item in data.get("items", []):
        allowed = item.get("allowed_hosts") or []
        if allowed and host not in {str(value or "").strip().lower() for value in allowed}:
            continue

        title = str(item.get("title", "") or "").strip()
        if not title:
            continue
        if not rss_rotation.is_airable_feed_item(item):
            continue

        eligible.append(item)

    eligible.sort(key=_rss_item_rank)
    ordered = rss_rotation.prepare_prompt_items(
        host,
        eligible,
        when or station_now(),
        limit=limit,
        rank_fn=_rss_item_rank,
    )
    return _format_rss_blocks(ordered), ordered, eligible


def _format_rss_blocks(items):
    blocks = []
    for item in items:
        title = str(item.get("title", "") or "").strip()
        summary = str(item.get("summary", "") or "").strip()
        category = str(item.get("category", "") or "").strip()
        block = [f"TOPIC: {title}"]
        if summary:
            block.append(
                "DETAIL (use specific facts from this on air — names, places, dates, who/what/where; "
                "do not reduce to a vague tease): "
                + summary
            )
        if category:
            block.append(f"TYPE: {category} (internal — do not say on air)")
        blocks.append("\n".join(block))
    return "\n\n".join(blocks)


def read_upcoming():
    music = load_music_context(KNOWLEDGE)
    supplied = []
    data = load_json(KNOWLEDGE / "UpcomingSongs.json")
    for line in music.get("upcoming_songs") or []:
        text = line.lstrip("- ").strip()
        if " — " in text:
            artist, title = text.split(" — ", 1)
            supplied.append({"artist": artist, "title": title})
    if not supplied:
        supplied = data.get("supplied_to_ai") or data.get("upcoming", [])
    return supplied[:6]


def content_prompt(items):
    if not items:
        return "No managed content items are currently eligible."

    blocks = []
    for item in items:
        blocks.append(
            f"""
CONTENT ID: {item['id']}
TITLE: {item['title']}
CATEGORY: {item['category']}
PRIORITY: {item['priority']}
CONTENT:
{item['content']}
""".strip()
        )
    return "\n\n".join(blocks)


def normalize_preview_text(text):
    value = text or ""
    value = re.sub(r"\bMoe'?s Place Radio\b", "Mo's Place Radio", value, flags=re.I)
    value = re.sub(r"\bMoes Place Radio\b", "Mo's Place Radio", value, flags=re.I)
    value = re.sub(r"\bDJ Moe\b", "DJ Mo", value, flags=re.I)
    return value.strip()


def parse_response(text):
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        data = json.loads(cleaned)
        script = str(data.get("script", "")).strip()
        used_ids = [int(value) for value in data.get("used_content_ids", [])]
        used_announcements = [
            str(value).strip()
            for value in (data.get("used_announcement_ids") or [])
            if str(value).strip()
        ]
        used_fun_day_ids = [
            str(value).strip()
            for value in (data.get("used_fun_day_ids") or [])
            if str(value).strip()
        ]
        used_birthday_ids = [
            str(value).strip()
            for value in (data.get("used_birthday_ids") or [])
            if str(value).strip()
        ]
        if script:
            return normalize_preview_text(script), used_ids, used_announcements, used_fun_day_ids, used_birthday_ids
    except Exception:
        pass

    return normalize_preview_text(text), [], [], [], []


def _infer_daily_content_usage(host: str, now: datetime, script: str) -> tuple[list[str], list[str], list[str]]:
    if not host_can_use_daily_content(host):
        return [], [], []
    birthday_ids = infer_used_entry_ids(
        script,
        fb_birthdays.entries_for_prompt(now, host_key=host),
        title_key="name",
        alt_keys=("note",),
    )
    fun_day_ids = infer_used_entry_ids(
        script,
        fun_days_module.today_entries_for_host(host, now),
        title_key="title",
        alt_keys=("note",),
    )
    announcement_ids = infer_used_entry_ids(
        script,
        community_ann.active_entries(now, host_key=host, enabled_only=True),
        title_key="title",
        alt_keys=("details",),
    )
    return birthday_ids, fun_day_ids, announcement_ids


def _mark_daily_content_usage(
    *,
    host: str,
    used_birthday_ids: list[str],
    used_fun_day_ids: list[str],
    used_announcements: list[str],
) -> None:
    if used_birthday_ids:
        fb_birthdays.mark_used(used_birthday_ids, host_key=host)
    if used_fun_day_ids:
        fun_days_module.mark_used(used_fun_day_ids, host_key=host)
    if used_announcements:
        community_ann.mark_used(used_announcements, host_key=host)


MO_HOST_KEYS = frozenset({"mo", "djmo"})
MUSIC_FIRST_HOSTS = frozenset({"moblues", "mo_blues", "casey"})


def station_anti_repetition_block(host_key: str) -> str:
    """Station-wide variety rules injected into every LiveDJ production prompt."""
    host = str(host_key or "").strip().lower()
    lines = [
        "STATION ANTI-REPETITION (all hosts — hard rules):",
        "- ONE station-name mention per break maximum. Never open with \"You're listening to Moe's Place Radio\" and then say it again.",
        "- ONE scene/personal/topic element per break — do not stack tropes, catchphrases, personal asides, or listener questions.",
        "- Zero or one catchphrase per break; rotate across the shift — never repeat the same catchphrase twice in one shift.",
        "- Talk like one person in the room: one thought leading into the next. Fun-day lines and catchphrases are fine when they grow out of what you just said to the listener.",
        "- One coherent thought per break — setup, one real point, then back to the music. Do not dump a collage of unrelated local images.",
        "- If you mention a local place or market, it MUST be a sourced name + town from this prompt. If none is supplied, talk music and daypart only — never invent geography.",
        "- Make the listener think: I like this person — I'd hang out with them. Fun, warm, one-to-one. Never a generic announcer stacking station bits.",
        "- Never park a slogan as a leftover last sentence after the thought already ended. Weave a catchphrase into the sentence you just said. Do not copy prompt examples word-for-word.",
        "- Show Open: vary structure day to day; one natural welcome naming host + station once, then into the break.",
        "- Mid-shift: no re-introduction, no daypart greeting (good morning/afternoon/evening), no station-ID opener.",
        "- Mention a holiday or observance only when that item is supplied in this prompt. Do not insert a holiday, a catchphrase, or a personal visit that was not supplied.",
    ]
    if host in MO_HOST_KEYS:
        lines.extend(
            [
                "- DJ Mo: ONE tropical scene beat max (commute OR music mood OR one island detail) — never stack Keys, beach, island breeze, and vacation in one break.",
                "- Retired Mo language: letting the music breathe, Keys are calling, rolled in from the beach, feel like a vacation, island breeze in the mix.",
            ]
        )
    if host == "bailey":
        lines.extend(
            [
                "- Bailey: funny, witty DJ talk — never invent a first-person scene. No \"I was at the cafe,\" \"I was at the bar,\" \"I was at the corner,\" and no made-up place she visited.",
                "- Bailey: ONE personal flavor when used — dog OR wine OR Friends OR Jammie Jams OR Law & Order OR books; never stack.",
                "- Bailey: book recommendations are occasional only — most breaks skip books entirely.",
                "- Bailey: at most ONE catchphrase per break — never chain scenic route + kindness + support local + be good to each other.",
                "- Retired: Someone out there needed to hear this today.",
            ]
        )
    if host == "johnnyj":
        lines.append(
            "- Johnny J: at most one verbal tic OR one catchphrase — never stack Come on + Seriously? + You know what? in one break."
        )
    if host == "kathy":
        lines.extend(
            [
                "- Kathy: warm lively Daily Mix energy — do not stack farm-stand promo with travel/island daydream in the same break.",
                "- Kathy: farm-stand mentions only when the farmstand block is supplied — Monday through Saturday, at most twice per shift. Never on Friday nights. Paraphrase the supplied copy; click the link for the Barndoor Bakehouse at mosplaceradio.com.",
                "- Kathy Friday nights (8–10pm): no Bakehouse; fun long-week-done energy — friends, bonfires, good times. Do not invent a specific place you went.",
                "- Kathy: zero or one catchphrase per break — most breaks skip catchphrases; never chain Daily Mix slogans.",
                "- Kathy: never invent unnamed local color — no farmers' market without a sourced name+town, no old barns around town, no kids by the river.",
            ]
        )
    if host == "casey":
        lines.extend(
            [
                "- Casey: music-first 70s flashback — zero or one catchphrase per break; vary story openers; never sound like a countdown host.",
                "- Casey: talk like a warm friend sharing a song story — not a polished announcer doing the same formula every break.",
                "- Casey: ONE handoff closing only — Back to the music. Never add Enjoy the music, Thanks for listening, or a second catalog sign-off.",
            ]
        )
    if host in {"moblues", "mo_blues"}:
        lines.extend(
            [
                "- Lowdown Larry: music-first Sunday blues — shuffle one unused catchphrase from his personality list, or skip; never stack.",
                "- Lowdown Larry: the blues-ain't-about-feeling-bad line is one option among his other catchphrases — do not force it every break.",
            ]
        )
    if host == "dave":
        lines.append(
            "- Dave: personal color optional — karaoke only Thu/Fri and still occasional; most breaks music-first."
        )
    if host == "flea":
        lines.append(
            "- Flea: Boston/local color optional — one detail max when used; most breaks music-first."
        )
    if host == "pete":
        lines.extend(
            [
                "- Pete: yacht/captain tropes optional — zero or one catchphrase per break; most breaks skip captain shtick.",
                "- Pete: sound like the guy next door — not a smooth-jazz announcer every break.",
            ]
        )
    return "\n".join(lines)


def studio_presence_block(host_key: str) -> str:
    """Host-scoped booth-presence guidance. Drink eligibility is shared, not per host."""
    host = str(host_key or "").strip().lower()
    common = """STUDIO PRESENCE (listener should feel someone live in the booth right now):
- Present-tense, in-the-moment. If you mention look-ahead music, put it inside the thought and say it is coming up later in the mix — never "I just flipped through the playlist," and never a liner that only names the artist.
- Never say you flipped through the local news. Never invent a farmers' market, old barns, a river, kids-playing scene, or "around town."
- One idea when chatting: if you mention a local place it must be a REAL sourced name+town from this prompt. If you do not have one, talk music/daypart — do not invent a scene or a nostalgic collage.
- Sentences must connect: setup → one point → back to the music. Not three unrelated postcards. Casual backyard-bar, not a newsreader.
- Natural rhythm variety — not always opener → music → signoff. Sometimes lead with music mood or artist appreciation first.
- Imperfect human flow — contractions, casual pivots, one thought leading to another like real speech.
- Shift awareness — Show Open vs mid-shift feel different; early shift = settling in; mid-shift = keeping company.
- Avoid robot tells — no "As your DJ," no "I'm an AI," no overly polished ad-copy, no identical break structure every time.
- Talk like one real person to one listener — not an announcer, not an ad read, not the same opener/close formula every break.
- One thought leading into the next, like a friend grabbing the mic — Johnny J's conversational shape, in this host's own voice.
- Make the listener want to hang out with this host — fun, warm, human. They should think "I love this person" and look forward to the next break.
- Fun-day lines and catchphrases are welcome when they grow out of what you just said. Never a leftover slogan after the break already ended.
- Paraphrase personality color, catchphrases, and managed content — never read catalog lines or prompt labels on air.
- Finish the thought with a natural exit back to the music. A short break is fine. Do not pad it."""
    if host in {"moblues", "mo_blues"}:
        return (
            common
            + """
- Blues booth: Sunday morning, unhurried — music notes, guitar mood, lived-in soul.
- Optional booth color when natural: one drink from the shared beverage rules — not a coffee-shop run. The eligible list is the same for every DJ.
- Music-first — booth color serves blues talk, not weather, news, sports, or trop-rock vacation vibes."""
        )
    if host == "casey":
        return (
            common
            + """
- 70s flashback booth: vinyl memories, turntable warmth, classic-rock nostalgia — music-first.
- No invented coffee-shop runs, bakery stops, or bar scenes. A booth drink, when one fits, comes from the shared beverage rules — the same list as every other DJ."""
        )
    if host in MO_HOST_KEYS:
        return (
            common
            + """
- Small human booth details sparingly — a booth drink only when the shared beverage rules allow it, adjusting the playlist, mic's on — matched to DJ Mo's trop-rock personality; not every break."""
        )
    return (
        common
        + """
- Small human booth details sparingly — a booth drink only when the shared beverage rules allow it, adjusting the playlist, mic's on, settling into the shift — matched to host personality; not every break.
- Drink eligibility is the same for every DJ. Do not invent a coffee-shop run, bakery visit, or bar scene."""
    )


def knowledge_synthesis_block(host_key: str) -> str:
    host = str(host_key or "").strip().lower()
    if host in {"moblues", "mo_blues"}:
        blues_name = spoken_host_name("moblues", "Lowdown Larry")
        return f"""
KNOWLEDGE SYNTHESIS ({blues_name} — music-first):
- Sound lived-in and soulful — blues feeling, guitar truth, artist appreciation, Sunday morning pace.
- Pull from music history, track facts, look-ahead blues songs, and this host's personality — not news, weather, or sports.
- Stay on one blues thought. Do not staple on a second artist, a drink, or a website.
- Never force unrelated facts together or read lists. Stay conversational, not informational.
- Balance studio presence with supplied music knowledge — live in the booth AND genuinely into the blues."""
    if host == "bailey":
        return """
KNOWLEDGE SYNTHESIS (Bailey):
- Funny, witty midday DJ talk — one listener, a quick observation, then back to the music. Not mean, not sarcastic-cruel, not a memoir.
- Never invent a personal anecdote or a place she visited. No "I was at the cafe," "I was at the bar," "I was at the corner."
- Pull from supplied music, fun days, and this host's personality. Personal color only when that block is supplied.
- New music additions are ONE optional source — mention at most one briefly when natural.
- Never force unrelated facts together or read lists. Stay conversational, not informational.
""".strip()
    if host == "casey":
        return """
KNOWLEDGE SYNTHESIS (DJ Casey — music-first):
- Sound warm and nostalgic — 70s memories, song stories, flashback energy, artist appreciation.
- Pull from verified 70s history, track facts, look-ahead songs, and this host's personality — not news, weather, or sports.
- Stay on one music thought. Do not staple a second fact, a greeting, or a website onto it.
- Never force unrelated facts together or read lists. Stay conversational, not informational.
- Balance studio presence with supplied music knowledge — live in the booth AND genuinely into the music."""
    return """
KNOWLEDGE SYNTHESIS (all hosts):
- Sound like a real person with breadth — bar talk, travel memory, food rec, music-scene color, local knowledge, managed promos, birthdays, fun days, and personal asides when supplied.
- Pull from the best available sources for this break. Do NOT default every break to only "we added X and Y to the mix" library-update filler.
- New music additions are ONE optional source among many — mention at most one addition briefly when natural, and still weave feed color or another supplied fact when available.
- This break has one subject. Do not combine a weekend check-in, a feed aside, a birthday, and a song mention.
- When you use a feed item, dig into TOPIC/DETAIL — at least two concrete facts (name, place, date) on air; never a vague RSS blurb.
- Never force unrelated facts together or read lists. Stay conversational, not informational.
- Balance studio presence with supplied knowledge — the host is live in the booth AND genuinely knowledgeable, not a slogan machine."""


def host_specific_coaching(host_key: str, format_name: str, row: dict | None = None, now=None) -> str:
    if host_key == "casey" or "casey" in format_name.lower():
        return """
This is DJ Casey hosting the 70's Flashback.
Keep it fun, memorable, and music-first — warm classic weekend-radio storytelling.
Tell short song stories that stick. Talk to one listener. Create flashback energy without lecturing.
Never make a listed song sound like it is coming up next — the list is look-ahead into the queue, not the immediate next track.
Never mention weather, forecasts, temperature, news headlines, current events, or sports.
Do not mention countdown rankings, chart positions, or "#1 song" claims unless explicitly supplied.
Never name or imitate any real-world celebrity DJ. Do not imitate DJ Mo or any other host on this station.
""".strip()
    if host_key == "moblues" or "blues" in str(format_name or "").lower():
        blues_name = spoken_host_name("moblues", "Lowdown Larry")
        return f"""
This is {blues_name} on Sunday Morning Blues.
Speak like a man with the blues in his blood — lived-in, soulful, unhurried, music-first.
Talk blues: the feeling, the guitar, the truth in the songs, artists who carry that sound.
Only tease songs from the supplied Blues look-ahead list. If none are listed, talk blues generally — never invent titles.
Never mention weather, forecasts, temperature, news headlines, or sports.
Do not sound like a newsreader, weatherman, or sports desk. Do not imitate Carter Alan or DJ Mo's Trop Rock show.
""".strip()
    if host_key == "mo":
        return """
This is DJ Mo.
Sound like a friendly New England trop-rock neighbor — relaxed, slightly sarcastic, not a generic announcer.
His on-air attitude is laid-back, playful, slightly mischievous, and never in a hurry —
like the hometown guy who just came back from the beach and brought island time home.
PERSONALITY VARIETY (optional — use at most one personal detail in a break):
- Born and raised in New England; loves Florida, the Florida Keys, beaches, and tropical life.
- Has a backyard bar called "Moe's Place." Treat it like a familiar hangout, not an advertisement.
- Hates drama and prefers good music, easy conversation, and people enjoying themselves.
- Knows boats, beaches, fishing, flip-flops, waterfront food, sunsets, travel, and vacation life.
- Use occasional observational/dad-joke-style tropical humor or a light self-tease. He has a story for everything, but never lectures.
- Occasionally invite a curious listener to visit the Mo's Place Radio website to read "Who is Mo?" and his story. Do not force this or repeat it often.
Make listeners feel like they are hanging out with him, not being presented to by a DJ.
Sound live in the booth right now — present-tense, in-the-moment; a Keys vibe or a playlist tweak when it fits; not a trop-rock slogan every break.
When MO TROP-ROCK COLOR is supplied, weave that spirit in Mo's voice — paraphrase only; at most ONE island or scene beat per break (Show Open included).
ONE scene element per break — commute OR music mood OR one tropical detail; never stack Keys, beach, island breeze, and vacation.
Show Open: say host name and station name ONCE in one natural welcome — never "You're listening to Moe's Place Radio" followed by a second station-ID line.
Vacation personality, never barfly: do not sound drunk, intoxicated, or focused on alcohol.
Only state weather or temperatures when fresh verified information is supplied.
For supplied music, a beach-chair/sunset/vacation setup is welcome, but never claim a look-ahead song is up next.
Keep drink talk rare and natural. Follow the shared BEVERAGE RULES. They are the same for every DJ. Personality only changes wording, never which drinks are allowed. Never force a drink into the break, and never explain how a drink is made.
""".strip()
    if host_key == "pete":
        day = ""
        if now is not None:
            try:
                day = now.strftime("%A")
            except Exception:
                day = ""
        if not day and isinstance(row, dict):
            day = str(row.get("day_of_week") or "").strip()
        if day == "Sunday" and str(format_name or "").strip().casefold() == "trop rock":
            return """
SUNDAY TROP ROCK OVERRIDE FOR DJ PETE — applies only to this Sunday show, never Daily Chill/Yacht Rock:
Laid-back, playful, slightly mischievous, and permanently on vacation. Never in a hurry.
Sound like Pete escaped to the islands and never fully came back — warm, relaxed, slightly raspy,
smiling delivery; coastal/Key West attitude without a fake accent.
Use at most one fresh tropical-life angle per break: boats, beaches, fishing, flip-flops,
travel, waterfront food, sunsets, island time, tourists, docks, marinas, or salt air.
Humor is observational and dad-joke-ish, with an occasional listener tease or self-tease.
He knows music and stories but never lectures. Make the listener feel like they are hanging out with him.
Vacation personality, not barfly: never sound drunk, intoxicated, or obsessed with alcohol.
Only state weather or temperatures when fresh verified information is supplied.
When referencing supplied look-ahead music, use a relaxed vacation-style setup but never say it is up next.
Life is short: enjoy the sunset, take the trip, and have another song — optimistic, never cheesy.
""".strip()
    if host_key == "bailey":
        event = ""
        if isinstance(row, dict):
            event = str(row.get("EventType") or row.get("Type") or "").strip().lower()
        is_close = event in {"handoff", "show close", "final half hour", "close"} or (
            "handoff" in event or event.endswith("close")
        )
        if is_close:
            return """
This is Bailey.
Funny, witty, warm, and easygoing — quick wit, never mean or sarcastic-cruel.
Never invent a first-person scene. No "I was at the cafe," "I was at the bar," "I was at the corner," or any made-up place she visited.
Occasional personal color on other breaks: Mo-Ca-Bay, a glass of wine, a book
she has been reading. Do not stack those with a Friends bit.
FRIENDS: only if FRIENDS EPISODE supplies today's last-night episode.
This IS a real shift close / handoff — signature sign-off is allowed:
"Have a great day everyone, remember to woosah and stay away from the filthy chooches. Love you, bye."
Name the schedule's next host before that sign-off when one is provided.
CLOSING FLAVOR (optional, not every close): she may briefly mention heading home
to play with Mo-Ca-Bay and enjoy a glass of wine. Keep it light. Skip it most of the time.
""".strip()
        return """
This is Bailey.
Funny, witty, warm, and easygoing — quick wit, never mean or sarcastic-cruel.
Keep dessert rare.
Talk like a funny friend in the booth — one witty thought, then the music.
Never invent a first-person scene. No "I was at the cafe," "I was at the bar," "I was at the corner," or any made-up place she visited.
Occasional personal color (not every break, and not stacked): Mo-Ca-Bay, a glass
of wine, or a book she has been reading.
FRIENDS: only when FRIENDS EPISODE supplies today's episode. One short thought
about that episode, then ask if anyone else knows it. That question is the Community closer for this break. Do not also ask for a song request.
Do not name Facebook. Never say drop it in the chat. If friends_episode is none,
do not mention Friends at all.
HARD RULE — this is NOT a shift close:
- Do NOT say "Love you, bye."
- Do NOT say woosah / filthy chooches.
- Do NOT hand the mic to Johnny J, Mo, or any other host.
- Do NOT sound like you are signing off or leaving.
Stay with the listeners and continue the show.
""".strip()
    if host_key == "johnnyj":
        return """
This is Johnny J.
Classic-rock afternoon wingman — experienced, dry, witty, not overly enthusiastic. Boston attitude, family-friendly.
At most one verbal tic OR one catchphrase per break — never stack "Come on," "Seriously?," and "You know what?" together.
At most one personal memory per break when it fits naturally — never force Medford/Seabee stories every break.
Show Open: one welcome with host + station once — no double station-ID lines.
""".strip()
    if host_key == "kathy":
        return """
This is DJ Kathy — warm, lively, engaging hometown Saturday radio.
Daily Mix energy: upbeat and genuine, never sleepy or nap-time laid-back.
Casual backyard-bar talk, not nostalgic filler. One coherent thought per break — not a collage of unrelated images.
Do not invent places, towns, barns, rivers, or kids-playing scenes.
If no sourced named place with town is supplied for this break (farmstand block, local talking point, or feed TOPIC/DETAIL), talk music and daypart only.
A farmers' market is allowed ONLY when THIS prompt names that market AND its town. Otherwise skip it — never "the farmers' market's back this weekend."
ONE personal/promo element per break when used — The Barn Door Bakehouse farm stand OR travel daydream, not both stacked.
Farm stand mentions only when THIS prompt's farmstand block supplies them — Monday through Saturday, at most twice per shift. Never on Friday nights. Paraphrase the supplied Bakehouse copy in first person; say click the link for the Barndoor Bakehouse at mosplaceradio.com. Never say check out Barn Door Bakehouse. Never say Facebook. Never list hours.
Friday nights (when FRIDAY NIGHT VIBE is supplied): the long week is done — friends, bonfires, good times. Fun weekend-off energy. Do not mention Bakehouse, sourdough, or folding dough. Do not invent a specific bonfire or that you went there.
Show Open: one welcome naming Kathy + station once — vary the structure day to day.
Never welcome yourself by your own name as the addressee.
""".strip()
    if host_key == "casey":
        return """
This is DJ Casey — warm 70s flashback friend, not a newsreader or countdown host.
Music-first every break. Zero or one catchphrase — most breaks skip them.
Vary story openers — do not use the same "some songs take you somewhere" formula every break.
Talk like one listener is in the room with you — conversational, not polished announcer copy.
End with ONE handoff only: Back to the music. — never chain Enjoy the music or Thanks for listening after it.
""".strip()
    if host_key in {"moblues", "mo_blues"}:
        blues_name = spoken_host_name("moblues", "Lowdown Larry")
        return f"""
This is {blues_name} — Sunday morning blues, unhurried and soulful.
Music-first: blues feeling, guitar truth, artist appreciation — never weather, news, or sports.
Shuffle one unused catchphrase from his personality list, or skip — never stack, never force the same line every break.
Optional booth color: one drink from the shared beverage rules when it fits — the same eligible list as every other DJ. Not a coffee-shop run.
""".strip()
    if host_key == "flea":
        return """
This is Flea — Boston through and through, energetic and mischievous, still music-first.
Classic rock and blues music-first. Optional local color (Fenway, Merrimack Valley, brewery) — one detail max when it fits.
Most breaks skip personal/local asides. Never sound like a generic announcer.
""".strip()
    if host_key == "dave":
        return """
This is Moe's Place Dave — warm local friend, humble and genuine; friendly sports and social conversation, not a sports desk.
Personal stories optional — most breaks music-first. Karaoke mentions only Thursday/Friday and still occasional.
Zero or one catchphrase when used — rotate; never force wedding/Vegas/family bits every break.
""".strip()
    if host_key == "pete":
        return """
This is DJ Pete — guy next door with the perfect soundtrack, relaxed and conversational.
Sound like someone the listener would want to hang out with — easy company, not a yacht announcement.
Yacht/captain tropes are optional flavor — zero or one catchphrase per break; most breaks skip captain shtick.
Family, Chipper the dog, and DMB love are occasional — not every break. Music-first with natural warmth.
One thought into the next. If a catchphrase lands, set it up in the same breath.
""".strip()
    if host_key == "lb":
        return """
This is DJ LB — back-porch country friend, never a big radio voice.
Talk with the listener, not at them: driving home, grilling, sitting by a lake.
Quick dry one-liners are fine; never stack country slogans. Zero or one catchphrase, woven in.
Make them think they'd like to hang out on the porch with this person.
One thought into the next — fun, easy, genuine.
""".strip()
    if host_key in {"tonytone", "tony"}:
        return """
This is DJ Tony Tone — veteran entertainer who includes people in the party.
Smooth, comfortable, no résumé, no corporate announcer. Every listener is a guest of honor.
Make them think they'd love to hang out with this guy.
One thought into the next. Catchphrases only when they continue what he just said.
""".strip()
    return ""


def _pending_station_mentions(host: str, now: datetime) -> tuple[list[dict], list[dict]]:
    """Birthdays and fun days still waiting to air in this half-day.

    Birthdays are station-wide: any DJ, every name, morning and afternoon each
    get their own pass. Fun days follow the same rule except moblues and casey
    never read them. A short birthday list (0-3) shares the break with fun days.
    Four or more birthdays take the break; fun days wait for the next one.
    """
    birthday_entries = fb_birthdays.station_birthdays_today(now)
    pending_names = pending_daily_mentions(
        [str(entry.get("name") or "").strip() for entry in birthday_entries],
        "birthdays",
        now,
    )
    wanted = {name.casefold() for name in pending_names}
    birthdays = [
        entry
        for entry in birthday_entries
        if str(entry.get("name") or "").strip().casefold() in wanted
    ]
    # Month items share this fun-day block. Birthdays still come first.
    fun_days = fun_days_module.pending_fun_days_for_break(
        host,
        now,
        birthday_count=len(birthdays),
    )
    return birthdays, fun_days


def _record_station_mentions(
    now: datetime,
    script: str,
    birthday_entries: list[dict],
    fun_entries: list[dict],
    host: str = "",
) -> None:
    """Record only names and titles that actually appear in the final script."""
    birthday_names = [str(entry.get("name") or "").strip() for entry in birthday_entries]
    aired_birthdays = names_present_in_script(script, birthday_names, "birthdays")
    if aired_birthdays:
        record_daily_mentions(aired_birthdays, "birthdays", now)
    fun_days_module.record_aired_fun_days(script, fun_entries, now, host)


def build_prompt(now, row):
    now = station_now(now)
    host = row["Host"]
    personalities = load_personalities()
    host_data = personalities.get(host)

    if not host_data:
        print("Personality repository:", personality_file_path())
        print("Requested host:", host)
        print("Available hosts:", sorted(personalities.keys()))
        raise KeyError(
            f"Host '{host}' not found. Available hosts: "
            f"{', '.join(sorted(personalities.keys()))}"
        )

    event_type = event_type_for_row(row)
    context = build_break_context(
        now,
        row,
        host_data,
        knowledge_dir=KNOWLEDGE,
        all_hosts=personalities,
    )
    mission_text = str(context.get("mission") or mission_text_for_row(row) or "").strip()
    format_name = context.get("format_name") or row.get("Format", "")
    new_music_additions = select_new_music_additions(
        format_name,
        event_type=event_type,
        now=now,
        limit=2,
    )
    new_music_section = format_new_music_prompt_block(
        new_music_additions,
        format_name=str(row.get("Format") or ""),
    )
    suppress_songs = bool(context.get("suppress_song_teases")) or suppress_song_teases_for_break(row)
    coaching = (
        boundary_event_coaching(event_type) if suppress_songs else event_coaching(event_type)
    )
    host_coaching = host_specific_coaching(host, format_name, row=row, now=now)
    context_block = format_context_block(context)
    time_phrase = context.get("time_phrase") or daypart_phrase(context.get("current_day", ""), row.get("Time") or now)

    upcoming_data = load_json(KNOWLEDGE / "UpcomingSongs.json")
    upcoming = read_upcoming()
    fallback_line = context.get("fallback_line") or upcoming_data.get(
        "fallback_line",
        "More great music is on the way.",
    )
    rss_material, rss_items, rss_eligible_pool = read_rss_for_host(host, when=now)
    check_in_opener = check_in_openers.select_opener(
        host,
        now,
        event_type=event_type,
        mission=mission_text,
    )
    check_in_opener_block = check_in_openers.format_prompt_block(check_in_opener)
    check_in_opener_prefix = f"{check_in_opener_block}\n\n" if check_in_opener_block else ""
    mo_trop_color = mo_trop_rock_color.select_color_line(
        host,
        now,
        event_type=event_type,
        mission=mission_text,
    )
    mo_trop_color_block = mo_trop_rock_color.format_prompt_block(mo_trop_color)
    mo_trop_color_prefix = f"{mo_trop_color_block}\n\n" if mo_trop_color_block else ""
    host_personality_color = personality_color.select_color_line(
        host,
        now,
        event_type=event_type,
        mission=mission_text,
    )
    host_personality_color_block = personality_color.format_prompt_block(host_personality_color)
    host_personality_color_prefix = (
        f"{host_personality_color_block}\n\n" if host_personality_color_block else ""
    )
    mob_blues_color = moblues_blues_color.select_color_line(
        host,
        now,
        event_type=event_type,
        mission=mission_text,
    )
    mob_blues_color_block = moblues_blues_color.format_prompt_block(mob_blues_color)
    mob_blues_color_prefix = f"{mob_blues_color_block}\n\n" if mob_blues_color_block else ""
    queue_text = context.get("queue_text") or ""

    music_history_section = ""
    if wants_music_history(event_type=event_type, mission=mission_text):
        history_facts = load_music_history_facts(when=now)
        music_history_section = f"""
{format_music_history_block(history_facts, when=now)}

MUSIC HISTORY RULES:
- This break is one music moment. Do not add a holiday, awareness month, PSA, or medical reminder.
- Use one fact from the source list. A second fact is allowed only when it connects to the first. Do not read three or four in a row.
- Do not start each sentence with "In [year]". Put the year inside the thought.
- Do not open with a segment title such as "Hey friends, taking a look back on this day in music history." Start with the moment.
- Use only details explicitly listed — do not invent dates, chart positions, album titles, birthdays, or other history.
- If no facts are available, skip This Day in Music History entirely.
- Do not add a question just to invite a reply. If you ask one, ask it once and stop.
- Talk like a DJ who already knows the record, not like a list of dates.
"""

    blues_talk_section = ""
    if _is_larry_host(host):
        try:
            blues_mod = _blues_talk_module()
        except ImportError:
            blues_mod = None
        if blues_mod and blues_mod.wants_blues_talk(
            event_type=event_type, mission=mission_text, host=host
        ):
            blues_talk = blues_mod.load_blues_talk(when=now)
            blues_talk_section = f"""
{blues_mod.format_prompt_block(blues_talk, when=now)}

BLUES TALK RULES:
- This is a conversation with one listener, not a history lesson and not a trivia list.
- Talk about {blues_talk.artist or "today's supplied blues artist"} like you already know them — Sunday coffee, porch, blues in the blood.
- Weave the supplied details into ONE short story: who they are, why they matter, one place or record or connection from the source.
- Do NOT say "fun fact", "did you know", "here's a fact", or number the points.
- Do NOT jump to a second artist. Do NOT invent dates, titles, bands, or history.
- If no facts are supplied, skip the history talk and give a normal Sunday blues check-in.
- Ease back to the music when you are done. Do not tease queue songs as coming up next.
"""

    seventies_section = ""
    seventies_facts: list[str] = []
    if wants_seventies_on_this_day(event_type=event_type, mission=mission_text):
        seventies_facts = load_seventies_facts(when=now)
        seventies_section = f"""
{format_seventies_block(seventies_facts, when=now)}

ON THIS DAY IN THE 70s RULES:
- Open like a warm 1970s radio host looking back on this calendar date in the seventies.
- Use one or two facts from the source list above — prefer two only when both are clear and short.
- Identify the subject explicitly. If discussing a song, track, record, or single, say its verified title and artist; never tease an unnamed historical song.
- If the fact describes a death, name the person and say they died or passed away — do not only use nicknames like "king of rock" without naming them.
- Do not pivot to generic "a song from that era" filler — stay on the historical event from the source list.
- Entertainment only: music, movies, TV. Skip sports, politics, disasters, and dense world-news.
- Make each fact easy to follow in one listen. Do not pile on names, dates, and side details.
- Use only details explicitly listed — do not invent dates, titles, scores, or other history.
- Stay inside 1970-1979. Skip anything outside that decade.
- If no facts are available, do not claim anything happened on this date. Skip the history segment and give a normal nostalgic 1970s music check-in instead.
- Keep it nostalgic and conversational, then return to the music.
"""

    track_facts_section = ""
    track_fact_items = list(context.get("track_facts") or [])
    track_facts_block = format_track_facts_block(track_fact_items)
    if track_facts_block:
        track_facts_section = f"""
{track_facts_block}

{track_facts_rules(mission=mission_text)}
"""

    managed = eligible_items(
        host=host,
        format_name=format_name,
        queue_text=queue_text,
        now=now,
        limit=8,
    )

    rss_header = (
        "RSS FEED FOR THIS BREAK (read TOPIC + DETAIL — use specific facts on air, not a vague tease):"
        if len(rss_items) <= 1
        else "RSS FEED OPTIONS FOR THIS BREAK (pick exactly ONE — read TOPIC + DETAIL, use specifics on air):"
    )
    rss_choice_rule = (
        "- Use the supplied feed topic above when natural conversational color fits this break."
        if len(rss_items) <= 1
        else "- Pick exactly ONE listed topic for this break. Do not combine or mention multiple feed topics."
    )
    if rss_items:
        rss_choice_rule += """
- RSS DEPTH (required when you mention the feed item): dig into THIS break's TOPIC and DETAIL — pull real specifics on air (title, name, place, date, who, what, where). Give listeners something concrete they can act on or picture.
- Include at least TWO concrete facts from THIS DETAIL when available (for example: band + venue; film + theater; restaurant + town; event + date).
- Wrong: vague blurbs with no names ("something local," "a local film," "near downtown").
- Right: use only the real names from THIS TOPIC/DETAIL. If the feed is a band at a club, name that band and club. If it is a harvest trip, name the region and what to do there. Never invent a different scene.
- Never speak prompt labels or placeholders on air: not TOPIC, DETAIL, TYPE, or bracketed coaching blanks.
- Use only facts from THIS break's TOPIC and DETAIL. Do not invent a different local scene than the one supplied.
- Never open a feed aside with "something local" — lead with the name, title, or subject from THIS TOPIC/DETAIL.
- Never invent facts beyond TOPIC/DETAIL. Never read DETAIL verbatim as a news clip — paraphrase naturally in the host's voice."""

    local_detail_notes_block = format_local_detail_notes_block(context.get("local_detail_notes"))
    if local_detail_notes_block:
        rss_choice_rule += f"\n{local_detail_notes_block}"

    upcoming_text = (
        "\n".join(context.get("upcoming_songs") or [])
        or f"(none — use generic line such as \"{fallback_line}\")"
    )
    show_open = suppress_songs
    if show_open:
        if event_type == "Show Open":
            boundary_goal = (
                "Welcome listeners and open the show. Stay on air — do NOT hand off, "
                "do NOT name a next host, and do NOT use a shift-close sign-off."
            )
        elif event_type in {"Handoff", "Show Close", "Final Half Hour"}:
            boundary_goal = (
                "Thank listeners and hand off to the named next host when required. "
                "Shift-close sign-offs are allowed here only."
            )
        else:
            boundary_goal = (
                "Stay with the show and format vibe. Do NOT invent a handoff or "
                "shift-close unless this event is a Handoff / Show Close / Final Half Hour."
            )
        upcoming_music_rules = f"""
UPCOMING MUSIC RULES (INTRO/OUTRO — AUTHORITATIVE):
- This break is an intro or outro near a format change ({event_type or "boundary"}).
- The RadioDJ queue may still be the previous format or already shifting to the next — it is unreliable here.
- Do NOT name any song titles or artists as look-ahead, coming up, in the mix, or later today.
- Do NOT use queue look-ahead at all for intros/outros.
- {boundary_goal}
- A generic line such as "{fallback_line}" is fine if you need a music handoff — without naming tracks.
""".strip()
    else:
        upcoming_music_rules = f"""
UPCOMING MUSIC RULES:
- You may ONLY mention songs listed under Look-ahead songs above.
- Those songs are a look-ahead into the queue while this break is written — NOT the immediate next track after you finish talking.
- Never make a song sound like it is "coming up next," "up next," "next up," "right after this," "about to play," or "here's what's next."
- If you mention a listed song, frame it as later in the mix, still ahead, coming up a little later, or in the rotation.
- Never mention the song that just finished, the song currently on air, or any song from play history.
- Never invent a song that is not in the look-ahead list.
- Do not promise exact timing or order.
- Mention at most two songs when natural.
- If no songs are listed, speak generally about the format and station content — do not invent artists or titles.
- For blues shows: talk blues music, blues artists, and the Sunday blues vibe only. Never fill with Trop Rock, country, or other formats.
- Use a generic line such as "{fallback_line}" and do not invent or guess song titles.
- Never read station tags such as Trop Rock, Reissue, Remastered, Radio Edit, or Album Version.
""".strip()

    rule_text = read_text(RULES / "LiveDJ.md")
    program_text = read_text(PROGRAMS / f"{format_name}.md")
    birthday_block = ""
    birthday_count = 0
    announcement_block = ""
    announcement_count = 0
    fun_day_block = ""
    fun_day_count = 0
    # Station-wide: any DJ, every pending name, once per half-day.
    # The per-DJ first-two-breaks window is no longer the gate.
    pending_birthdays, pending_fun_days = _pending_station_mentions(host, now)
    birthday_block, birthday_count = fb_birthdays.format_station_birthday_block(
        pending_birthdays,
        now,
        host_key=host,
    )
    if host_can_use_daily_content(host):
        announcement_block, announcement_count = community_ann.format_prompt_block(host, now)
    if pending_fun_days:
        fun_day_block, fun_day_count = fun_days_module.format_station_fun_day_block(
            pending_fun_days,
            now,
            host_key=host,
        )
    try:
        question_entry = question_module.pending_question_for_break(
            host,
            now,
            birthday_count=birthday_count,
        )
        question_block = question_module.format_question_block(question_entry)
    except Exception as exc:
        print(f"WARNING: question of the day skipped ({exc})")
        question_entry = None
        question_block = ""
    daily_content_section = ""
    if birthday_count or fun_day_count:
        daily_content_section = f"\n{station_mention_rules(birthday_count, fun_day_count)}\n"
    elif host_can_use_daily_content(host) and announcement_count:
        daily_content_section = f"\n{daily_content_priority_rules()}\n"
    if birthday_count or fun_day_count or announcement_count:
        rss_items = [
            item
            for item in rss_items
            if str(item.get("category") or "").strip().lower() != "sports"
        ]
        rss_material = _format_rss_blocks(rss_items)
        if not rss_items:
            rss_header = "RSS FEED FOR THIS BREAK:"
            rss_choice_rule = (
                "- No extra feed topic on this break — a birthday, fun day, or announcement already carries it. "
                "Do not add sports quotes, Yankees receipts, or other headline asides."
            )
    birthday_section = f"\n{birthday_block}\n" if birthday_block else ""
    announcement_section = f"\n{announcement_block}\n" if announcement_block else ""
    fun_day_section = f"\n{fun_day_block}\n" if fun_day_block else ""
    question_section = f"\n{question_block}\n" if question_block else ""

    personal_topic_block, personal_topic = personality_topics.format_prompt_block(
        host,
        host_data,
        now,
        event_type=event_type,
    )
    personal_topic_section = f"\n{personal_topic_block}\n" if personal_topic_block else ""

    friends_block = ""
    friends_episode = None
    if host == "bailey":
        friends_block, friends_episode = bailey_friends.format_prompt_block(
            now,
            event_type=event_type,
        )
        if personality_topics.topic_mentions_friends(personal_topic):
            personal_topic = None
            personal_topic_block = """
PERSONAL TOPIC (optional — usually skip):
personal_topic: none

PERSONAL TOPIC RULES:
- Do NOT force a personal aside on this break.
- Friends talk is handled only by the FRIENDS EPISODE section — never invent a generic Friends habit.
- NEVER connect personal topics to upcoming songs, artists, or new music.
""".strip()
            personal_topic_section = f"\n{personal_topic_block}\n"
    friends_section = f"\n{friends_block}\n" if friends_block else ""

    books_block = ""
    bailey_book = None
    if host == "bailey" and personality_topics.topic_mentions_books(personal_topic):
        books_block, bailey_book = bailey_books.format_prompt_block(
            now,
            event_type=event_type,
        )
        if bailey_book is None:
            personal_topic = None
            personal_topic_block = """
PERSONAL TOPIC (optional — usually skip):
personal_topic: none

PERSONAL TOPIC RULES:
- Do NOT force a personal aside on this break.
- Most breaks should stay music-first without a life-detail detour.
- NEVER connect personal topics to upcoming songs, artists, or new music.
- Book talk is occasional only — skip it on this break.
""".strip()
            personal_topic_section = f"\n{personal_topic_block}\n"
        else:
            personal_topic = None
            personal_topic_block = """
PERSONAL TOPIC (optional — usually skip):
personal_topic: none

PERSONAL TOPIC RULES:
- Do NOT force a personal aside on this break.
- Most breaks should stay music-first without a life-detail detour.
- NEVER connect personal topics to upcoming songs, artists, or new music.
""".strip()
            personal_topic_section = f"\n{personal_topic_block}\n"
    books_section = f"\n{books_block}\n" if books_block else ""

    dogs_block = ""
    bailey_dogs_pick = None
    if host == "bailey" and personality_topics.topic_mentions_dogs(personal_topic):
        dogs_block, bailey_dogs_pick = bailey_dogs.format_prompt_block(
            now,
            event_type=event_type,
        )
        if bailey_dogs_pick is None:
            personal_topic = None
            personal_topic_block = """
PERSONAL TOPIC (optional — usually skip):
personal_topic: none

PERSONAL TOPIC RULES:
- Do NOT force a personal aside on this break.
- Most breaks should stay music-first without a life-detail detour.
- NEVER connect personal topics to upcoming songs, artists, or new music.
- Dog talk is occasional only — skip it on this break.
""".strip()
            personal_topic_section = f"\n{personal_topic_block}\n"
        else:
            personal_topic = None
            personal_topic_block = """
PERSONAL TOPIC (optional — usually skip):
personal_topic: none

PERSONAL TOPIC RULES:
- Do NOT force a personal aside on this break.
- Most breaks should stay music-first without a life-detail detour.
- NEVER connect personal topics to upcoming songs, artists, or new music.
""".strip()
            personal_topic_section = f"\n{personal_topic_block}\n"
    dogs_section = f"\n{dogs_block}\n" if dogs_block else ""

    farmstand_block = ""
    farmstand_mention = None
    friday_night_block = ""
    if host == "kathy":
        farmstand_block, farmstand_mention = kathy_farmstand.format_prompt_block(
            now,
            event_type=event_type,
            occupied=bool(fun_day_count or birthday_count or announcement_count or question_entry),
        )
        friday_night_block = kathy_farmstand.friday_night_vibe_block(
            now,
            event_type=event_type,
        )
    farmstand_section = f"\n{farmstand_block}\n" if farmstand_block else ""
    friday_night_section = f"\n{friday_night_block}\n" if friday_night_block else ""

    engagement_occupied = bool(
        personal_topic
        or friends_episode
        or bailey_book
        or bailey_dogs_pick
        or farmstand_mention
        or birthday_count
        or fun_day_count
        or announcement_count
        or question_entry
    )
    engagement_block, engagement_pick = listener_engagement.format_prompt_block(
        host,
        now,
        event_type=event_type,
        format_name=format_name,
        occupied=engagement_occupied,
        break_context=mission_text,
    )
    engagement_section = f"\n{engagement_block}\n" if engagement_block else ""

    talking_occupied = bool(engagement_occupied or engagement_pick)
    talking_block, talking_pick = local_talking_points.format_prompt_block(
        host,
        now,
        event_type=event_type,
        occupied=talking_occupied,
        break_context=mission_text,
        format_name=format_name,
    )
    talking_section = f"\n{talking_block}\n" if talking_block else ""

    station_alert = None
    alert_section = ""
    try:
        import station_alerts as station_alerts_module
        from livedj_schedule import load_schedule_file

        alert_when = now if isinstance(now, datetime) else station_now()
        if station_alerts_module.active_alerts(alert_when):
            station_alert = station_alerts_module.this_break_is_alert(
                row,
                alert_when,
                load_schedule_file(schedule_path()),
            )
        if station_alert:
            pending_birthdays = []
            pending_fun_days = []
            birthday_count = 0
            birthday_block = ""
            birthday_section = ""
            announcement_count = 0
            announcement_block = ""
            announcement_section = ""
            fun_day_count = 0
            fun_day_block = ""
            fun_day_section = ""
            question_entry = None
            question_block = ""
            question_section = ""
            daily_content_section = ""
            friends_episode = None
            friends_block = ""
            friends_section = ""
            bailey_book = None
            books_block = ""
            books_section = ""
            bailey_dogs_pick = None
            dogs_block = ""
            dogs_section = ""
            farmstand_mention = None
            farmstand_block = ""
            farmstand_section = ""
            friday_night_block = ""
            friday_night_section = ""
            personal_topic = None
            personal_topic_block = ""
            personal_topic_section = ""
            engagement_pick = None
            engagement_block = ""
            engagement_section = ""
            talking_pick = None
            talking_block = ""
            talking_section = ""
            rss_items = []
            rss_material = "No extra feed topic on this break."
            rss_choice_rule = "- No extra feed topic on this break. Read the station alert only."
            new_music_additions = []
            new_music_section = ""
            check_in_opener = None
            check_in_opener_prefix = ""
            mo_trop_color = None
            mo_trop_color_prefix = ""
            mob_blues_color = None
            mob_blues_color_prefix = ""
            host_personality_color = None
            host_personality_color_prefix = ""
            alert_section = (
                "\n"
                + station_alerts_module.alert_break_rules(station_alert)
                + "\n"
                + station_alerts_module.pause_other_announcements(station_alert)
                + "\n"
            )
    except Exception as exc:
        print(f"WARNING: station alert check skipped ({exc})")
        station_alert = None
        alert_section = ""

    # One subject per break. Music can close the thought. Nothing here rewrites the script.
    def _clear_subjects(*names: str) -> None:
        nonlocal birthday_count, birthday_block, birthday_section, pending_birthdays
        nonlocal announcement_count, announcement_block, announcement_section
        nonlocal fun_day_count, fun_day_block, fun_day_section, pending_fun_days
        nonlocal question_entry, question_block, question_section
        nonlocal friends_episode, friends_block, friends_section
        nonlocal bailey_book, books_block, books_section
        nonlocal bailey_dogs_pick, dogs_block, dogs_section
        nonlocal farmstand_mention, farmstand_block, farmstand_section
        nonlocal friday_night_block, friday_night_section
        nonlocal personal_topic, personal_topic_block, personal_topic_section
        nonlocal engagement_pick, engagement_block, engagement_section
        nonlocal talking_pick, talking_block, talking_section
        nonlocal rss_items, rss_material, rss_choice_rule, rss_header
        nonlocal new_music_section, new_music_additions, daily_content_section
        if "birthday" in names:
            birthday_count = 0
            birthday_block = ""
            birthday_section = ""
            pending_birthdays = []
        if "announcement" in names:
            announcement_count = 0
            announcement_block = ""
            announcement_section = ""
        if "fun_day" in names:
            fun_day_count = 0
            fun_day_block = ""
            fun_day_section = ""
            pending_fun_days = []
        if "question" in names:
            question_entry = None
            question_block = ""
            question_section = ""
        if "friends" in names:
            friends_episode = None
            friends_block = ""
            friends_section = ""
        if "books" in names:
            bailey_book = None
            books_block = ""
            books_section = ""
        if "dogs" in names:
            bailey_dogs_pick = None
            dogs_block = ""
            dogs_section = ""
        if "farmstand" in names:
            farmstand_mention = None
            farmstand_block = ""
            farmstand_section = ""
            friday_night_block = ""
            friday_night_section = ""
        if "personal" in names:
            personal_topic = None
            personal_topic_block = ""
            personal_topic_section = ""
        if "engagement" in names:
            engagement_pick = None
            engagement_block = ""
            engagement_section = ""
        if "talking" in names:
            talking_pick = None
            talking_block = ""
            talking_section = ""
        if "rss" in names:
            rss_items = []
            rss_material = "No second story on this break."
            rss_header = "RSS FEED FOR THIS BREAK:"
            rss_choice_rule = "- Do not add a headline or a second topic."
        if "new_music" in names:
            new_music_additions = []
            new_music_section = ""

    extras = (
        "birthday", "announcement", "fun_day", "question", "friends", "books",
        "dogs", "farmstand", "personal", "engagement", "talking", "rss", "new_music",
    )
    # One subject per break — still use the supplied library item conversationally.
    # Never ban greetings/lead-ins; source notes are facts, not finished scripts.
    one_subject_block = ""
    _pre_subject = break_structure.resolve_subject_kind(
        event_type=str(event_type or ""),
        station_alert=bool(station_alert),
        music_history=bool(music_history_section),
        blues=bool(blues_talk_section),
        seventies=bool(seventies_section),
        birthday=bool(birthday_count),
        question=bool(question_entry),
        fun_day=bool(pending_fun_days),
        announcement=bool(announcement_count),
        friends=bool(friends_episode),
        books=bool(bailey_book),
        dogs=bool(bailey_dogs_pick),
        farmstand=bool(farmstand_mention),
        personal=bool(personal_topic),
        engagement=bool(engagement_pick),
        talking=bool(talking_pick),
        rss=bool(rss_items),
    )
    break_shape = break_structure.break_shape_coaching(
        event_type=str(event_type or ""),
        subject=_pre_subject,
    )
    if station_alert:
        pass
    elif music_history_section or blues_talk_section or seventies_section:
        _clear_subjects(*extras)
        one_subject_block = break_structure.one_subject_coaching(
            _pre_subject,
            event_type=str(event_type or ""),
        )
    elif birthday_count:
        _clear_subjects(*(name for name in extras if name != "birthday"))
        _bday_names = [
            str(entry.get("name") or "").strip()
            for entry in pending_birthdays
            if str(entry.get("name") or "").strip()
        ]
        _bday_label = _bday_names[0] if len(_bday_names) == 1 else ", ".join(_bday_names)
        one_subject_block = break_structure.one_subject_coaching(
            "show_open" if break_structure.is_show_open(str(event_type or "")) else "birthday",
            event_type=str(event_type or ""),
            label=_bday_label,
        )
    elif question_entry:
        _clear_subjects(*(name for name in extras if name != "question"))
        one_subject_block = break_structure.one_subject_coaching(
            "question",
            event_type=str(event_type or ""),
            label=str(question_entry.get("question") or "").strip(),
        )
    elif pending_fun_days:
        chosen_day = next(
            (entry for entry in pending_fun_days if fun_days_module.entry_is_serious(entry)),
            pending_fun_days[0],
        )
        fun_day_block, fun_day_count = fun_days_module.format_station_fun_day_block(
            [chosen_day],
            now,
            host_key=host,
        )
        fun_day_section = f"\n{fun_day_block}\n" if fun_day_block else ""
        pending_fun_days = [chosen_day]
        day_title = str(chosen_day.get("title") or "today's observance").strip()
        _clear_subjects(*(name for name in extras if name != "fun_day"))
        one_subject_block = break_structure.one_subject_coaching(
            "fun_day",
            event_type=str(event_type or ""),
            label=day_title,
            serious=bool(fun_days_module.entry_is_serious(chosen_day)),
        )
    elif announcement_count:
        _clear_subjects(*(name for name in extras if name != "announcement"))
        one_subject_block = break_structure.one_subject_coaching(
            "announcement",
            event_type=str(event_type or ""),
        )
    elif friends_episode:
        _clear_subjects(*(name for name in extras if name != "friends"))
        one_subject_block = break_structure.one_subject_coaching(
            "friends",
            event_type=str(event_type or ""),
            label=str(friends_episode.get("title") or "").strip(),
        )
    elif bailey_book:
        _clear_subjects(*(name for name in extras if name != "books"))
        one_subject_block = break_structure.one_subject_coaching(
            "books",
            event_type=str(event_type or ""),
            label=str(bailey_book.get("title") or bailey_book.get("mention_as") or "").strip(),
        )
    elif bailey_dogs_pick:
        _clear_subjects(*(name for name in extras if name != "dogs"))
        picked = bailey_dogs_pick.get("picked") or {}
        one_subject_block = break_structure.one_subject_coaching(
            "dogs",
            event_type=str(event_type or ""),
            label=str(picked.get("name") or "MoeCarBay").strip(),
        )
    elif farmstand_mention:
        _clear_subjects(*(name for name in extras if name not in {"farmstand"}))
        one_subject_block = break_structure.one_subject_coaching(
            "farmstand",
            event_type=str(event_type or ""),
            label=str(farmstand_mention.get("stand_name") or "Barndoor Bakehouse").strip(),
        )
    elif personal_topic:
        _clear_subjects(*(name for name in extras if name != "personal"))
        one_subject_block = break_structure.one_subject_coaching(
            "personal",
            event_type=str(event_type or ""),
            label=str(personal_topic.get("text") or "").strip()[:80],
        )
    elif engagement_pick:
        _clear_subjects(*(name for name in extras if name != "engagement"))
        one_subject_block = break_structure.one_subject_coaching(
            "engagement",
            event_type=str(event_type or ""),
            label=str(engagement_pick.get("question") or "").strip(),
        )
    elif talking_pick:
        _clear_subjects(*(name for name in extras if name != "talking"))
        one_subject_block = break_structure.one_subject_coaching(
            "talking",
            event_type=str(event_type or ""),
            label=str(talking_pick.get("name") or "").strip(),
            note=str(talking_pick.get("town") or "").strip(),
        )
    elif rss_items:
        rss_items = rss_items[:1]
        rss_material = _format_rss_blocks(rss_items)
        rss_header = "RSS FEED FOR THIS BREAK (read TOPIC + DETAIL — use specific facts on air, not a vague tease):"
        rss_choice_rule = (
            "- Use this one feed story. Pull the real names and details from TOPIC and DETAIL. "
            "Paraphrase naturally — never read DETAIL verbatim. Do not add a second headline."
        )
        _clear_subjects(*(name for name in extras if name != "rss"))
        one_subject_block = break_structure.one_subject_coaching(
            "rss",
            event_type=str(event_type or ""),
            label=str(rss_items[0].get("title") or "").strip(),
        )
    else:
        one_subject_block = break_structure.one_subject_coaching(
            "music",
            event_type=str(event_type or ""),
        )
    if one_subject_block:
        one_subject_block = one_subject_block.rstrip() + break_shape
    if birthday_count or fun_day_count:
        daily_content_section = f"\n{station_mention_rules(birthday_count, fun_day_count)}\n"
    elif host_can_use_daily_content(host) and announcement_count:
        daily_content_section = f"\n{daily_content_priority_rules()}\n"
    else:
        daily_content_section = ""
    if one_subject_block:
        print(f"One subject: {one_subject_block.split('.', 1)[0].replace('ONE SUBJECT: ', '')}")


    subject_label = ""
    subject_note = ""
    if birthday_count:
        names = [
            str(entry.get("name") or "").strip()
            for entry in pending_birthdays
            if str(entry.get("name") or "").strip()
        ]
        subject_label = names[0] if len(names) == 1 else ", ".join(names)
        notes = [
            str(entry.get("note") or "").strip()
            for entry in pending_birthdays
            if str(entry.get("note") or "").strip()
            and str(entry.get("note") or "").strip().lower() != "none"
        ]
        subject_note = " ".join(notes)
    elif question_entry:
        subject_label = str(question_entry.get("question") or "").strip()
        subject_note = str(question_entry.get("note") or subject_label).strip()
    elif fun_day_count and pending_fun_days:
        chosen = pending_fun_days[0] or {}
        subject_label = str(chosen.get("title") or "").strip()
        subject_note = str(chosen.get("note") or "").strip()
    elif friends_episode:
        subject_label = str(friends_episode.get("title") or "").strip()
        subject_note = str(friends_episode.get("summary") or friends_episode.get("note") or "").strip()
    elif bailey_book:
        subject_label = str(bailey_book.get("title") or bailey_book.get("mention_as") or "").strip()
        subject_note = str(bailey_book.get("note") or bailey_book.get("mention_as") or "").strip()
    elif bailey_dogs_pick:
        picked = bailey_dogs_pick.get("picked") or {}
        subject_label = str(picked.get("name") or "MoeCarBay").strip()
        subject_note = str(picked.get("note") or "").strip()
    elif farmstand_mention:
        subject_label = str(farmstand_mention.get("stand_name") or "Barndoor Bakehouse").strip()
    elif personal_topic:
        subject_note = str(personal_topic.get("text") or "").strip()
        subject_label = subject_note[:80]
    elif engagement_pick:
        subject_label = str(engagement_pick.get("question") or "").strip()
        subject_note = subject_label
    elif talking_pick:
        subject_label = str(talking_pick.get("name") or "").strip()
        subject_note = str(talking_pick.get("town") or "").strip()
    elif rss_items:
        subject_label = str(rss_items[0].get("title") or "").strip()
        subject_note = str(
            rss_items[0].get("detail")
            or rss_items[0].get("summary")
            or rss_items[0].get("description")
            or ""
        ).strip()

    subject_kind = break_structure.resolve_subject_kind(
        event_type=str(event_type or ""),
        station_alert=bool(station_alert),
        music_history=bool(music_history_section),
        blues=bool(blues_talk_section),
        seventies=bool(seventies_section),
        birthday=bool(birthday_count),
        question=bool(question_entry),
        fun_day=bool(fun_day_count and pending_fun_days),
        announcement=bool(announcement_count),
        friends=bool(friends_episode),
        books=bool(bailey_book),
        dogs=bool(bailey_dogs_pick),
        farmstand=bool(farmstand_mention),
        personal=bool(personal_topic),
        engagement=bool(engagement_pick),
        talking=bool(talking_pick),
        rss=bool(rss_items),
    )
    break_focus = {
        "subject": subject_kind,
        "label": subject_label,
        "note": subject_note,
        "event_type": str(event_type or ""),
        "content_kind": (
            "birthday"
            if birthday_count
            else "fun_day"
            if fun_day_count and pending_fun_days
            else "question"
            if question_entry
            else subject_kind
        ),
    }
    try:
        import break_continuity

        hints = break_continuity.recent_opening_hints(now)
    except Exception:
        hints = []
    structure_extra = break_structure.structure_coaching_text(
        event_type=str(event_type or ""),
        subject=subject_kind,
        label=subject_label,
        note=subject_note,
        station_alert=bool(station_alert),
    )
    if one_subject_block and structure_extra:
        one_subject_block += " " + structure_extra
    if birthday_count and one_subject_block:
        one_subject_block += break_structure.birthday_structure_coaching(
            subject_label,
            event_type=str(event_type or ""),
        )
    if hints and one_subject_block:
        one_subject_block += (
            " Vary the opener — do not reuse a recent opening that starts like: "
            + "; ".join(hints[:6])
            + "."
        )
    check_in_opener = None
    check_in_opener_prefix = ""
    # Keep host color available on show opens even when daily content is the topic.
    if subject_kind not in {"music", "show_open", "handoff"} and not break_structure.is_show_open(
        str(event_type or "")
    ):
        mo_trop_color = None
        mo_trop_color_prefix = ""
        mob_blues_color = None
        mob_blues_color_prefix = ""
        host_personality_color = None
        host_personality_color_prefix = ""
        managed = []
    print(f"Break subject: {subject_kind}")

    beverage_block = beverage_rules.prompt_block(now, host)

    news_bulletin_rules = ""
    if host == "mo" and now.weekday() < 5:
        minutes_now = now.hour * 60 + now.minute
        if minutes_now < 9 * 60 + 15:
            news_bulletin_rules = """
NEWS BULLETIN RULES (DJ Mo — before 9:15 AM):
- Do NOT say "Morning Refresh" on air — that bulletin airs at 9:15 AM and has not happened yet.
- If you mention news, say "Morning News" or "the news" only — never tease or name a later bulletin.
"""
        elif minutes_now < 9 * 60 + 45:
            news_bulletin_rules = """
NEWS BULLETIN RULES (DJ Mo — Morning Refresh window):
- You may mention "Morning Refresh" only when referring to the 9:15 bulletin.
- Do NOT use "Morning Refresh" when talking about the 7:15 Morning News.
"""

    bailey_dog_rules = ""
    if host == "bailey":
        bailey_dog_rules = """
BAILEY DOG RULES (hard facts when Bailey mentions her dog):
- Bailey's dog now is Mo-Ca-Bay — a male dog. On air say MoeCarBay (one word, like MoeCarBay — not Mo hyphen Ca hyphen Bay). Always he/him/his.
- Never call the current dog Scout. Never she/her or good girl for the dog.
- Past dogs Bailey loved: Moe, Cabo, and Jake — they were great. She may mention one warmly now and then; not every break.
- When she says past dog Moe, mean her old dog — not DJ Mo on the radio.
- At most one dog mention per break (current OR one past dog — never a full roll call).
"""

    prompt = f"""
You are creating one spoken LiveDJ break for Mo's Place Radio.

Write the break in the voice of {context.get("display_name") or host}.
Use the personality profile below — this must sound like THAT host, not a generic announcer and not DJ Mo unless the host is DJ Mo.

{context_block}

EVENT TYPE COACHING ({event_type}):
{coaching}

BREAK GOAL / MISSION (creative guidance for this break — interpret the intent; never read these words verbatim on air):
{mission_text}
{host_coaching}

PROGRAM / FORMAT NOTES ({format_name or "General"}):
{program_text or "No separate program guide supplied for this format."}

{new_music_section}

GENERAL LIVE DJ RULES:
{rule_text}

TIME RULES:
- Prefer not to announce the exact clock time unless the break needs it (a handoff, or a supplied time).
- When any DJ must say a time, write it like 7 PM, 8:30 PM, 10 AM (number plus AM or PM) — that same pattern for every hour. Never o'clock, Oh Clock, 3:00, or 3 house.
- A time-of-day reference is OPTIONAL. Skip it entirely unless the sentence genuinely needs one; do not open or close every break with one.
- When you do use one, it must describe right now (for example: {time_phrase}) and must read naturally in the sentence. Never append it to a line about upcoming songs or handing off the shift.
- Calendar for THIS break (authoritative — do not reuse older break language): {context.get("current_day")}, {context.get("current_month")} {context.get("current_date")}, local time context {context.get("current_local_time")}, weekend position: {context.get("weekend_position_label")}.
- Follow the weekend language guidance in STATION CONTEXT. Never say "this coming weekend" on Saturday or Sunday.
- Only use relative words like tomorrow, yesterday, later this week, or next week when they are accurate for the calendar above.

{upcoming_music_rules}

WEATHER / NEWS RULES:
- Follow Avoid Topics and Never lists from the host profile.
- For Lowdown Larry / Sunday Morning Blues: never mention weather, forecasts, temperature, rain, news headlines, current events, or sports. Blues talk only.
- For DJ Casey / 70's Flashback: never mention weather, forecasts, temperature, rain, news headlines, current events, or sports. Keep it fun, memorable 70s music talk only.
{news_bulletin_rules}
{bailey_dog_rules}

SPORTS SCHEDULE RULES (Patriots, Bruins, Celtics, Red Sox):
- Never invent game schedules, start times, opponents, or tonight/today/this-weekend game claims for those teams unless explicitly supplied in BACKGROUND KNOWLEDGE or MANAGED CONTENT for this break.
- League news is OK when supplied in feed background knowledge (trades, signings, injuries, season storylines) — weave it as fan conversation, never as a sports-desk read.
- Fan loyalty and nostalgia are OK (Brady, Ortiz, Bird, Bergeron, Fenway memories) — but do not attach them to invented "game tonight" or "playing today" claims.
- Sports on air must be something a casual New England listener would get in one sentence (Sox in the playoffs, Bruins open the season) — not a player's quote about phones, receipts, or internet beef.
- If the feed is a press-conference quote, social-media clapback, or an opposing player's "keeping receipts" story, skip it and stay on music.
- Never say "Red Socks." It is Red Sox.
- Drake Maye is not a rookie — never call him a rookie.
- When in doubt, skip the sports angle and stay on music.

HOST NAME RULES:
- Mo's Place Dave is the full on-air persona name — always write Moe's Place Dave with the apostrophe. Never "Moe Place Dave" or "Moes Place Dave".
- On Show Open / shift-start intros: welcome LISTENERS — never address yourself by name as the person being welcomed. Wrong: "Kathy, welcome to Moe's Place Radio." Right: "Hey everyone, Kathy here on Moe's Place Radio." or "Welcome to Moe's Place Radio — I'm Kathy."

{check_in_opener_prefix}{rss_header}
{rss_material or "No background knowledge items are available."}

BACKGROUND KNOWLEDGE RULES:
- Feed items are things the host already knows — like something you'd say to a friend at the bar, on a drive, or between songs. NOT headlines to report.
- When you use a feed item, dig deeper than a one-line blurb — pull specific facts from TOPIC and DETAIL (names, titles, places, dates, who/what/where). Listeners should learn something concrete, not "there's something local worth seeing."
- Do NOT read them as news. Never say "in the news", "headlines", "breaking", "according to", "reports say", or cite source/publication/feed names.
- Never read TOPIC/DETAIL/TYPE labels, list structure, or promotional copy verbatim on air.
- Do NOT mention the station name, show name, or "I heard on the radio" framing to sell the topic — the knowledge should sound like your own.
- Sound knowledgeable because you genuinely know the topic, not because you're performing a branding bit or reciting feed content.
- Use a feed item only when this break's one subject is that feed story. Otherwise leave it out.
{rss_choice_rule}
- Feed topics are NOT queue songs. Never use "coming up," "still ahead," "in the mix," or "up next" for feed knowledge — those phrases are for look-ahead music only.
- Travel / local: personal memory or relaxed recommendation — name the specific place, film, event, or subject from THIS TOPIC/DETAIL (wrong: "a local film screening"; right: the real title and place from DETAIL).
- Music: band, show, venue, or scene color — fan enthusiasm, not chart headlines or industry news reads.
- Food / drink / beer: casual foodie tone — name the spot or dish when supplied; not "there's a place..." with no name when DETAIL gives one.
- Sports: fan conversation only when the story is obvious (Sox in the playoffs, a Boston team playing) — never reciting a Yankees pitcher's quotes, receipts, or phone comments. If a casual listener would say "who?", skip it.
- Promotional or event lines → casual personal recommendation with the real name — not an ad read and not a vague tease.
- LOCAL EVENTS / ARTS: If THIS TOPIC/DETAIL mentions a film, show, festival, or event — say what it is using those supplied names. Do not substitute a different arts story.
- Use at most one feed item in a normal music break.
- Use only details explicitly supplied in the topic or detail lines.
- Do not invent names, quotes, causes, scores, or other facts.
- NEVER invent a farmers' market, old barns, a river, kids-playing-after-school scene, or "around town." If TOPIC/DETAIL or a local talking point names a real market or place WITH town, you may mention THAT one. Otherwise skip and stay on music/daypart.
- Skip serious crime, tragedy, traffic alerts, or heavy national/regional news unless the event type clearly calls for it.

{host_personality_color_prefix}{mob_blues_color_prefix}{mo_trop_color_prefix}{studio_presence_block(host)}

{station_anti_repetition_block(host)}

{knowledge_synthesis_block(host)}
{music_history_section}
{blues_talk_section}
{seventies_section}
{track_facts_section}
MANAGED CONTENT ITEMS:
{content_prompt(managed)}

CONTENT RULES:
- You may use zero, one, or two managed content items when they fit — alongside feed color or personal asides, not instead of sounding knowledgeable.
- Prefer the highest-priority item that fits naturally.
- Never force an item merely because it is available.
- Do not let managed content or new-music mentions become the only talking point when feed background or daily content is also supplied.
- Do not invent facts beyond the supplied content.
- If you use a managed item, include its numeric ID in used_content_ids.
- If you do not actually mention the item, do not include its ID.
{daily_content_section}{birthday_section}{announcement_section}{fun_day_section}{question_section}{personal_topic_section}{friends_section}{books_section}{dogs_section}{farmstand_section}{friday_night_section}{engagement_section}{talking_section}{alert_section}RETURN ONLY VALID JSON:
{{
  "script": "the spoken break only",
  "used_content_ids": [1, 2],
  "used_announcement_ids": ["announcement-id"],
  "used_fun_day_ids": ["fun-day-id"],
  "used_birthday_ids": ["birthday-id"]
}}

{beverage_block}

{one_subject_block}

STRICT SCRIPT RULES:
- Sound exactly like the host described in the personality profile above.
- Talk to one listener like a real person — warm, natural, imperfect human flow; not a corporate announcer or ad read.
- Finish the thought with a natural exit back to the music. A short break is fine when there is nothing more to say. Do not pad. Standard topic/show-open breaks need a conversational lead-in — never start on a raw source fact, and never paste a source note as the whole break.
- Do not sound like a generic announcer or another station host.
- Let the subject and the music belong to the same conversation. Personal color and catchphrases are light seasoning, not a separate bit.
- Vary openers and closes across the shift — do not repeat the same break structure, scene stack, or sign-off formula every time.
- Paraphrase personality color, catchphrases, managed content, and feed facts in the host's own words — never read catalog lines, TOPIC/DETAIL labels, or prompt instructions on air.
- Keep it clean and radio friendly.
- Do not say "as an AI."
- Use the break goal as creative direction only — never read that wording verbatim on air.
- Never mention exact clock times unless explicitly requested in the mission.
- NEVER invent a diner, cafe, bar, farm stand, farmers' market, town, street, library, barn, river, kids-playing scene, owner, menu item, quote, or visit. No "fifth and Main," "around town," "near the river," homemade jam, or flipping through notes into an invented stop.
- If inviting a song request, say click Request a Song at the top of mosplaceradio.com. Never send a request to Community.
- If you say you were somewhere, a light I stopped by {{name}} in {{town}} is allowed only for an active place on the station list. Do not invent a meal, owner, or memory beyond the talking points and the food or drink allowed for this time of day.
- If a local talking point or feed names a real place WITH town, use that name and town only when it already fits this break. You heard or read about it — you were not there. If asking a question, follow it with: Let us know what you think by clicking Community at mosplaceradio.com. We would love to hear from you! Never drop it in the chat, never name Facebook as the destination. Skip it if it would sound random.
- If no sourced named place is in this prompt, talk music and daypart only. One coherent thought: setup → point → back to the music. Casual backyard-bar, not a nostalgic collage and not a newsreader.
- Never invent geography while "sitting here thinking about" old barns, rivers, kids after school, or "around town."


{human_dj_final_checklist()}
""".strip()

    return (
        prompt,
        birthday_count,
        announcement_count,
        fun_day_count,
        new_music_additions,
        friends_episode,
        bailey_book,
        bailey_dogs_pick,
        farmstand_mention,
        personal_topic,
        rss_items,
        rss_eligible_pool,
        check_in_opener,
        mo_trop_color,
        mob_blues_color,
        host_personality_color,
        engagement_pick,
        talking_pick,
        question_entry,
        station_alert,
        break_focus,
    )


def main():
    """
    Manual button:
        selected personality -> generate script
        Producer.py --force --host djmo --script-only

    Automatic event:
        current schedule -> determine personality -> generate script
        Producer.py "2026-07-18 10:20:00"
    """
    init_db()
    args = parse_args()
    now = station_now()

    # OPENAI_API_KEY checked later based on AI provider policy (Local Only may not need it).

    if args.schedule_payload_file:
        payload_path = Path(str(args.schedule_payload_file))
        if not payload_path.is_file():
            print(f"ERROR: schedule payload file not found: {payload_path}")
            raise SystemExit(1)
        try:
            payload = json.loads(payload_path.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            print(f"ERROR: could not read schedule payload: {exc}")
            raise SystemExit(1)
        scheduled_time = str(payload.get("scheduled_time", "")).strip()
        event_type = str(payload.get("event_type", "")).strip()
        mission = str(payload.get("mission", "")).strip()
        format_name = str(payload.get("format", "")).strip()
        schedule_type = str(payload.get("schedule_type", "")).strip()
        host_key = str(payload.get("host", "")).strip()
        next_host = str(payload.get("next_host") or payload.get("NextHost") or "").strip()
        if not scheduled_time or not event_type or not mission or not format_name or not host_key:
            print("ERROR: schedule payload requires host, scheduled_time, event_type, mission, and format.")
            raise SystemExit(1)
        try:
            now = datetime.fromisoformat(scheduled_time.replace(" ", "T", 1))
        except ValueError:
            print(f"Invalid scheduled_time in payload: {scheduled_time}")
            raise SystemExit(1)
        host = normalize_host(host_key)
        print(f"Scheduled script generation for {host} at {now.strftime('%A %I:%M %p').lstrip('0')}.")
        row = build_scheduled_row(
            host,
            when=now,
            event_type=event_type,
            mission=mission,
            format_name=format_name,
            schedule_type=schedule_type,
            next_host=next_host,
        )
        ensure_host_active(host)
    elif args.scheduled_host:
        if not args.event_time:
            print("ERROR: --event-time is required with --scheduled-host.")
            raise SystemExit(1)
        if not args.event_type or not args.mission or not args.format_name:
            print("ERROR: --event-type, --mission, and --format are required with --scheduled-host.")
            raise SystemExit(1)
        try:
            now = datetime.fromisoformat(str(args.event_time).replace(" ", "T", 1))
        except ValueError:
            print(f"Invalid event_time: {args.event_time}")
            raise SystemExit(1)
        host = normalize_host(args.scheduled_host)
        print(f"Scheduled script generation for {host} at {now.strftime('%A %I:%M %p').lstrip('0')}.")
        row = build_scheduled_row(
            host,
            when=now,
            event_type=str(args.event_type).strip(),
            mission=str(args.mission).strip(),
            format_name=str(args.format_name).strip(),
            schedule_type=str(args.schedule_type or "").strip(),
            next_host=str(getattr(args, "next_host", "") or "").strip(),
        )
        ensure_host_active(host)
    elif args.host_key:
        host = normalize_host(args.host_key)
        print(f"Manual script generation for {producer_host_cli_key(args.host_key)} ({host}).")
        row = build_manual_row(host, now=now)
        ensure_host_active(host)
        if args.event_time:
            try:
                now = datetime.fromisoformat(args.event_time)
            except ValueError:
                print(f"Invalid event_time: {args.event_time}")
                raise SystemExit(1)
    else:
        if args.event_time:
            now = datetime.fromisoformat(args.event_time)
        stamp = now.strftime("%A %I:%M %p").lstrip("0")
        print(f"Automatic script generation from schedule at {stamp}.")
        row = resolve_scheduled_row(now)

    now = station_now(now)
    host = row["Host"]
    try:
        from dj_control_bridge import try_produce_approved
        from kathy_library_bridge import LibraryRefusal, try_produce_kathy

        approved_result = try_produce_approved(
            row,
            now,
            BASE / "Output",
            pid=os.getpid(),
        )
    except LibraryRefusal as exc:
        print(f"ERROR: Approved dialogue refused the break — {exc}")
        raise SystemExit(1)
    if approved_result is not None:
        print(approved_result.script)
        print()
        print(f"AIR TIME: {approved_result.air_time_label}")
        print(f"Wrote: {approved_result.script_path}")
        print("Approved Control Center dialogue. No AI rewrite.")
        return
    try:
        library_result = try_produce_kathy(
            row,
            now,
            BASE / "Output",
            pid=os.getpid(),
        )
    except LibraryRefusal as exc:
        print(f"ERROR: Kathy text library refused the break — {exc}")
        raise SystemExit(1)
    if library_result is not None:
        print(library_result.script)
        print()
        print(f"AIR TIME: {library_result.air_time_label}")
        print(f"Wrote: {library_result.script_path}")
        print(f"Text library job: {library_result.job_id}")
        return
    personalities = load_personalities()
    print("Personality repository:", personality_file_path())
    print("Requested host:", host)
    print("Available hosts:", sorted(personalities.keys()))

    break_time = now if isinstance(now, datetime) else station_now()
    try:
        refresh_upcoming_songs(scan_limit=60, break_time=break_time, phase="pre-script-safety")
        print("LiveDJ safety check: refreshed upcoming songs from RadioDJ before script generation.")
    except Exception as exc:
        print(f"WARNING: LiveDJ safety queue refresh failed ({exc}); using last saved UpcomingSongs.json.")

    try:
        rss_out = refresh_rss_headlines()
        print(
            f"LiveDJ safety check: refreshed RSS/weather/news headlines "
            f"({rss_out.get('feeds_ok', 0)} feeds OK, {len(rss_out.get('items') or [])} items)."
        )
    except Exception as exc:
        print(f"WARNING: LiveDJ RSS refresh failed ({exc}); using last saved RSSHeadlines.json.")

    try:
        if wants_music_history(
            event_type=event_type_for_row(row),
            mission=mission_text_for_row(row),
        ):
            history_out = refresh_music_history(when=break_time, force=False)
            print(
                f"LiveDJ safety check: music history facts ready "
                f"({len(history_out.get('facts') or [])} items"
                f"{', ' + history_out['error'] if history_out.get('error') else ''})."
            )
    except Exception as exc:
        print(f"WARNING: LiveDJ music history refresh failed ({exc}); continuing without it.")

    try:
        row_host = str(row.get("Host") or "")
        if _is_larry_host(row_host):
            blues_mod = _blues_talk_module()
            if blues_mod.wants_blues_talk(
                event_type=event_type_for_row(row),
                mission=mission_text_for_row(row),
                host=row_host,
            ):
                blues_out = blues_mod.refresh_blues_talk(when=break_time)
                print(
                    f"LiveDJ safety check: Sunday blues talk ready "
                    f"({blues_out.get('artist') or 'no artist'}, "
                    f"{len(blues_out.get('facts') or [])} talking points"
                    f"{', ' + blues_out['error'] if blues_out.get('error') else ''})."
                )
    except Exception as exc:
        print(f"WARNING: LiveDJ blues talk refresh failed ({exc}); continuing without it.")

    try:
        if wants_seventies_on_this_day(
            event_type=event_type_for_row(row),
            mission=mission_text_for_row(row),
        ):
            seventies_out = refresh_seventies_on_this_day(when=break_time, force=False)
            print(
                f"LiveDJ safety check: 1970s on-this-day facts ready "
                f"({len(seventies_out.get('facts') or [])} items"
                f"{', ' + seventies_out['error'] if seventies_out.get('error') else ''})."
            )
    except Exception as exc:
        print(f"WARNING: LiveDJ 1970s on-this-day refresh failed ({exc}); continuing without it.")

    break_focus = {"subject": "music", "label": "", "note": ""}
    (
        prompt,
        birthday_count,
        announcement_count,
        fun_day_count,
        new_music_additions,
        friends_episode,
        bailey_book,
        bailey_dogs_pick,
        farmstand_mention,
        personal_topic,
        rss_items,
        rss_eligible_pool,
        check_in_opener,
        mo_trop_color,
        mob_blues_color,
        host_personality_color,
        engagement_pick,
        talking_pick,
        question_entry,
        station_alert,
        break_focus,
    ) = build_prompt(now, row)
    break_cta = ""
    if not station_alert:
        break_cta = pick_break_cta(
            bakehouse=bool(farmstand_mention),
            listener_question=bool(question_entry or engagement_pick),
        )
    if break_cta:
        prompt = f"{prompt}\n{cta_prompt_line(break_cta)}"
    print(f"Call to action this break: {break_cta or 'none'}")
    if station_alert:
        print(f"Station alert on this break: {station_alert.get('title')}")
    if question_entry:
        print(f"Question of the day included: {question_entry.get('question')}")
    if host == "bailey":
        if birthday_count:
            print(f"Facebook birthdays included: {birthday_count}")
        else:
            print("Facebook birthdays included: 0")
            print("Birthday segment skipped")
        if friends_episode:
            print(
                "Friends episode included: "
                f"{friends_episode.get('title')} ({friends_episode.get('id')})"
            )
        if bailey_book:
            print(
                "Book recommendation included: "
                f"{bailey_book.get('mention_as')} ({bailey_book.get('id')})"
            )
        if bailey_dogs_pick:
            picked = (bailey_dogs_pick.get("picked") or {})
            print(
                "Bailey dog memory included: "
                f"{picked.get('name')} ({picked.get('id')})"
            )
        elif not friends_episode:
            print("Friends episode included: 0")
    if host == "kathy":
        if farmstand_mention:
            products = farmstand_mention.get("products") or []
            names = ", ".join(str(item.get("name") or "") for item in products[:2])
            print(f"Farm stand included: {farmstand_mention.get('stand_name')} — {names}")
        else:
            print("Farm stand included: none")
    if personal_topic:
        print(f"Personal topic included: {personal_topic.get('text')}")
    else:
        print("Personal topic included: none")
    if engagement_pick:
        print(
            "Listener engagement included: "
            f"{engagement_pick.get('category')} — {engagement_pick.get('question')}"
        )
    else:
        print("Listener engagement included: none")
    if talking_pick:
        print(
            "Local talking point included: "
            f"{talking_pick.get('name')} ({talking_pick.get('town')})"
        )
    else:
        print("Local talking point included: none")
    if check_in_opener:
        print(f"Check-in opener included: {check_in_opener.get('text')}")
    if mo_trop_color:
        print(
            f"Mo trop-rock color included ({mo_trop_color.get('category')}): "
            f"{mo_trop_color.get('text')}"
        )
    else:
        print("Mo trop-rock color included: none")
    if mob_blues_color:
        print(
            f"{spoken_host_name('moblues', 'Lowdown Larry')} color included ({mob_blues_color.get('category')}): "
            f"{mob_blues_color.get('text')}"
        )
    else:
        print(f"{spoken_host_name('moblues', 'Lowdown Larry')} color included: none")
    if host_personality_color:
        print(f"Host personality color included: {host_personality_color.get('text')}")
    else:
        print("Host personality color included: none")
    if rss_items:
        _safe_print(
            f"RSS topics supplied ({len(rss_items)}): {rss_items[0].get('category')} — {rss_items[0].get('title', '')[:80]}"
        )
    if announcement_count:
        print(f"Community announcements included: {announcement_count}")
    else:
        print("Community announcements included: 0")
    if fun_day_count:
        print(f"Fun days included: {fun_day_count}")
    else:
        print("Fun days included: 0")
    model = "gpt-5.5"
    _core = Path(__file__).resolve().parents[2] / "Core"
    if str(_core) not in sys.path:
        sys.path.insert(0, str(_core))
    from openai_credentials import run_producer_responses_create  # noqa: E402

    _next_artist = ""
    _next_song = ""
    try:
        _music = load_music_context(KNOWLEDGE)
        _next = str((_music or {}).get("next_song") or "").strip()
        if _next and _next != "(not available)":
            if " — " in _next:
                _next_artist, _next_song = [p.strip() for p in _next.split(" — ", 1)]
            elif " - " in _next:
                _next_artist, _next_song = [p.strip() for p in _next.split(" - ", 1)]
            else:
                _next_song = _next
    except Exception:
        pass

    # Resolve personality display name for Local AI profiles.
    _personality_name = str(host)
    try:
        _host_data = get_host(host, aliases=HOST_ALIASES) or {}
        _personality_name = str(_host_data.get("display_name") or host)
    except Exception:
        pass

    def _openai_raw(prompt_text: str) -> str:
        response = run_producer_responses_create(
            model=model,
            prompt=prompt_text,
            context=f"Producer.py host={host}",
        )
        return str(getattr(response, "output_text", "") or "")

    # Provider policy: LiveDJ Local-first with OpenAI fallback (configurable).
    _app = Path(__file__).resolve().parents[3] / "Application"
    if str(_app) not in sys.path:
        sys.path.insert(0, str(_app))
    from Services import ai_provider_policy as ai_policy  # noqa: E402

    effective = ai_policy.resolve_effective_policy("livedj")
    print(f"AI provider policy (livedj): {effective}")

    # OPENAI_API_KEY required unless Local Only and Local succeeds without fallback.
    if (
        not station_alert
        and effective != ai_policy.MODE_LOCAL_ONLY
        and not os.environ.get("OPENAI_API_KEY")
    ):
        print("ERROR: OPENAI_API_KEY is not set.")
        raise SystemExit(1)

    _event_now = str(row.get("EventType") or "")
    _next_host = ""
    if _event_now in {"Handoff", "Show Close", "Final Half Hour"}:
        _next_host = str(row.get("NextHost") or "").strip()
    _suppress_song_context = suppress_song_teases_for_break(row)
    _seventies_history_facts: list[str] = []
    if wants_seventies_on_this_day(
        event_type=str(row.get("EventType") or ""),
        mission=str(row.get("Mission") or ""),
    ):
        _seventies_history_facts = load_seventies_facts(when=now)
    _required_fun_day = ""
    _required_fun_day_note = ""
    _fun_day_brief = False
    _required_daily_content_phrases: list[str] = []
    _daily_content_repair_phrase = ""
    _daily_content_repair_kind = ""
    _daily_content_repair_relationship = ""
    _offered_birthdays: list[dict] = []
    _offered_fun_days: list[dict] = []
    try:
        _offered_birthdays, _offered_fun_days = _pending_station_mentions(host, now)
        # build_prompt already dropped a fun day when this break has another subject.
        # Do not require it again, or the repair will paste the note onto that break.
        if not fun_day_count:
            _offered_fun_days = []
        announcement_items = (
            community_ann.prompt_payload(host, now) if host_can_use_daily_content(host) else []
        )
        for item in _offered_birthdays:
            name = str((item or {}).get("name") or "").strip()
            if name:
                _required_daily_content_phrases.append(name)
        for item in announcement_items:
            title = str((item or {}).get("title") or "").strip()
            if title:
                _required_daily_content_phrases.append(title)
        for item in _offered_fun_days:
            title = str((item or {}).get("title") or "").strip()
            if title:
                _required_daily_content_phrases.append(title)
                if not _required_fun_day:
                    _required_fun_day = title
        if _offered_fun_days:
            _daily_content_repair_phrase = str((_offered_fun_days[0] or {}).get("title") or "").strip()
            _daily_content_repair_kind = "fun_day"
            _required_fun_day_note = str((_offered_fun_days[0] or {}).get("note") or "").strip()
            if _required_fun_day_note.lower() == "none":
                _required_fun_day_note = ""
            _fun_day_brief = fun_days_module.entry_span(_offered_fun_days[0]) != "day"
            _suppress_song_context = True
        elif _offered_birthdays:
            _daily_content_repair_phrase = str((_offered_birthdays[0] or {}).get("name") or "").strip()
            _daily_content_repair_kind = "birthday"
            _daily_content_repair_relationship = str(
                (_offered_birthdays[0] or {}).get("relationship") or "friend"
            )
        elif announcement_items:
            _daily_content_repair_phrase = str((announcement_items[0] or {}).get("title") or "").strip()
            _daily_content_repair_kind = "announcement"
    except Exception:
        _required_fun_day = ""
        _required_fun_day_note = ""
        _fun_day_brief = False
        _required_daily_content_phrases = []
        _daily_content_repair_phrase = ""
        _daily_content_repair_kind = ""
        _daily_content_repair_relationship = ""
        _offered_birthdays = []
        _offered_fun_days = []

    from on_air_dj_dialogue import (  # noqa: E402
        PRODUCER_SKIP_WITHOUT_APPROVED_EXIT,
        producer_serves_scheduled_break,
        should_refuse_on_air_model_dialogue,
        skip_without_model_dialogue_message,
    )

    serving_scheduled = producer_serves_scheduled_break(
        host_key=args.host_key,
        schedule_payload_file=args.schedule_payload_file,
        scheduled_host=args.scheduled_host,
        event_time=args.event_time,
    )
    if should_refuse_on_air_model_dialogue(
        host,
        manual_host_key=args.host_key,
        station_alert=station_alert,
        serving_scheduled_break=serving_scheduled,
    ):
        print(skip_without_model_dialogue_message(host))
        raise SystemExit(PRODUCER_SKIP_WITHOUT_APPROVED_EXIT)

    if station_alert:
        _required_fun_day = ""
        _required_fun_day_note = ""
        _fun_day_brief = False
        _required_daily_content_phrases = []
        _daily_content_repair_phrase = ""
        _daily_content_repair_kind = ""
        _offered_birthdays = []
        _offered_fun_days = []
        alert_script = str(station_alert.get("script") or "").strip()
        print("Station alert break: alert sound and the alert message only.")
        outcome = ai_policy.ProviderOutcome(
            ok=bool(alert_script),
            script=alert_script,
            provider="station_alert",
            model="",
            prompt="",
            generation_time=0.0,
            status_message="Station alert: operator text only.",
            error="" if alert_script else "Station alert had no words to read.",
        )
    else:
        outcome = ai_policy.generate_with_policy(
            generator="livedj",
            prompt=prompt,
            personality=_personality_name,
            task="Write one spoken radio break for Mo's Place Radio.",
            context={
                "format": str(row.get("Format") or ""),
                "current_day": now.strftime("%A"),
                "current_date": now.strftime("%d").lstrip("0"),
                "current_month": now.strftime("%B"),
                "current_local_time": format_clock(now),
                "time_of_day": format_clock(now),
                # A new-music break uses the additions as its music topic. Do not also
                # hard-require a queue artist, which would overcrowd a short break.
                "upcoming_artist": "" if (new_music_additions or _suppress_song_context or str((break_focus or {}).get("subject") or "") not in {"music", "show_open", "handoff", ""}) else _next_artist,
                "upcoming_song": "" if (new_music_additions or _suppress_song_context or str((break_focus or {}).get("subject") or "") not in {"music", "show_open", "handoff", ""}) else _next_song,
                "new_music_additions": [] if _suppress_song_context else new_music_additions,
                "suppress_song_teases": _suppress_song_context,
                "openai_model": model,
                "scheduled_time": now.isoformat(timespec="seconds"),
                "event_type": str(row.get("EventType") or ""),
                "mission": str(row.get("Mission") or ""),
                "next_host": _next_host,
                "required_fun_day": _required_fun_day,
                "required_fun_day_note": _required_fun_day_note,
                "fun_day_brief": _fun_day_brief,
                "required_daily_content_phrases": _required_daily_content_phrases,
                "required_question": str((question_entry or {}).get("question") or "").strip(),
                "daily_content_repair_phrase": _daily_content_repair_phrase,
                "daily_content_repair_kind": _daily_content_repair_kind,
                "daily_content_repair_relationship": _daily_content_repair_relationship,
                "seventies_history_facts": _seventies_history_facts,
                # LiveDJ prompts are large; 2048 ctx truncates music/rules and tanks quality.
                "num_ctx": 8192,
                "num_predict": 260,
            },
            openai_generate=_openai_raw,
        )
    ai_policy.record_provider_outcome(outcome, generator="livedj", host=str(row.get("Host") or host))
    try:
        print(outcome.status_message)
    except UnicodeEncodeError:
        print(outcome.status_message.encode("ascii", "replace").decode("ascii"))
    if not outcome.ok or not str(outcome.script or "").strip():
        err = outcome.error or outcome.status_message
        try:
            print(f"ERROR: Script generation failed — {err}")
        except UnicodeEncodeError:
            print("ERROR: Script generation failed — " + str(err).encode("ascii", "replace").decode("ascii"))
        raise SystemExit(1)

    if station_alert:
        script = str(station_alert.get("script") or "").strip()
        used_ids = []
        used_announcements = []
        used_fun_day_ids = []
        used_birthday_ids = []
    else:
        script, used_ids, used_announcements, used_fun_day_ids, used_birthday_ids = parse_response(outcome.script)
        script = repair_human_dj_script(
            script,
            prompt,
            event_type=str(row.get("EventType") or ""),
            preferred_cta=break_cta,
        )
        try:
            import break_continuity

            script = break_continuity.focus_spoken_break(
                script,
                subject=str((break_focus or {}).get("subject") or ""),
                label=str((break_focus or {}).get("label") or ""),
                note=str((break_focus or {}).get("note") or ""),
                allow_cta=break_cta,
                recent_opening_fingerprints=break_continuity.recent_opening_hints(now),
                event_type=str(row.get("EventType") or (break_focus or {}).get("event_type") or ""),
                content_kind=str((break_focus or {}).get("content_kind") or ""),
            )
            break_continuity.record_break(
                host,
                now,
                script,
                event_type=str(row.get("EventType") or ""),
            )
        except Exception as exc:
            print(f"WARNING: break focus was not applied ({exc})")
        _structure = break_structure.validate_break_structure(
            script,
            subject=str((break_focus or {}).get("subject") or ""),
            event_type=str(row.get("EventType") or ""),
            label=str((break_focus or {}).get("label") or ""),
            note=str((break_focus or {}).get("note") or ""),
            host=str(row.get("Host") or host or ""),
            station_alert=False,
            paraphrase_expected=True,
        )
        if not _structure.ok and _structure.required:
            print(break_structure.format_structure_failure(_structure))
            print(
                "ERROR: Script failed conversational structure check — "
                + ", ".join(_structure.reasons)
            )
            raise SystemExit(1)
    try:
        import station_alerts as station_alerts_module

        script = station_alerts_module.ensure_script(script, station_alert)
    except Exception as exc:
        print(f"WARNING: station alert script was not applied ({exc})")
    if station_alert:
        used_birthday_ids = []
        used_fun_day_ids = []
        used_announcements = []
        question_entry = None
        _offered_birthdays = []
        _offered_fun_days = []
    elif outcome.provider == "local":
        used_ids = []
        inferred_birthdays, inferred_fun_days, inferred_announcements = _infer_daily_content_usage(
            host,
            now,
            script,
        )
        if not used_announcements:
            used_announcements = inferred_announcements
        if not used_fun_day_ids:
            used_fun_day_ids = inferred_fun_days
        if not used_birthday_ids:
            used_birthday_ids = inferred_birthdays
    if not station_alert:
        script = beverage_rules.enforce_script(
            script,
            now,
            host=str(row.get("Host") or host),
        )
    if not str(script or "").strip() or str(script).lstrip().startswith("{"):
        print("ERROR: Script generation failed — Local/OpenAI returned unusable script text.")
        raise SystemExit(1)
    if used_ids and not station_alert:
        mark_content_used(used_ids)
    if not station_alert:
        _mark_daily_content_usage(
            host=host,
            used_birthday_ids=used_birthday_ids,
            used_fun_day_ids=used_fun_day_ids,
            used_announcements=used_announcements,
        )
        _record_station_mentions(now, script, _offered_birthdays, _offered_fun_days, host=host)
        try:
            if question_entry and question_module.record_aired_question(script, question_entry, now, host):
                print("Question of the day aired on this break.")
        except Exception as exc:
            print(f"WARNING: question of the day was not marked aired ({exc})")
        record_daily_content_break(host, now, aired=bool(used_birthday_ids or used_fun_day_ids))
    if friends_episode and host == "bailey":
        bailey_friends.mark_used(str(friends_episode.get("id") or ""), now)
    if bailey_book and host == "bailey":
        bailey_books.mark_used(str(bailey_book.get("id") or ""), now)
    if bailey_dogs_pick and host == "bailey":
        picked = bailey_dogs_pick.get("picked") or {}
        bailey_dogs.mark_used(str(picked.get("id") or ""), now)
    if farmstand_mention and host == "kathy":
        kathy_farmstand.mark_used(farmstand_mention.get("product_ids"), now)
    if personal_topic:
        personality_topics.mark_used(host, personal_topic, now)
    if engagement_pick:
        listener_engagement.mark_used(host, engagement_pick, now)
    if talking_pick:
        local_talking_points.mark_used(host, talking_pick, now)

    used_rss_item = rss_rotation.resolve_used_item(
        script,
        rss_items,
        eligible_items=rss_eligible_pool,
    )
    if used_rss_item:
        rss_rotation.mark_used(host, used_rss_item, now)
    if check_in_opener:
        check_in_openers.mark_used(host, check_in_opener, now)
    if mo_trop_color:
        mo_trop_rock_color.mark_used(host, mo_trop_color, now)
    if mob_blues_color:
        moblues_blues_color.mark_used(host, mob_blues_color, now)
    if host_personality_color:
        personality_color.mark_used(host, host_personality_color, now)
    _host_profile = load_personalities().get(host) or {}
    _catchphrases = list(_host_profile.get("catchphrases") or [])
    if _catchphrases:
        catchphrase_shift.mark_used(host, script, _catchphrases, now)

    output_dir = BASE / "Output"
    output_dir.mkdir(parents=True, exist_ok=True)

    text_path = output_dir / f"{row['Host']}_latest.txt"
    prompt_path = output_dir / f"{row['Host']}_latest_prompt.txt"
    used_path = output_dir / f"{row['Host']}_latest_used_content.json"
    provider_path = output_dir / f"{row['Host']}_latest_provider.json"

    text_path.write_text(script, encoding="utf-8")
    prompt_path.write_text(prompt, encoding="utf-8")
    generated_at = datetime.now().isoformat(timespec="seconds")
    announced_new_music_ids = []
    # Manual/script-only tests may preview the talking point but must not consume it.
    if not args.host_key:
        announced_new_music_ids = mark_announced_if_mentioned(
            str(row.get("Format") or ""),
            new_music_additions,
            script,
            air_time=now,
        )
    used_path.write_text(
        json.dumps(
            {
                "generated_at": generated_at,
                "air_time": now.strftime("%A %Y-%m-%d %I:%M %p"),
                "host": row["Host"],
                "used_content_ids": used_ids,
                "used_announcement_ids": used_announcements,
                "used_fun_day_ids": used_fun_day_ids,
                "used_birthday_ids": used_birthday_ids,
                "new_music_candidate_ids": [
                    int(item.get("id") or 0) for item in new_music_additions
                ],
                "new_music_announced_ids": announced_new_music_ids,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    provider_path.write_text(
        json.dumps(
            {
                "generated_at": generated_at,
                "host": row["Host"],
                "provider": outcome.provider,
                "model": outcome.model,
                "fallback": outcome.fallback,
                "fallback_reason": outcome.fallback_reason,
                "status_message": outcome.status_message,
                "generation_time": outcome.generation_time,
                "policy": effective,
                "new_music_candidate_ids": [
                    int(item.get("id") or 0) for item in new_music_additions
                ],
                "new_music_announced_ids": announced_new_music_ids,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(script)
    print()
    print(f"AIR TIME: {now.strftime('%A %Y-%m-%d %I:%M %p')}")
    print(f"generated_at: {generated_at}")
    print(f"Managed content used: {used_ids or 'None'}")
    if new_music_additions:
        print(
            "New music additions mentioned: "
            f"{announced_new_music_ids or 'None (kept pending)'}"
        )
    print(f"Wrote: {text_path}")
    print(f"Provider detail: {provider_path}")

    # Shadow Mode only when production used OpenAI (compare Local silently).
    if outcome.provider == "openai" and not outcome.fallback:
        try:
            from Services.shadow_hooks import enqueue_livedj_shadow  # noqa: E402

            enqueue_livedj_shadow(
                host=str(row.get("Host") or host),
                script=script,
                prompt=prompt,
                model=outcome.model or model,
                generation_time=outcome.generation_time,
                event_type=str(row.get("EventType") or ""),
                mission=str(row.get("Mission") or ""),
                format_name=str(row.get("Format") or ""),
                air_time=now.strftime("%I:%M %p").lstrip("0"),
                next_artist=_next_artist,
                next_song=_next_song,
            )
            print("Shadow Mode: Local AI comparison queued (Logs\\LocalAI\\Shadow).")
        except Exception as _shadow_exc:
            print(f"Shadow Mode skipped: {_shadow_exc}")


if __name__ == "__main__":
    main()

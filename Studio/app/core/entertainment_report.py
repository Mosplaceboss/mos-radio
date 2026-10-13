"""Morning entertainment report for Michael G.

Runs after Dave's sports in the morning newscast. Michael G reads up to four
stories from Deadline, TMZ, and the Variety film feed, then hands to DJ Mo.
DJ Mo thanks Michael G by name.

Story selection is fail-soft: a down feed is skipped, graphic crime and sexual
items are dropped, and fewer than four usable stories are read as-is. Nothing
here invents gossip.

The prompt block matches the sports-desk style: rules plus supplied facts for
Local AI, with a speakable fallback script when generation is not available.

Print a fail-soft morning handoff (network optional) with:

    python Studio/app/core/entertainment_report.py
"""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

MICHAEL_G_NAME = "Michael G"
MICHAEL_G_NEWS_ID = "michael_g"
MICHAEL_G_PERSONALITY_ID = "michael-g"
MICHAEL_G_VOICE_RECORD_ID = "vb-michael-g"
MICHAEL_G_VOICEBOX_ID = "41e35c72-041b-42ae-8cc4-a8e68ae11b6f"
MICHAEL_G_VOICEBOX_PROFILE = (
    r"\\MOSPLACERADIO\Users\mospl\AppData\Roaming\sh.voicebox.app\profiles"
    r"\41e35c72-041b-42ae-8cc4-a8e68ae11b6f"
)

ENTERTAINMENT_STORY_COUNT = 4

ENTERTAINMENT_SOURCES: tuple[dict[str, str], ...] = (
    {
        "id": "deadline",
        "name": "Deadline",
        "kind": "general",
        "url": "https://deadline.com/feed/atom/",
    },
    {
        "id": "tmz",
        "name": "TMZ",
        "kind": "general",
        "url": "https://www.tmz.com/rss.xml",
    },
    {
        "id": "variety_film",
        "name": "Variety Film",
        "kind": "film",
        "url": "https://variety.com/v/film/feed/",
    },
)

DAVE_SPORTS_CLOSE = "That's sports for this morning. Michael G has the entertainment report."
MICHAEL_OPEN = "Thanks, Dave."
MICHAEL_HANDOFF = "DJ Mo, back to you."
MICHAEL_EMPTY = "That's all for entertainment this morning."
MO_THANKS = "Thanks, Michael G."

DEFAULT_ENTERTAINMENT_REPORT_RULES = (
    "Michael G reads the entertainment report after Dave's sports. "
    "Use only the supplied stories. Read four when four usable stories are supplied; "
    "if fewer are supplied, read only those and do not invent gossip, quotes, or extra stories. "
    "Deadline and TMZ items are general entertainment. Variety film items are new movies and reviews. "
    "Skip graphic crime, sexual content, and anything that does not fit a morning music-radio show. "
    "Do not name the outlets on the air. "
    "Thank Dave, then read the stories in short conversational beats, then hand the show to DJ Mo. "
    "DJ Mo's next line thanks Michael G by name."
)

ENTERTAINMENT_PERSONALITY_CLAUSE = (
    "After Dave finishes sports, he hands to Michael G for the entertainment report "
    "instead of going straight to DJ Mo. Michael G reads up to four supplied entertainment "
    "stories, then hands to DJ Mo. DJ Mo thanks Michael G by name."
)

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_OUTLET_PREFIX_RE = re.compile(r"(?i)^(deadline|tmz|variety(?:\s+film)?)\s*[:|\-—–]\s*")
_KILLED_IT_RE = re.compile(r"(?i)\bkilled it\b")
_UNSAFE_RE = re.compile(
    r"(?i)\b("
    r"murder(?:ed|s|ing)?|homicide|manslaughter|"
    r"kill(?:ed|s|ing)?|shot dead|shooting|gunman|gunshot|"
    r"stab(?:bed|bing|s)?|"
    r"rape[sd]?|rapist|sexual(?:ly)?(?:\s+assault)?|"
    r"molest(?:ed|ation|s)?|child porn|underage|"
    r"sex(?:\s+tape)?|sext(?:ing|s)?|sexy|nudes?|naked|porn(?:ography|ographic)?|onlyfans|"
    r"xxx|nsfw|orgy|prostitut\w*|escort|"
    r"assault(?:ed|s|ing)?|"
    r"suicide|overdose|"
    r"dismember\w*|decapitat\w*|gore|gruesome|"
    r"terror(?:ist|ism)?|bombing|hostage|massacre|"
    r"arrested for|charged with|indicted|mugshot"
    r")\b"
)
_STRAIGHT_TO_MO_RE = re.compile(
    r"(?i)("
    r"back to you,?\s+(?:dj\s+)?mo\b"
    r"|dj\s+mo,?\s+back to you"
    r"|over to\s+(?:dj\s+)?mo\b"
    r"|now back to the music"
    r"|back to the music"
    r"|for mo's place radio, i'm"
    r")"
)
_USER_AGENT = "MoPlaceStudio/2.0 (entertainment report)"


@dataclass(frozen=True)
class EntertainmentStory:
    title: str
    summary: str
    url: str
    source_id: str
    source_name: str
    kind: str
    published: datetime | None = None


def entertainment_feed_urls() -> list[str]:
    return [source["url"] for source in ENTERTAINMENT_SOURCES]


def _source_for_url(url: str) -> dict[str, str] | None:
    key = url.strip().lower().rstrip("/")
    for source in ENTERTAINMENT_SOURCES:
        if source["url"].strip().lower().rstrip("/") == key:
            return source
    return None


def _clean_text(value: str) -> str:
    text = html.unescape(str(value or ""))
    text = _TAG_RE.sub(" ", text)
    text = text.replace("\xa0", " ")
    return _WS_RE.sub(" ", text).strip()


def _strip_outlet_prefix(value: str) -> str:
    return _OUTLET_PREFIX_RE.sub("", _clean_text(value)).strip()


def _parse_datetime(raw: str) -> datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    parsed: datetime | None = None
    try:
        parsed = parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError, OverflowError):
        parsed = None
    if parsed is None:
        iso = text.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(iso)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _element_text(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return "".join(node.itertext())


def _child_text(item: ET.Element, names: tuple[str, ...]) -> str:
    wanted = {name.lower() for name in names}
    for child in list(item):
        if _local_name(child.tag) in wanted:
            text = _element_text(child).strip()
            if text:
                return text
    return ""


def _child_link(item: ET.Element) -> str:
    for child in list(item):
        if _local_name(child.tag) != "link":
            continue
        href = (child.attrib.get("href") or _element_text(child) or "").strip()
        if href:
            return href
    return ""


def is_morning_safe(title: str, summary: str = "") -> bool:
    """True when a story fits a morning music-radio entertainment report."""
    title_text = _clean_text(title)
    if len(title_text) < 8:
        return False
    blob = f"{title_text} {_clean_text(summary)}"
    blob = _KILLED_IT_RE.sub(" ", blob)
    return _UNSAFE_RE.search(blob) is None


def _dedupe_key(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def parse_feed_xml(xml_text: str, source: dict[str, str]) -> list[EntertainmentStory]:
    """Parse one RSS or Atom document. Bad XML returns an empty list."""
    text = str(xml_text or "").strip()
    if not text:
        return []
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []

    root_name = _local_name(root.tag)
    items: list[ET.Element] = []
    if root_name == "rss" or root.find("channel") is not None:
        channel = root.find("channel")
        parent = channel if channel is not None else root
        items = [node for node in list(parent) if _local_name(node.tag) == "item"]
    else:
        items = [node for node in root.iter() if _local_name(node.tag) == "entry"]

    stories: list[EntertainmentStory] = []
    for item in items:
        title = _strip_outlet_prefix(_child_text(item, ("title",)))
        summary = _strip_outlet_prefix(
            _child_text(item, ("description", "summary", "content", "subtitle"))
        )
        if not is_morning_safe(title, summary):
            continue
        published = _parse_datetime(
            _child_text(item, ("pubDate", "published", "updated", "date"))
        )
        if len(summary) > 280:
            summary = summary[:277].rstrip() + "..."
        stories.append(
            EntertainmentStory(
                title=title,
                summary=summary,
                url=_child_link(item),
                source_id=source.get("id", ""),
                source_name=source.get("name", ""),
                kind=source.get("kind", "general"),
                published=published,
            )
        )
    return stories


def _freshness_key(story: EntertainmentStory) -> tuple[int, float, str]:
    if story.published is None:
        return (1, 0.0, story.title.lower())
    return (0, -story.published.timestamp(), story.title.lower())


def select_entertainment_stories(
    stories: list[EntertainmentStory],
    *,
    limit: int = ENTERTAINMENT_STORY_COUNT,
) -> list[EntertainmentStory]:
    """Pick up to `limit` fresh, morning-safe stories.

    Variety film items cover new movies and reviews. When the freshest items
    would otherwise leave film out, the newest film story replaces the oldest
    pick so a movie or review still airs.
    """
    usable: list[EntertainmentStory] = []
    seen: set[str] = set()
    for story in stories:
        if not is_morning_safe(story.title, story.summary):
            continue
        key = _dedupe_key(story.title)
        if not key or key in seen:
            continue
        seen.add(key)
        usable.append(story)

    usable.sort(key=_freshness_key)
    if limit < 1 or not usable:
        return []
    if len(usable) <= limit:
        return usable

    chosen = usable[:limit]
    if any(story.kind == "film" for story in chosen):
        return chosen
    film = next((story for story in usable if story.kind == "film"), None)
    if film is None:
        return chosen
    chosen = chosen[:-1] + [film]
    chosen.sort(key=_freshness_key)
    return chosen


def collect_entertainment_stories(
    xml_by_url: dict[str, str | BaseException] | None = None,
    *,
    fetch: bool = False,
    timeout: float = 12.0,
) -> list[EntertainmentStory]:
    """Gather stories from the three entertainment feeds.

    Pass `xml_by_url` for offline fixtures. Set `fetch` to download live feeds.
    Each feed fails on its own; the others are still used.
    """
    payloads: dict[str, str | BaseException] = {}
    if xml_by_url is not None:
        payloads = dict(xml_by_url)
    elif fetch:
        for source in ENTERTAINMENT_SOURCES:
            url = source["url"]
            try:
                payloads[url] = _fetch_feed_xml(url, timeout=timeout)
            except (URLError, OSError, TimeoutError, ValueError) as exc:
                payloads[url] = exc

    stories: list[EntertainmentStory] = []
    for source in ENTERTAINMENT_SOURCES:
        payload = payloads.get(source["url"])
        if payload is None or isinstance(payload, BaseException):
            continue
        stories.extend(parse_feed_xml(str(payload), source))
    return select_entertainment_stories(stories)


def _fetch_feed_xml(url: str, *, timeout: float) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": _USER_AGENT,
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def _first_sentence(text: str, limit: int = 180) -> str:
    cleaned = _clean_text(text)
    if not cleaned:
        return ""
    match = re.search(r"^.+?[.!](?:\s|$)", cleaned)
    sentence = match.group(0).strip() if match else cleaned
    if len(sentence) > limit:
        return sentence[: limit - 3].rstrip() + "..."
    return sentence


_OUTLET_WORD_RE = re.compile(r"(?i)\b(deadline|tmz|variety)(?:\s+film)?\b")
_ATTRIBUTION_RE = re.compile(
    r"(?i)\b(?:according to|via|reports from|reported by)\s+"
    r"(deadline|tmz|variety)(?:\s+film)?\b[:,]?\s*"
)
_OUTLET_SAYS_RE = re.compile(
    r"(?i)\b(deadline|tmz|variety)(?:\s+film)?\s+"
    r"(?:reports|says|writes|reported|is reporting)\b[:,]?\s*"
)


def _summary_for_air(summary: str) -> str:
    """Use a short factual blurb. Drop it when it is outlet attribution."""
    text = _strip_outlet_prefix(summary)
    text = _ATTRIBUTION_RE.sub("", text)
    text = _OUTLET_SAYS_RE.sub("", text)
    text = _first_sentence(text)
    if not text or _OUTLET_WORD_RE.search(text):
        return ""
    return text


def spoken_story(story: EntertainmentStory) -> str:
    """One on-air beat from the headline. Outlet names are not added."""
    title = _strip_outlet_prefix(story.title)
    summary = _summary_for_air(story.summary)
    if summary and summary.lower() not in title.lower() and title.lower() not in summary.lower():
        if summary[0].isalpha() and summary[0].islower():
            summary = summary[0].upper() + summary[1:]
        if title[-1:] not in ".!?":
            return f"{title}. {summary}"
        return f"{title} {summary}"
    return title


def sports_close_hands_to_michael(close: str) -> str:
    """Dave's sports close hands to Michael G, not straight to DJ Mo."""
    text = _WS_RE.sub(" ", str(close or "")).strip()
    if not text:
        return DAVE_SPORTS_CLOSE
    if re.search(r"(?i)\bmichael\s+g\b", text):
        return text
    if _STRAIGHT_TO_MO_RE.search(text):
        return DAVE_SPORTS_CLOSE
    if text[-1] not in ".!?":
        text += "."
    return f"{text} Michael G has the entertainment report."


def michael_g_script(stories: list[EntertainmentStory]) -> str:
    lines = [MICHAEL_OPEN]
    if stories:
        lines.extend(spoken_story(story) for story in stories[:ENTERTAINMENT_STORY_COUNT])
    else:
        lines.append(MICHAEL_EMPTY)
    lines.append(MICHAEL_HANDOFF)
    return "\n".join(lines)


def format_entertainment_prompt(
    stories: list[EntertainmentStory],
    *,
    rules: str = DEFAULT_ENTERTAINMENT_REPORT_RULES,
) -> str:
    """Local-AI prompt: sports-style rules plus only the supplied stories."""
    count = len(stories)
    lines = [rules.strip(), "", f"SUPPLIED STORIES ({count}):"]
    if not stories:
        lines.append("(none — do not invent entertainment stories; hand off to DJ Mo.)")
    else:
        for index, story in enumerate(stories, start=1):
            lines.append(f"{index}. {spoken_story(story)}")
    lines.append("")
    if count >= ENTERTAINMENT_STORY_COUNT:
        lines.append(
            "Read exactly these four stories, in order, one short beat each. "
            "Do not add a fifth story."
        )
    elif count:
        lines.append(
            f"Only {count} usable stor{'y' if count == 1 else 'ies'} were supplied. "
            "Read those and do not invent stories to reach four."
        )
    else:
        lines.append("No usable stories were supplied. Do not invent any. Hand off to DJ Mo.")
    lines.append("Do not name Deadline, TMZ, or Variety on the air.")
    lines.append("After the stories, hand the show to DJ Mo.")
    lines.append(f"DJ Mo's next line is: {MO_THANKS}")
    return "\n".join(lines)


def mo_thanks_line(thanks: str = "") -> str:
    text = _WS_RE.sub(" ", str(thanks or "")).strip()
    if re.search(r"(?i)\bmichael\s+g\b", text) and re.search(r"(?i)\bthanks\b", text):
        return text
    return MO_THANKS


def build_morning_flow(
    stories: list[EntertainmentStory] | None = None,
    *,
    sports_close: str = "",
    mo_thanks: str = "",
    rules: str = DEFAULT_ENTERTAINMENT_REPORT_RULES,
) -> dict[str, Any]:
    """Morning order after the hard-news block: Dave, Michael G, then DJ Mo."""
    selected = select_entertainment_stories(list(stories or []))
    dave_close = sports_close_hands_to_michael(sports_close)
    michael_script = michael_g_script(selected)
    thanks = mo_thanks_line(mo_thanks)
    return {
        "order": ["news", "dave_sports", "michael_g_entertainment", "mo_thanks"],
        "story_count": len(selected),
        "stories": selected,
        "dave_sports_close": dave_close,
        "michael_g_script": michael_script,
        "michael_g_prompt": format_entertainment_prompt(selected, rules=rules),
        "mo_thanks": thanks,
        "script": "\n\n".join(
            [
                "[Dave]",
                dave_close,
                "[Michael G]",
                michael_script,
                "[DJ Mo]",
                thanks,
            ]
        ),
    }


def morning_preview_lines(rules: dict[str, Any] | None = None) -> list[str]:
    """Development preview of the handoff. Does not invent on-air stories."""
    payload = rules or {}
    close = sports_close_hands_to_michael(str(payload.get("sports_close", "")))
    thanks = mo_thanks_line(str(payload.get("mo_entertainment_thanks", "")))
    return [
        "[Morning handoff]",
        "[Dave]",
        close,
        "",
        "[Michael G]",
        MICHAEL_OPEN,
        "[Up to four supplied entertainment stories. Do not invent stories in this preview.]",
        MICHAEL_HANDOFF,
        "",
        "[DJ Mo]",
        thanks,
        "",
    ]


def _michael_record(record: dict[str, Any] | None = None) -> dict[str, Any]:
    item = dict(record or {})
    item["id"] = item.get("id") or MICHAEL_G_NEWS_ID
    item["name"] = MICHAEL_G_NAME
    item["role"] = item.get("role") or "entertainment"
    if not str(item.get("voice_id") or "").strip():
        item["voice_id"] = MICHAEL_G_VOICE_RECORD_ID
    item.setdefault("enabled", True)
    notes = str(item.get("notes") or "")
    if MICHAEL_G_VOICEBOX_ID not in notes:
        item["notes"] = (notes + "\n" + MICHAEL_G_VOICEBOX_PROFILE).strip()
    return item


def _is_michael(record: dict[str, Any]) -> bool:
    if record.get("id") == MICHAEL_G_NEWS_ID:
        return True
    name = _WS_RE.sub(" ", str(record.get("name") or "")).strip().lower().rstrip(".")
    return name == "michael g"


def ensure_michael_g_personality(personalities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Insert Michael G after Dave when an existing news desk is missing him."""
    updated: list[dict[str, Any]] = []
    found = False
    for record in personalities:
        if _is_michael(record):
            updated.append(_michael_record(record))
            found = True
        else:
            updated.append(record)
    if found:
        return updated

    insert_at = len(updated)
    for index, record in enumerate(updated):
        if record.get("id") == "mos_place_dave":
            insert_at = index + 1
            break
    updated.insert(insert_at, _michael_record())
    return updated


def apply_entertainment_script_rules(rules: dict[str, Any]) -> dict[str, Any]:
    """Upgrade saved script rules with the Michael G handoff. Other fields stay."""
    personality = str(rules.get("news_first_personality_rules") or "").strip()
    if "michael g" not in personality.lower():
        if personality:
            personality = f"{personality.rstrip('. ')}. {ENTERTAINMENT_PERSONALITY_CLAUSE}"
        else:
            personality = f"Lead anchor opens every newscast. {ENTERTAINMENT_PERSONALITY_CLAUSE}"
    rules["news_first_personality_rules"] = personality

    rules["sports_close"] = sports_close_hands_to_michael(str(rules.get("sports_close", "")))
    rules["mo_entertainment_thanks"] = mo_thanks_line(str(rules.get("mo_entertainment_thanks", "")))
    rules["entertainment_story_count"] = ENTERTAINMENT_STORY_COUNT

    report_rules = str(rules.get("entertainment_report_rules") or "").strip()
    if not report_rules:
        rules["entertainment_report_rules"] = DEFAULT_ENTERTAINMENT_REPORT_RULES
    elif not report_rules.startswith(DEFAULT_ENTERTAINMENT_REPORT_RULES):
        lowered = report_rules.lower()
        if "michael g" not in lowered or "do not invent" not in lowered:
            rules["entertainment_report_rules"] = (
                f"{DEFAULT_ENTERTAINMENT_REPORT_RULES} {report_rules}"
            ).strip()

    feeds = rules.get("entertainment_feeds")
    if not isinstance(feeds, list):
        feeds = []
    normalized_feeds: list[str] = []
    seen: set[str] = set()
    for url in list(entertainment_feed_urls()) + [str(item) for item in feeds]:
        cleaned = url.strip()
        key = cleaned.lower().rstrip("/")
        if not cleaned or key in seen:
            continue
        seen.add(key)
        normalized_feeds.append(cleaned)
    rules["entertainment_feeds"] = normalized_feeds
    return rules


def main() -> int:
    """Print today's entertainment handoff. Feeds fail soft when unreachable."""
    stories = collect_entertainment_stories(fetch=True)
    package = build_morning_flow(stories)
    print(package["script"])
    print()
    print(package["michael_g_prompt"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

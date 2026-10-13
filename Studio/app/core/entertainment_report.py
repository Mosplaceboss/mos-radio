"""Morning entertainment report for Michael G.

Runs after Dave's sports in the morning newscast. Michael G reads four slots,
in order, then hands to DJ Mo. DJ Mo thanks Michael G by name.

1. A TMZ celebrity item: a death, gossip, or a sighting.
2. One bigger Deadline entertainment story. If Deadline is empty or down, a
   second usable TMZ item may fill this slot.
3. One new movie or trailer from Variety film news only: title, when it arrives
   if the item says so, and one sentence on what it is.
4. A few words from Variety reviews: title plus one or two sentences. The news
   feeds are not turned into a review.

A down or empty feed skips that slot. Graphic crime, explicit sexual content,
and birthdays are dropped. Nothing here invents gossip.

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

SLOT_TMZ = "tmz_celebrity"
SLOT_DEADLINE = "deadline_news"
SLOT_FILM_NEWS = "variety_film_news"
SLOT_REVIEW = "variety_review"
SLOT_ORDER = (SLOT_TMZ, SLOT_DEADLINE, SLOT_FILM_NEWS, SLOT_REVIEW)

ENTERTAINMENT_SOURCES: tuple[dict[str, str], ...] = (
    {
        "id": "tmz",
        "name": "TMZ",
        "kind": "celebrity",
        "slot": SLOT_TMZ,
        "url": "https://www.tmz.com/rss.xml",
    },
    {
        "id": "deadline",
        "name": "Deadline",
        "kind": "entertainment_news",
        "slot": SLOT_DEADLINE,
        "url": "https://deadline.com/feed/atom/",
    },
    {
        "id": "variety_film",
        "name": "Variety Film",
        "kind": "film_news",
        "slot": SLOT_FILM_NEWS,
        "url": "https://variety.com/v/film/feed/",
    },
    {
        "id": "variety_reviews",
        "name": "Variety Reviews",
        "kind": "film_review",
        "slot": SLOT_REVIEW,
        "url": "https://variety.com/v/film/reviews/feed/",
    },
)

DAVE_SPORTS_CLOSE = "That's sports for this morning. Michael G has the entertainment report."
MICHAEL_OPEN = "Thanks, Dave."
MICHAEL_HANDOFF = "DJ Mo, back to you."
MICHAEL_EMPTY = "That's all for entertainment this morning."
MO_THANKS = "Thanks, Michael G."

DEFAULT_ENTERTAINMENT_REPORT_RULES = (
    "Michael G reads the entertainment report after Dave's sports. "
    "Use only the supplied stories, in this order: "
    "a celebrity item about a death, gossip, or a sighting; "
    "one bigger entertainment-news item, or a second celebrity item if that news feed has nothing; "
    "one new movie or trailer from the film-news feed, with the title, when it arrives if the item says so, "
    "and one sentence on what it is; "
    "then a few words about a movie from Variety reviews: the title plus one or two sentences, not the whole review. "
    "Do not invent a review from the news feeds. "
    "If a feed is down or a slot has nothing usable, skip that slot and do not invent gossip, quotes, or extra stories. "
    "Skip graphic crime, sexual content, and birthdays. "
    "Do not name the outlets on the air. "
    "Thank Dave, then read the supplied slots, then hand the show to DJ Mo. "
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
_BIRTHDAY_RE = re.compile(r"(?i)\b(?:birthdays?|born on this day|turns \d{1,3})\b")
_CELEBRITY_RE = re.compile(
    r"(?i)\b("
    r"dies|died|dead at|passes away|passed away|obituary|"
    r"gossip|rumou?rs?|dating|split|splits|breakup|broke up|engaged|engagement|wedding|divorc\w*|"
    r"spotted|sighting|sightings|seen with|steps out|"
    r"celebrity|actor|actress|singer|rapper|star"
    r")\b"
)
_REVIEW_ITEM_RE = re.compile(r"(?i)^review\b|\b(?:movie|film)\s+review\b")
_FILM_NEWS_PREFER_RE = re.compile(
    r"(?i)\b(?:trailer|teaser|movie|film|opens|opening|premiere|premieres|theaters|theatres)\b"
)
_ARRIVAL_RE = re.compile(
    r"(?i)\b("
    r"(?:opens|opening|premieres|premiering|arrives|arriving|debuts|hits theaters|in theaters|in theatres|"
    r"set for|coming to theaters)"
    r"(?:\s+\w+){0,6}"
    r")"
)
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
    slot: str = ""


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
    if _BIRTHDAY_RE.search(blob):
        return False
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
        if len(summary) > 900:
            summary = summary[:897].rstrip() + "..."
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


def _story_pool(story: EntertainmentStory) -> str | None:
    """Which slot pool a story belongs to. Slot wins so a TMZ fallback stays put."""
    if story.slot == SLOT_REVIEW or story.source_id == "variety_reviews" or story.kind == "film_review":
        return "reviews"
    if story.slot == SLOT_FILM_NEWS or story.source_id == "variety_film" or story.kind in {"film_news", "film"}:
        return "film_news"
    if story.slot == SLOT_DEADLINE or story.source_id == "deadline" or story.kind == "entertainment_news":
        return "deadline"
    if story.slot == SLOT_TMZ or story.source_id == "tmz" or story.kind == "celebrity":
        return "tmz"
    return None


def _is_review_item(story: EntertainmentStory) -> bool:
    return _REVIEW_ITEM_RE.search(story.title) is not None


def _deduped_safe(stories: list[EntertainmentStory]) -> list[EntertainmentStory]:
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
    return usable


def _with_slot(story: EntertainmentStory, slot: str) -> EntertainmentStory:
    if story.slot == slot:
        return story
    return EntertainmentStory(
        title=story.title,
        summary=story.summary,
        url=story.url,
        source_id=story.source_id,
        source_name=story.source_name,
        kind=story.kind,
        published=story.published,
        slot=slot,
    )


def select_entertainment_stories(
    stories: list[EntertainmentStory],
    *,
    limit: int = ENTERTAINMENT_STORY_COUNT,
) -> list[EntertainmentStory]:
    """Fill the four morning slots in order. Missing slots are skipped.

    Slot 1 is a TMZ celebrity item (death, gossip, or sighting preferred).
    Slot 2 is Deadline. A second TMZ item fills slot 2 only when Deadline
    has nothing usable. Slot 3 is Variety film news, never a review.
    Slot 4 is the Variety reviews feed only.
    """
    grouped: dict[str, list[EntertainmentStory]] = {
        "tmz": [],
        "deadline": [],
        "film_news": [],
        "reviews": [],
    }
    for story in stories:
        pool = _story_pool(story)
        if pool:
            grouped[pool].append(story)

    tmz = _deduped_safe(grouped["tmz"])
    celebrity = [story for story in tmz if _CELEBRITY_RE.search(f"{story.title} {story.summary}")]
    tmz_order = celebrity or tmz
    if len(celebrity) > 1:
        tmz_fallback = celebrity[1:]
    else:
        used_title = _dedupe_key(tmz_order[0].title) if tmz_order else ""
        tmz_fallback = [story for story in tmz if _dedupe_key(story.title) != used_title]

    deadline = _deduped_safe(grouped["deadline"])
    film_news = [
        story
        for story in _deduped_safe(grouped["film_news"])
        if not _is_review_item(story)
    ]
    film_preferred = [
        story for story in film_news if _FILM_NEWS_PREFER_RE.search(f"{story.title} {story.summary}")
    ]
    film_order = film_preferred or film_news
    reviews = _deduped_safe(grouped["reviews"])

    chosen: list[EntertainmentStory] = []
    if tmz_order:
        chosen.append(_with_slot(tmz_order[0], SLOT_TMZ))
    if deadline:
        chosen.append(_with_slot(deadline[0], SLOT_DEADLINE))
    elif tmz_fallback:
        chosen.append(_with_slot(tmz_fallback[0], SLOT_DEADLINE))
    if film_order:
        chosen.append(_with_slot(film_order[0], SLOT_FILM_NEWS))
    if reviews:
        chosen.append(_with_slot(reviews[0], SLOT_REVIEW))
    if limit < 1:
        return []
    return chosen[:limit]


def collect_entertainment_stories(
    xml_by_url: dict[str, str | BaseException] | None = None,
    *,
    fetch: bool = False,
    timeout: float = 12.0,
) -> list[EntertainmentStory]:
    """Gather the four entertainment slots. Each feed fails on its own.

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


def _summary_body(summary: str) -> str:
    """Outlet-cleaned summary text. Kept long enough for one or two sentences."""
    text = _strip_outlet_prefix(summary)
    text = _ATTRIBUTION_RE.sub("", text)
    text = _OUTLET_SAYS_RE.sub("", text)
    text = _clean_text(text)
    if not text or _OUTLET_WORD_RE.search(text):
        return ""
    return text


def _summary_for_air(summary: str) -> str:
    """Use a short factual blurb. Drop it when it is outlet attribution."""
    return _first_sentence(_summary_body(summary))


def _take_sentences(text: str, count: int) -> list[str]:
    cleaned = _clean_text(text)
    if not cleaned or count < 1:
        return []
    sentences: list[str] = []
    for part in re.findall(r"[^.!?]+[.!?]?", cleaned):
        sentence = _WS_RE.sub(" ", part).strip()
        if not sentence:
            continue
        if sentence[-1:] not in ".!?":
            sentence += "."
        sentences.append(sentence)
        if len(sentences) >= count:
            break
    return sentences


def _finish_title(title: str) -> str:
    text = _strip_outlet_prefix(title)
    if not text:
        return ""
    if text[-1:] not in ".!?":
        return f"{text}."
    return text


def _spoken_general(story: EntertainmentStory) -> str:
    title = _strip_outlet_prefix(story.title)
    summary = _summary_for_air(story.summary)
    if summary and summary.lower() not in title.lower() and title.lower() not in summary.lower():
        if summary[0].isalpha() and summary[0].islower():
            summary = summary[0].upper() + summary[1:]
        if title[-1:] not in ".!?":
            return f"{title}. {summary}"
        return f"{title} {summary}"
    return title


def _is_arrival_only(sentence: str) -> bool:
    match = _ARRIVAL_RE.search(sentence)
    if not match:
        return False
    leftover = _ARRIVAL_RE.sub(" ", sentence)
    leftover = re.sub(r"(?i)\b(?:the|a|an|on|in|this|next)\b", " ", leftover)
    leftover = re.sub(r"[^\w]+", "", leftover)
    return len(leftover) < 4


def _spoken_film_news(story: EntertainmentStory) -> str:
    """Title, arrival when the item states it, and one sentence on what it is."""
    title = _finish_title(story.title)
    body = _summary_body(story.summary)
    what = ""
    for sentence in _take_sentences(body, 3):
        if _is_arrival_only(sentence):
            continue
        what = sentence
        break
    arrival = ""
    match = _ARRIVAL_RE.search(f"{title} {body}")
    if match:
        arrival = _clean_text(match.group(1)).strip(" .,;")
    parts = [title] if title else []
    arrival_in_title = bool(arrival) and arrival.lower() in title.lower()
    arrival_in_what = bool(arrival and what) and arrival.lower() in what.lower()
    if arrival and not arrival_in_title and not arrival_in_what:
        if arrival[0].isalpha() and arrival[0].islower():
            arrival = arrival[0].upper() + arrival[1:]
        if arrival[-1:] not in ".!?":
            arrival += "."
        parts.append(arrival)
    if what and what.lower() not in title.lower():
        parts.append(what if what[-1:] in ".!?" else f"{what}.")
    return " ".join(parts)


def _spoken_review(story: EntertainmentStory) -> str:
    """Title plus one or two sentences. The rest of the review stays off air."""
    title = _finish_title(story.title)
    kept: list[str] = []
    for sentence in _take_sentences(_summary_body(story.summary), 2):
        if title and sentence.lower().rstrip(".!?") in title.lower():
            continue
        kept.append(sentence)
    parts = [title] if title else []
    parts.extend(kept)
    return " ".join(parts)


def spoken_story(story: EntertainmentStory) -> str:
    """On-air beat for one slot. Outlet names are not added."""
    if story.slot == SLOT_REVIEW or story.kind == "film_review" or story.source_id == "variety_reviews":
        return _spoken_review(story)
    if story.slot == SLOT_FILM_NEWS or story.kind in {"film_news", "film"} or story.source_id == "variety_film":
        return _spoken_film_news(story)
    return _spoken_general(story)


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


_SLOT_PROMPT = (
    (SLOT_TMZ, "Celebrity item about a death, gossip, or a sighting."),
    (
        SLOT_DEADLINE,
        "Bigger entertainment-news item. A second celebrity item belongs here only when the news feed had nothing.",
    ),
    (
        SLOT_FILM_NEWS,
        "New movie or trailer from film news only. Say the title, when it arrives if the item says so, "
        "and one sentence on what it is. Do not turn this into a review.",
    ),
    (
        SLOT_REVIEW,
        "Movie review. Say the title and one or two sentences only. Do not read the whole review. "
        "Do not invent a review from the news items.",
    ),
)


def format_entertainment_prompt(
    stories: list[EntertainmentStory],
    *,
    rules: str = DEFAULT_ENTERTAINMENT_REPORT_RULES,
) -> str:
    """Local-AI prompt: sports-style rules plus only the supplied slots."""
    by_slot = {story.slot: story for story in stories if story.slot}
    lines = [rules.strip(), "", "SUPPLIED STORIES:"]
    filled = 0
    for index, (slot, label) in enumerate(_SLOT_PROMPT, start=1):
        story = by_slot.get(slot)
        if story is None:
            lines.append(f"{index}. {label} (skipped — do not invent this slot.)")
            continue
        filled += 1
        lines.append(f"{index}. {label} {spoken_story(story)}")
    lines.append("")
    if filled >= ENTERTAINMENT_STORY_COUNT:
        lines.append(
            "Read exactly these four stories, in order. "
            "Do not add a fifth story."
        )
    elif filled:
        lines.append(
            f"Only {filled} usable stor{'y' if filled == 1 else 'ies'} were supplied. "
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
        "[Four slots when the feeds supply them: celebrity item, entertainment news, new movie or trailer, short movie review. Do not invent stories in this preview.]",
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
    lowered_rules = report_rules.lower()
    has_slot_order = "variety reviews" in lowered_rules and "do not invent a review" in lowered_rules
    if not report_rules or not has_slot_order:
        if not report_rules or "new movies and reviews" in lowered_rules:
            rules["entertainment_report_rules"] = DEFAULT_ENTERTAINMENT_REPORT_RULES
        elif not report_rules.startswith(DEFAULT_ENTERTAINMENT_REPORT_RULES):
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

"""Morning entertainment report for Michael G.

Runs after Dave's sports in the morning newscast. Michael G thanks Dave,
says he has the entertainment report, adds one short light comical beat,
then reads four slots, in order, and hands to DJ Mo. DJ Mo thanks Michael G
by name. The comical beat stays in that open. It is not a punchline on a
death or illness story.

1. A TMZ celebrity item: a death, gossip, or a sighting, as one or two
   plain sentences. The headline is not read and then repeated as the lede.
2. One bigger Deadline entertainment story, in one or two sentences. If
   Deadline is empty or down, a second usable TMZ item may fill this slot.
3. Movie news from the Variety film feed only, in the "In movie news" shape.
   The film title is used, and only when the item actually names one.
   A theater day is spoken only when the item gives one. The plot comes from
   the blurb. Nothing is invented.
4. One more entertainment item from TMZ or Deadline, in the same plain speech.

Spec-script sales, writers labs, agency moves, cast laundry lists, and
untitled projects with no film title are skipped. There is no reviews feed.
Michael does not say "exclusive," "according to," "review," "critics say,"
or a star rating. A down or empty feed skips that slot. Graphic crime,
explicit sexual content, and birthdays are dropped.

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
SLOT_EXTRA = "more_entertainment"
SLOT_ORDER = (SLOT_TMZ, SLOT_DEADLINE, SLOT_FILM_NEWS, SLOT_EXTRA)

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
)

# Retired on purpose. Do not fetch or speak this feed.
_RETIRED_FEED_MARKERS = ("variety.com/v/film/reviews",)

DAVE_SPORTS_CLOSE = "That's sports for this morning. Michael G has the entertainment report."
MICHAEL_OPEN = "Thanks, Dave."
MICHAEL_BEAT = "I brought the popcorn, and I will keep this shorter than the previews."
MICHAEL_INTRO = f"Michael G here with the entertainment report. {MICHAEL_BEAT}"
MICHAEL_HANDOFF = "DJ Mo, back to you."
MICHAEL_EMPTY = "That's all for entertainment this morning."
MO_THANKS = "Thanks, Michael G."

DEFAULT_ENTERTAINMENT_REPORT_RULES = (
    "Michael G reads the entertainment report after Dave's sports. "
    "His personality is comical: light and warm, one or two sentences, then the stories. "
    "Not sarcastic about death or illness. Not a long monologue. "
    'Open with "Thanks, Dave. Michael G here with the entertainment report." '
    "then one short comical beat, then the supplied stories, then hand to DJ Mo. "
    "Do not put that comical beat on a death or illness story. "
    "Do not invent a movie title or a person's death for the joke. "
    "Use only the supplied stories, in this order: "
    "a celebrity item about a death, gossip, or a sighting, in one or two plain sentences; "
    "one bigger entertainment-news item, or a second celebrity item if that news feed has nothing, in one or two sentences; "
    "movie news that starts with In movie news, names the movie with a short get-ready only when a film title is supplied, "
    "says when it hits theaters only if the item gives a day or date, "
    "then one or two sentences on the story from the supplied blurb, then a short closer; "
    "then one more entertainment item from the celebrity or entertainment-news items. "
    "Do not read the headline and then the lede. "
    "Do not say exclusive, according to, or a list of parenthetical credits. "
    "Do not say review, critics say, or a star rating. "
    "Do not invent a plot, a release day, a cast, or a Friday. "
    "Skip spec-script sales, writers labs, agency moves, cast laundry lists, and untitled projects with no film title. "
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
_REVIEW_ITEM_RE = re.compile(r"(?i)^review\b|\breviews?\b|\b(?:movie|film)\s+review\b")
_FILM_NEWS_PREFER_RE = re.compile(
    r"(?i)\b(?:trailer|teaser|first look|opens|opening|premiere|premieres|hits theaters|in theaters|in theatres)\b"
)
_QUOTED_TITLE_RE = re.compile(
    r"[\"“]([^\"”]{2,80})[\"”]|(?:^|[\s(\[])['‘]([^'’]{2,80})['’](?=$|[\s,.:;!?)\]])"
)
_TRAILER_NAME_RE = re.compile(
    r"(?i)^(.+?)\s+(?:official\s+)?(?:trailer|teaser|first look)\b"
)
_EXCLUSIVE_RE = re.compile(r"(?i)\bexclusive\b\s*:?\s*")
_PAREN_RE = re.compile(r"\s*\([^)]*\)")
_ELLIPSIS_RE = re.compile(r"\s*(?:\.{3}|…)+\s*")
_OUTLET_CLAUSE_RE = re.compile(
    r"(?i),?\s*(?:deadline|tmz|variety)(?:\s+film)?\s+"
    r"(?:has learned|can reveal(?:\s+exclusively)?|reports|reported|says|writes|is reporting)\b[:,]?\s*"
)
_ACCORDING_RE = re.compile(r"(?i)\baccording to\b(?:\s+[^,.]{0,80},)?\s*")
_SPEC_RE = re.compile(
    r"(?i)\b(?:spec scripts?|comedy spec|horror spec|script spec|"
    r"acquir\w+\s+the rights to a\s+[^.]{0,40}\bspec)\b"
)
_WRITERS_LAB_RE = re.compile(r"(?i)\bwriters?\s+labs?\b")
_CAST_LIST_RE = re.compile(r"(?i)\bround(?:s|ed|ing)? out (?:the )?cast\b")
_AGENCY_RE = re.compile(r"(?i)\b(?:signs|signed) with\b")
_COMPANY_LAUNCH_RE = re.compile(
    r"(?i)\b(?:launch(?:es|ed)?|form(?:s|ed)?)\b.{0,40}\bproduction compan(?:y|ies)\b|"
    r"\bproduction compan(?:y|ies)\b.{0,40}\b(?:launch(?:es|ed)?|form(?:s|ed)?)\b"
)
_UNTITLED_RE = re.compile(r"(?i)\buntitled\b")
_THEATER_CUE_RE = re.compile(
    r"(?i)\b(?:opens|opening|premieres|premiering|hits theaters|in theaters|in theatres|"
    r"arrives in theaters|coming to theaters|debuts in theaters)\b"
)
_ARRIVAL_RE = re.compile(
    r"(?i)\b("
    r"(?:opens|opening|premieres|premiering|arrives|arriving|debuts|hits theaters|in theaters|in theatres|"
    r"set for|coming to theaters)"
    r"(?:\s+\w+){0,6}"
    r")"
)
_WHEN_RE = re.compile(
    r"(?i)\b("
    r"(?:this|next)\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|weekend)"
    r"|(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday),\s+"
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june|july|aug(?:ust)?|"
    r"sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?\s+\d{1,2}(?:,\s*\d{4})?"
    r"|(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june|july|aug(?:ust)?|"
    r"sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?\s+\d{1,2}(?:,\s*\d{4})?"
    r")\b"
)
_FORBIDDEN_SPOKEN_RE = re.compile(
    r"(?i)\breviews?\b|critics?\s+say|critics?\s+said|critic\s+says|star rating|"
    r"\b\d(?:\.\d)?\s*(?:out of|/)\s*5\b|"
    r"\b(?:\d+(?:\.\d+)?|one|two|three|four|five)\s+stars?\b|★+"
)
MOVIE_CLOSER = "Get ready for this one."
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
    if story.source_id == "variety_reviews" or story.kind == "film_review":
        return None
    if story.slot == SLOT_EXTRA:
        return "extra"
    if story.slot == SLOT_FILM_NEWS or story.source_id == "variety_film" or story.kind in {"film_news", "film"}:
        return "film_news"
    if story.slot == SLOT_DEADLINE or story.source_id == "deadline" or story.kind == "entertainment_news":
        return "deadline"
    if story.slot == SLOT_TMZ or story.source_id == "tmz" or story.kind == "celebrity":
        return "tmz"
    return None


def _is_review_item(story: EntertainmentStory) -> bool:
    if story.source_id == "variety_reviews" or story.kind == "film_review":
        return True
    return _REVIEW_ITEM_RE.search(story.title) is not None


def _is_unlistenable(story: EntertainmentStory) -> bool:
    """Industry copy that does not belong on a morning music-radio show."""
    blob = f"{story.title} {story.summary}"
    if _WRITERS_LAB_RE.search(blob) or _CAST_LIST_RE.search(blob):
        return True
    if _AGENCY_RE.search(blob) or _COMPANY_LAUNCH_RE.search(blob) or _SPEC_RE.search(blob):
        return True
    if _UNTITLED_RE.search(blob) and not _movie_name(story.title):
        return True
    return False


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
    has nothing usable. Slot 3 is a Variety film item that names a movie
    people could see, with a trailer or opening preferred over a deal.
    Slot 4 is one more TMZ or Deadline item. Reviews, spec sales, writers
    labs, agency moves, and cast laundry lists are not used.
    """
    grouped: dict[str, list[EntertainmentStory]] = {
        "tmz": [],
        "deadline": [],
        "film_news": [],
        "extra": [],
    }
    for story in stories:
        pool = _story_pool(story)
        if pool:
            grouped[pool].append(story)

    tmz = [story for story in _deduped_safe(grouped["tmz"]) if not _is_unlistenable(story)]
    celebrity = [story for story in tmz if _CELEBRITY_RE.search(f"{story.title} {story.summary}")]
    tmz_order = celebrity or tmz
    if len(celebrity) > 1:
        tmz_fallback = celebrity[1:]
    else:
        used_title = _dedupe_key(tmz_order[0].title) if tmz_order else ""
        tmz_fallback = [story for story in tmz if _dedupe_key(story.title) != used_title]

    deadline = [story for story in _deduped_safe(grouped["deadline"]) if not _is_unlistenable(story)]
    film_news = [
        story
        for story in _deduped_safe(grouped["film_news"])
        if not _is_review_item(story) and not _is_unlistenable(story) and _movie_name(story.title)
    ]
    film_preferred = [
        story for story in film_news if _FILM_NEWS_PREFER_RE.search(f"{story.title} {story.summary}")
    ]
    film_order = film_preferred or film_news

    chosen: list[EntertainmentStory] = []
    used: set[str] = set()
    if tmz_order:
        chosen.append(_with_slot(tmz_order[0], SLOT_TMZ))
        used.add(_dedupe_key(tmz_order[0].title))
    if deadline:
        chosen.append(_with_slot(deadline[0], SLOT_DEADLINE))
        used.add(_dedupe_key(deadline[0].title))
    elif tmz_fallback:
        chosen.append(_with_slot(tmz_fallback[0], SLOT_DEADLINE))
        used.add(_dedupe_key(tmz_fallback[0].title))
    if film_order:
        chosen.append(_with_slot(film_order[0], SLOT_FILM_NEWS))
    extras = list(grouped["extra"])
    for story in tmz + deadline:
        key = _dedupe_key(story.title)
        if not key or key in used or _is_review_item(story):
            continue
        extras.append(story)
    extras = _deduped_safe(extras)
    if extras:
        chosen.append(_with_slot(extras[0], SLOT_EXTRA))
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


_OUTLET_WORD_RE = re.compile(r"(?i)\b(deadline|tmz|variety)(?:\s+film)?\b")
_ATTRIBUTION_RE = re.compile(
    r"(?i)\b(?:according to|via|reports from|reported by)\s+"
    r"(deadline|tmz|variety)(?:\s+film)?\b[:,]?\s*"
)
_OUTLET_SAYS_RE = re.compile(
    r"(?i)\b(deadline|tmz|variety)(?:\s+film)?\s+"
    r"(?:reports|says|writes|reported|is reporting)\b[:,]?\s*"
)


def _plain_body(summary: str) -> str:
    """Summary text with outlet names, exclusives, and credit lists removed."""
    text = _strip_outlet_prefix(summary)
    text = re.sub(r"\s*\[(?:…|\.{3})\]\s*", " ", text)
    # Feed ellipses are pauses or cutoffs, not new sentences.
    text = _ELLIPSIS_RE.sub(", ", text)
    text = _EXCLUSIVE_RE.sub("", text)
    text = _PAREN_RE.sub("", text)
    text = _OUTLET_CLAUSE_RE.sub("", text)
    text = _ATTRIBUTION_RE.sub("", text)
    text = _OUTLET_SAYS_RE.sub("", text)
    text = _ACCORDING_RE.sub("", text)
    text = _OUTLET_WORD_RE.sub("", text)
    text = re.sub(r"\s+,", ",", text)
    text = re.sub(r"(?:,\s*)+$", "", text)
    text = _clean_text(text)
    return text.strip(" ,;:-")


def _cap_sentence(sentence: str) -> str:
    text = _WS_RE.sub(" ", sentence).strip()
    if text and text[0].isalpha() and text[0].islower():
        text = text[0].upper() + text[1:]
    return text


def _protect_initials(text: str) -> str:
    """Keep C.S. and Mr. from looking like the end of a sentence."""
    protected = re.sub(
        r"\b(Mr|Mrs|Ms|Dr|St|Jr|Sr|Prof|Gen|Rep|Sen|Rev|vs|etc|Inc|Ltd)\.",
        r"\1<dot>",
        text,
        flags=re.IGNORECASE,
    )
    protected = re.sub(r"\b([A-Z])\.(?=[A-Z]\.)", r"\1<dot>", protected)
    protected = re.sub(r"<dot>([A-Z])\.(?=\s)", r"<dot>\1<dot>", protected)
    return protected


def _restore_initials(text: str) -> str:
    return text.replace("<dot>", ".")


_DANGLING_END_RE = re.compile(
    r"(?i)\b(?:in|on|of|to|for|with|by|from|and|or|the|a|an|between|who|that|which|into)\s*$"
)


def _is_speakable_sentence(sentence: str) -> bool:
    words = re.findall(r"[A-Za-z0-9'’$]+", sentence)
    if len(words) < 3:
        return False
    core = re.sub(r"[\"'”’]+$", "", sentence.rstrip(".!? ")).rstrip()
    return _DANGLING_END_RE.search(core) is None


def _take_sentences(text: str, count: int) -> list[str]:
    cleaned = _protect_initials(_clean_text(text))
    if not cleaned or count < 1:
        return []
    sentences: list[str] = []
    for match in re.finditer(r"[^.!?]*[.!?]+[\"'”’]*|[^.!?]+$", cleaned):
        raw = match.group(0).strip()
        if not raw:
            continue
        core = raw.rstrip("\"'”’ ")
        truncated = core[-1:] not in ".!?"
        sentence = _cap_sentence(_restore_initials(raw))
        if truncated:
            cut = sentence.rfind(",")
            if cut >= 40:
                sentence = sentence[:cut].rstrip()
        sentence = sentence.strip(" ,;:-")
        if not sentence:
            continue
        if sentence.rstrip("\"'”’ ")[-1:] not in ".!?":
            sentence += "."
        if not _is_speakable_sentence(sentence):
            continue
        sentences.append(sentence)
        if len(sentences) >= count:
            break
    return sentences


def _is_arrival_only(sentence: str) -> bool:
    match = _ARRIVAL_RE.search(sentence)
    if not match:
        return False
    leftover = _ARRIVAL_RE.sub(" ", sentence)
    leftover = re.sub(r"(?i)\b(?:the|a|an|on|in|this|next)\b", " ", leftover)
    leftover = re.sub(r"[^\w]+", "", leftover)
    return len(leftover) < 4


def _looks_like_title(name: str) -> bool:
    text = _clean_text(name).strip(" '\"“”‘’:-|,")
    if len(text) < 2 or len(text) > 60:
        return False
    words = text.split()
    if not words or len(words) > 8:
        return False
    if re.search(r"(?i)\b(?:acquires|exclusive|spec|round out|writers lab|signs with)\b", text):
        return False
    return True


def _movie_name(title: str) -> str:
    """Pull a film title from a headline. Never the whole acquisition headline."""
    text = _strip_outlet_prefix(title)
    text = _EXCLUSIVE_RE.sub("", text)
    text = _PAREN_RE.sub("", text)
    text = _clean_text(text)
    quoted_name = ""
    quoted = _QUOTED_TITLE_RE.search(text)
    if quoted:
        candidate = _clean_text(quoted.group(1) or quoted.group(2) or "").strip(" -:|")
        if _looks_like_title(candidate):
            quoted_name = candidate
    trailer_name = ""
    trailer = _TRAILER_NAME_RE.match(text)
    if trailer:
        candidate = _clean_text(trailer.group(1)).strip(" '\"“”‘’:-|")
        if _looks_like_title(candidate):
            trailer_name = candidate
    if (
        trailer_name
        and quoted_name
        and trailer_name.startswith(quoted_name)
        and len(trailer_name) > len(quoted_name)
    ):
        return trailer_name
    return quoted_name or trailer_name


def _theater_when(text: str) -> str:
    """A theater day copied from an opening line. Never a made-up Friday."""
    source = text or ""
    for cue in _THEATER_CUE_RE.finditer(source):
        window = source[cue.end(): cue.end() + 48]
        match = _WHEN_RE.search(window)
        if match:
            return _clean_text(match.group(1)).strip(" .,;")
    return ""


_DEATH_CLAIM_RE = re.compile(
    r"(?i)\b(?:the late|died|dies|passes away|passed away|has died|was killed)\b|\bdeath\b"
)
_HEADLINE_DEATH_RE = re.compile(
    r"(?i)\b(?:dead|dies|died|death|mourns|obituary|killed|passes|passed away)\b"
)


def _death_not_in_headline(sentence: str, title: str) -> bool:
    """A blurb must not declare a death the headline never reported."""
    if not _DEATH_CLAIM_RE.search(sentence or ""):
        return False
    return _HEADLINE_DEATH_RE.search(title or "") is None


def _story_sentences(text: str, limit: int = 2) -> list[str]:
    kept: list[str] = []
    for sentence in _take_sentences(text, 8):
        if _is_arrival_only(sentence) or _FORBIDDEN_SPOKEN_RE.search(sentence):
            continue
        if _WHEN_RE.fullmatch(sentence.strip(" .!?")):
            continue
        kept.append(sentence)
        if len(kept) >= limit:
            break
    return kept


def _headline_sentence(title: str) -> str:
    """One sentence from a headline, used only when the item has no blurb."""
    text = _strip_outlet_prefix(title)
    text = _EXCLUSIVE_RE.sub("", text)
    text = _PAREN_RE.sub("", text)
    text = _OUTLET_WORD_RE.sub("", text)
    text = _clean_text(text).strip(" -:|")
    if not text:
        return ""
    if text[-1:] not in ".!?":
        text += "."
    return text


def _spoken_film_news(story: EntertainmentStory) -> str:
    """In movie news: title when we have one, optional theater day, blurb, closer."""
    if _is_unlistenable(story):
        return ""
    name = _clean_text(_FORBIDDEN_SPOKEN_RE.sub(" ", _movie_name(story.title))).strip(" -:|,")
    body = _plain_body(story.summary)
    when = _theater_when(f"{story.title} {body}") if name else ""
    sentences = _story_sentences(body, 2)
    if name:
        parts = [f"In movie news, {name} fans, get ready!"]
    elif sentences:
        parts = ["In movie news."]
    else:
        return ""
    if when:
        parts.append(f"It hits theaters {when}.")
    parts.extend(sentences)
    parts.append(MOVIE_CLOSER)
    return " ".join(part for part in parts if part)


def _spoken_general(story: EntertainmentStory) -> str:
    """One or two plain sentences. The headline is not read in front of the lede."""
    if _is_unlistenable(story):
        return ""
    title_key = _dedupe_key(_headline_sentence(story.title).rstrip("."))
    kept: list[str] = []
    for sentence in _story_sentences(_plain_body(story.summary), 2):
        if _dedupe_key(sentence.rstrip(".")) == title_key:
            continue
        if re.search(r"(?i)\b(?:exclusive|according to)\b", sentence):
            continue
        if _death_not_in_headline(sentence, story.title):
            continue
        kept.append(sentence)
    if kept:
        return " ".join(kept)
    return _headline_sentence(story.title)


def spoken_story(story: EntertainmentStory) -> str:
    """On-air beat for one slot. Outlet names are not added."""
    if _is_unlistenable(story):
        return ""
    if story.slot == SLOT_FILM_NEWS or story.kind in {"film_news", "film"} or story.source_id == "variety_film":
        spoken = _spoken_film_news(story)
    else:
        spoken = _spoken_general(story)
    if _FORBIDDEN_SPOKEN_RE.search(spoken):
        kept = [sentence for sentence in _take_sentences(spoken, 8) if not _FORBIDDEN_SPOKEN_RE.search(sentence)]
        spoken = " ".join(kept)
    return (
        spoken.replace("“", '"')
        .replace("”", '"')
        .replace("‘", "'")
        .replace("’", "'")
        .replace("–", "-")
        .replace("—", "-")
    )


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
    """Spoken fallback. The introduction is here even when OpenAI is not called."""
    lines = [MICHAEL_OPEN, MICHAEL_INTRO]
    if stories:
        lines.extend(
            line
            for line in (spoken_story(story) for story in stories[:ENTERTAINMENT_STORY_COUNT])
            if line
        )
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
        "Movie news only. Start with In movie news. Say fans, get ready only when a film title is supplied. "
        "Say when it hits theaters only if a day or date is supplied, "
        "then one or two sentences from the blurb, then a short closer. "
        "Do not read the headline and then the lede. "
        "Do not say exclusive, according to, review, critics say, or a star rating. "
        "Do not invent a plot, day, or cast.",
    ),
    (
        SLOT_EXTRA,
        "One more entertainment item from the celebrity or entertainment-news stories already supplied. "
        "Do not say review, critics say, or a star rating.",
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
    lines.append(
        'Open with "Thanks, Dave. Michael G here with the entertainment report." '
        "Then one short light, warm comical beat, then the stories. "
        "Not sarcastic about death or illness. Not a long monologue. "
        "Do not put that comical beat on a death or illness story. "
        "Do not invent a movie title or a person's death for the joke."
    )
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
        MICHAEL_INTRO,
        "[Four slots when the feeds supply them: celebrity item, entertainment news, movie news, one more entertainment item. Do not invent stories in this preview.]",
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
    has_movie_shape = "in movie news" in lowered_rules and "do not say review" in lowered_rules
    mentions_reviews_feed = "variety reviews" in lowered_rules or "reviews/feed" in lowered_rules
    has_intro = "michael g here with the entertainment report" in lowered_rules
    if not has_movie_shape or mentions_reviews_feed or not has_intro:
        rules["entertainment_report_rules"] = DEFAULT_ENTERTAINMENT_REPORT_RULES

    feeds = rules.get("entertainment_feeds")
    if not isinstance(feeds, list):
        feeds = []
    normalized_feeds: list[str] = []
    seen: set[str] = set()
    for url in list(entertainment_feed_urls()) + [str(item) for item in feeds]:
        cleaned = url.strip()
        key = cleaned.lower().rstrip("/")
        if not cleaned or key in seen or any(marker in key for marker in _RETIRED_FEED_MARKERS):
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

"""Morning entertainment report for Michael G.

Runs after Dave's sports in the morning newscast. The handoff is locked:

1. Dave hands the morning news to Michael.
2. Michael thanks Dave, then does the entertainment report. He does not
   thank Mo at the start.
3. After the report, Michael turns it over to Mo.
4. Mo thanks Michael, and may mention weekdays at 7:15 on Mo's Place Radio.

On a normal day Michael adds one short conversational beat that sounds like
him talking, using coffee or classic rock. He does not read his biography.
A death, obituary, or mourning item leads, and that open stays straight.
Stories are collected, deduped, and ranked before anything is written.
A confirmed death leads. Major Hollywood and television headlines come
next, then movies opening within seven days. Streaming, reviews, and box
office only fill leftover room. Four stories, refreshed every morning.
The first airing is October 14, 2026 at 7:15.

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
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

LOGGER = logging.getLogger("mos.entertainment_report")

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
        "id": "deadline",
        "name": "Deadline",
        "kind": "entertainment_news",
        "slot": SLOT_DEADLINE,
        "url": "https://deadline.com/feed/atom/",
    },
    {
        "id": "tmz",
        "name": "TMZ",
        "kind": "celebrity",
        "slot": SLOT_TMZ,
        "url": "https://www.tmz.com/rss.xml",
    },
    {
        "id": "variety",
        "name": "Variety",
        "kind": "headlines",
        "slot": SLOT_FILM_NEWS,
        "url": "https://feeds.feedburner.com/variety/headlines",
    },
)

# Supplemental search. These are not saved as station feeds. Each query is
# fetched whole; selection ranks the pool instead of keeping the newest few.
GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
ENTERTAINMENT_SEARCH_QUERIES: tuple[str, ...] = (
    "breaking celebrity news",
    "actor dies",
    "actor death",
    "actor passed away",
    "actor dead",
    "actor obituary",
    "musician dies",
    "hollywood obituary",
    "major TV news",
    "movie opening",
)

# General items older than a day yield to fresher news. A confirmed death can
# still lead on the next morning show. An obituary older than this is not
# breaking. Movie openings can use an older item when the film opens within
# the next week.
FRESH_HOURS = 24
DEATH_BREAKING_HOURS = 72
OPENING_DAYS = 7

# Retired on purpose. Do not fetch or speak these feeds.
_RETIRED_FEED_MARKERS = (
    "variety.com/v/film/reviews",
    "variety.com/v/film/feed",
)

DAVE_SPORTS_CLOSE = "That's sports for this morning. Michael G has the entertainment report."
MICHAEL_G_BIO = (
    "Mike Gleason has a BA in Communications-Journalism from Roger Williams University "
    "and an MA in Professional Writing & Communication from the University of Massachusetts-Dartmouth. "
    "He and his husband live in Southeast Massachusetts where they spoil their grandkids and their dog. "
    "Oh, right. I drink a lot of coffee and enjoy listening to classic rock and talking about all the different sub genres of rock music going back to the golden age."
)
MICHAEL_OPEN = "Thanks, Dave."
MICHAEL_REPORT = "Michael G here with the entertainment report."
MICHAEL_STRAIGHT_OPEN = f"{MICHAEL_OPEN} {MICHAEL_REPORT}"
# Stable fallback for a normal day. The model may vary the sentence.
# This one sounds like him talking about coffee and classic rock.
# It is not the biography, and it is not a disconnected gag.
MICHAEL_BEAT = (
    "I have had enough coffee to get us through this, and I am still not done talking about classic rock."
)
MICHAEL_WARM_OPEN = f"{MICHAEL_STRAIGHT_OPEN} {MICHAEL_BEAT}"
MICHAEL_INTRO = MICHAEL_WARM_OPEN
MICHAEL_HANDOFF = "DJ Mo, back to you."
MICHAEL_EMPTY = "That's all for entertainment this morning."
MO_THANKS = "Thanks, Michael G. Weekdays at 7:15 on Mo's Place Radio."
ENTERTAINMENT_FIRST_AIRING = "October 14, 2026 at 7:15"
# Dave, Michael thanks Dave, Michael turns it over to Mo, Mo thanks Michael.
LOCKED_HANDOFF_LINES = (
    DAVE_SPORTS_CLOSE,
    MICHAEL_STRAIGHT_OPEN,
    MICHAEL_HANDOFF,
    MO_THANKS,
)

DEFAULT_ENTERTAINMENT_REPORT_RULES = (
    "Michael G reads the entertainment report after Dave's sports. "
    "Handoff order is locked. Dave hands the morning news to Michael. "
    "Michael thanks Dave, then reads the entertainment report. "
    "Michael does not thank Mo at the start. Dave is the person he thanks. "
    "After the report, Michael turns it over to Mo. Mo thanks Michael. "
    "Mo may mention weekdays at 7:15 on Mo's Place Radio. "
    "The first airing is October 14, 2026 at 7:15. "
    "Four stories, refreshed every morning. "
    "His on-air name is Michael G. He does not read his biography. "
    "His personality is comical: light and warm, one short beat, then the stories. "
    "Not sarcastic about death or illness. Not a long monologue. "
    'On a normal day, open with "Thanks, Dave. Michael G here with the entertainment report." '
    "Then one short conversational beat that sounds like him talking, using coffee or classic rock. "
    "One sentence. Not a disconnected gag. "
    "One short beat. Not a biography. Not the degrees or the universities. Not the same sentence every day. "
    "A death, obituary, or mourning item leads, and the whole open is straight. "
    'Open with exactly "Thanks, Dave. Michael G here with the entertainment report." '
    "No coffee, no classic rock, no popcorn joke, no grandkids joke, no dog joke, and no husband joke. "
    "The death story itself stays straight. "
    "Do not invent a movie title or a person's death for the joke. "
    "Other stories are new movies when the feeds have them. "
    "Each movie is its own short paragraph: a hook, the title, the opening day only if it is supplied, "
    "the stars only if they are supplied, and what it is about. "
    "Movie news that starts with In movie news, names the movie with a short get-ready only when a film title is supplied, "
    "says when it hits theaters only if the item gives a day or date, "
    "then one or two sentences on the story from the supplied blurb, then a short closer. "
    "Do not read the headline and then the lede. "
    "Do not say exclusive, according to, or a list of parenthetical credits. "
    "Do not say review, critics say, or a star rating. "
    "Do not invent a plot, a release day, a cast, a star, or a Friday. "
    "Skip spec-script sales, writers labs, agency moves, cast laundry lists, and untitled projects with no film title. "
    "If a feed is down or a slot has nothing usable, skip that slot and do not invent gossip, quotes, or extra stories. "
    "Skip graphic crime, sexual content, and birthdays. "
    "About 350 to 450 words when four stories are supplied, and shorter when fewer qualify. "
    "Short sentences. No bullet points. "
    "A death airs only after at least two independent reputable sources, "
    "and an old obituary is not breaking news. "
    "Do not name the outlets on the air. "
    "Thank Dave, then read the supplied stories, then turn the show over to DJ Mo. "
    "Do not open with thanks to Mo. "
    "DJ Mo's next line thanks Michael G by name."
)

ENTERTAINMENT_PERSONALITY_CLAUSE = (
    "Dave hands to Michael G for the entertainment report "
    "instead of going straight to DJ Mo. Michael thanks Dave, then reads up to four supplied entertainment "
    "stories. He does not thank Mo at the start. Michael turns it over to DJ Mo. "
    "DJ Mo thanks Michael G by name and may mention weekdays at 7:15 on Mo's Place Radio."
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
    r"dismember\w*|decapitat\w*|gore|gruesome|"
    r"terror(?:ist|ism)?|bombing|hostage|massacre|"
    r"arrested for|charged with|indicted|mugshot"
    r")\b"
)
# A cause of death must not erase the announcement. It also must not be
# read as a graphic aside when the headline is not itself a death.
_SENSITIVE_CAUSE_RE = re.compile(r"(?i)\b(?:suicide|overdose)\b")
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
    updated: datetime | None = None
    outlet: str = ""
    confirmed_outlets: tuple[str, ...] = ()


def entertainment_feed_urls() -> list[str]:
    return [source["url"] for source in ENTERTAINMENT_SOURCES]


def google_news_rss_url(query: str) -> str:
    """Google News search RSS. Query is escaped; the rest of the URL stays fixed."""
    return GOOGLE_NEWS_RSS.format(query=quote(str(query or "").strip()))


def entertainment_search_urls() -> list[str]:
    return [google_news_rss_url(query) for query in ENTERTAINMENT_SEARCH_QUERIES]


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
    """First matching child, preferring `names` order over document order."""
    found: dict[str, str] = {}
    for child in list(item):
        name = _local_name(child.tag)
        if name not in found:
            text = _element_text(child).strip()
            if text:
                found[name] = text
    for name in names:
        if name.lower() in found:
            return found[name.lower()]
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
    if _UNSAFE_RE.search(blob):
        return False
    if _SENSITIVE_CAUSE_RE.search(blob) and not _title_reports_death(title_text):
        return False
    return True


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

    # Rank the whole document. Do not keep only the newest few items.
    stories: list[EntertainmentStory] = []
    for item in items:
        title = _strip_outlet_prefix(_child_text(item, ("title",)))
        summary = _strip_outlet_prefix(
            _child_text(item, ("description", "summary", "content", "subtitle"))
        )
        if not is_morning_safe(title, summary):
            continue
        # Publication date wins when the feed also has a later update time.
        # dc:date's local name is "date". updated is only a fallback.
        published = _parse_datetime(_child_text(item, ("published", "pubdate", "date")))
        updated = _parse_datetime(_child_text(item, ("updated",)))
        if published is None:
            published = updated
        outlet = _child_text(item, ("source",))
        source_name = source.get("name", "")
        if outlet:
            source_name = _clean_text(outlet) or source_name
            title = _strip_publisher_suffix(title, source_name)
        if len(summary) > 900:
            summary = summary[:897].rstrip() + "..."
        stories.append(
            EntertainmentStory(
                title=title,
                summary=summary,
                url=_child_link(item),
                source_id=source.get("id", ""),
                source_name=source_name,
                kind=source.get("kind", "general"),
                published=published,
                updated=updated,
                outlet=_clean_text(outlet),
            )
        )
    return stories


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


def _with_slot(story: EntertainmentStory, slot: str) -> EntertainmentStory:
    if story.slot == slot:
        return story
    return replace(story, slot=slot)


def _strip_publisher_suffix(title: str, publisher: str) -> str:
    name = _clean_text(publisher).strip(" .")
    text = _clean_text(title)
    if not name or not text:
        return text
    trimmed = re.sub(
        r"(?:\s*[-–—|:]\s*|\s+)" + re.escape(name) + r"[.\s]*$",
        "",
        text,
        flags=re.IGNORECASE,
    )
    return _clean_text(trimmed) or text


_FILM_CUE_RE = re.compile(
    r"(?i)\b(?:movie|film|cinema|screening|director|comedy|horror|drama|sequel|franchise|starring)\b"
)
_BREAKING_NEWS_RE = re.compile(
    r"(?i)\b(?:renews|renewed|orders|greenlights?|finale|canceled|cancelled|"
    r"strike|network|studio|emmy|oscar)\b"
)
_BOX_OFFICE_RE = re.compile(r"(?i)\b(?:box office|ticket sales)\b")
_STREAMING_RE = re.compile(
    r"(?i)\b(?:streaming|netflix|hulu|disney\+|prime video|premieres on)\b"
)
_OLD_DEATH_MENTION_RE = re.compile(
    r"(?i)\b(?:weeks|months|years)\s+after\b|\banniversary of (?:his|her|their) death\b"
)
_DEATH_ANNOUNCEMENT_RE = re.compile(
    r"(?i)(?:"
    r"\bobituar(?:y|ies)\b|"
    r"\bpass(?:es|ed) away\b|"
    r"\bpassing of\b|"
    r"\bdies\b|"
    r"\bdied\b|"
    r"\bdead at\b|"
    r"\bdead\s*:|"
    r"\bis dead\b|"
    r"\bfound dead\b|"
    r"\bpronounced dead\b|"
    r"\bconfirmed dead\b|"
    r"\bdeath of\b"
    r")"
)
_RUMOR_RE = re.compile(r"(?i)\b(?:unconfirmed|rumou?rs?)\b")
_CONFIRMED_WORD_RE = re.compile(r"(?i)\b(?:confirmed|confirmation)\b")
_SOCIAL_RE = re.compile(
    r"(?i)\b(?:facebook|instagram|tiktok|reddit|threads)\b|"
    r"(?:facebook|instagram|tiktok|reddit|threads)\.com|(?:^|\.)x\.com|twitter\.com"
)
_NAME_STOP = {
    "the", "a", "an", "of", "and", "on", "in", "for", "with", "after", "before",
    "his", "her", "their", "who", "was", "from", "best", "known", "as", "by",
    "at", "aged", "age",
}
_NAME_ROLE = {
    "actor", "actress", "singer", "rapper", "musician", "star", "costar", "co-star",
    "legend", "icon", "beloved", "famous", "veteran", "hollywood",
}
_REPUTABLE_KEYS = {
    "abc",
    "ap",
    "bbc",
    "billboard",
    "cbs",
    "cnn",
    "deadline",
    "empire",
    "entertainment weekly",
    "guardian",
    "hollywood reporter",
    "indiewire",
    "los angeles times",
    "nbc",
    "new york times",
    "npr",
    "page six",
    "pbs",
    "people",
    "reuters",
    "rolling stone",
    "the wrap",
    "tmz",
    "tvline",
    "usa today",
    "variety",
    "washington post",
}
_FAR_FUTURE = datetime(9999, 1, 1, tzinfo=timezone.utc)


def _title_reports_death(title: str) -> bool:
    """A headline that reports a death, not a later tribute or a 'weeks after' item."""
    text = _KILLED_IT_RE.sub(" ", _clean_text(title))
    if _OLD_DEATH_MENTION_RE.search(text):
        return False
    return _DEATH_ANNOUNCEMENT_RE.search(text) is not None


def _is_movie_item(story: EntertainmentStory) -> bool:
    """A new movie the morning report can read as its own short paragraph."""
    if _is_review_item(story) or _is_unlistenable(story):
        return False
    if is_death_obituary_or_mourning(story) or _title_reports_death(story.title):
        return False
    name = _movie_name(story.title)
    blob = f"{story.title} {story.summary}"
    trailer = _TRAILER_NAME_RE.match(_clean_text(story.title)) is not None
    filmish = _FILM_CUE_RE.search(blob) is not None or _FILM_NEWS_PREFER_RE.search(blob) is not None
    if name and (trailer or filmish or story.kind in {"film_news", "film"}):
        return True
    movie_source = story.kind in {"film_news", "film"} or story.source_id in {"variety_film", "variety"}
    return bool(movie_source and _FILM_NEWS_PREFER_RE.search(blob))


def _is_fill_entertainment(story: EntertainmentStory) -> bool:
    """A usable non-movie item when the feeds do not have four movies."""
    if _is_review_item(story) or _is_unlistenable(story) or _is_movie_item(story):
        return False
    if is_death_obituary_or_mourning(story):
        return False
    if story.kind in {"film_news", "film"} and not _movie_name(story.title):
        return False
    if story.source_id in {"variety_reviews"}:
        return False
    return story.source_id in {"tmz", "deadline", "variety", "variety_film"} or story.kind in {
        "celebrity",
        "entertainment_news",
        "headlines",
    }


def _as_utc(moment: datetime | None) -> datetime:
    if moment is None:
        return datetime.now(timezone.utc)
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def _age_hours(published: datetime | None, now: datetime) -> float | None:
    if published is None:
        return None
    return (_as_utc(now) - _as_utc(published)).total_seconds() / 3600.0


def _recency(story: EntertainmentStory, now: datetime) -> float:
    age = _age_hours(story.published, now)
    if age is None:
        return 10_000.0
    return age


def _source_label(story: EntertainmentStory) -> str:
    return _clean_text(story.outlet or story.source_name or story.source_id or "unknown")


def _outlet_key(story: EntertainmentStory) -> str:
    """Stable outlet id. Unknown publishers do not count as reputable."""
    raw = " ".join(
        part for part in (story.outlet, story.source_name, story.source_id) if part
    ).lower()
    if re.search(r"\bassociated press\b|\bap news\b|\bap\b", raw):
        return "ap"
    for needle in (
        "hollywood reporter",
        "new york times",
        "washington post",
        "los angeles times",
        "usa today",
        "entertainment weekly",
        "rolling stone",
        "the wrap",
        "page six",
        "deadline",
        "variety",
        "reuters",
        "guardian",
        "billboard",
        "indiewire",
        "tvline",
        "people",
        "empire",
        "tmz",
        "cnn",
        "bbc",
        "nbc",
        "abc",
        "cbs",
        "npr",
        "pbs",
    ):
        if re.search(rf"\b{re.escape(needle)}\b", raw):
            return needle
    if story.source_id in {"deadline", "tmz", "variety"}:
        return story.source_id
    return ""


def _is_social(story: EntertainmentStory) -> bool:
    blob = f"{story.url} {story.outlet} {story.source_name}"
    return _SOCIAL_RE.search(blob) is not None


def _is_reputable(story: EntertainmentStory) -> bool:
    if _is_social(story):
        return False
    return _outlet_key(story) in _REPUTABLE_KEYS


def _is_rumor(story: EntertainmentStory) -> bool:
    if _RUMOR_RE.search(story.title) is None:
        return False
    return _CONFIRMED_WORD_RE.search(f"{story.title} {story.summary}") is None


def _is_preconfirmed(story: EntertainmentStory) -> bool:
    return len(tuple(story.confirmed_outlets or ())) >= 2 and _title_reports_death(story.title)


def _name_key(phrase: str) -> str:
    """Person key from the clause next to the verb. Initials lose their dots."""
    clause = re.split(r"[,:;]", phrase or "", maxsplit=1)[0]
    tokens: list[str] = []
    for token in re.findall(r"[A-Za-z][A-Za-z'’.-]*", clause):
        token = token.lower().strip(".'’").replace(".", "")
        if len(token) <= 1 or token in _NAME_STOP:
            continue
        tokens.append(token)
    proper = [token for token in tokens if token not in _NAME_ROLE]
    chosen = proper or tokens
    if len(chosen) >= 2:
        return " ".join(chosen[-2:])
    return " ".join(chosen)


def _death_cluster_key(story: EntertainmentStory) -> str:
    title = _clean_text(story.title)
    title = re.sub(r"\s+[-–—|]\s+[^-–—|]{2,60}$", "", title)
    title = re.sub(r"[\"“”‘’][^\"“”‘’]{0,80}[\"“”‘’]", " ", title)
    if re.search(r"(?i)\bmourns?\b", title):
        tail = re.split(r"(?i)\bmourns?\b", title, maxsplit=1)[-1]
        tail = re.split(r"(?i)\b(?:following|after|over|amid)\b|:", tail)[0]
        return _name_key(tail) or _dedupe_key(story.title)
    match = re.search(
        r"(?i)^(?:obituary:?\s+)?(.+?)\s+(?:"
        r"is\s+dead|was\s+found\s+dead|found\s+dead|pronounced\s+dead|confirmed\s+dead|"
        r"dead|dies|died|has\s+died|passed\s+away|passes\s+away"
        r")\b",
        title,
    )
    if match:
        return _name_key(match.group(1)) or _dedupe_key(story.title)
    match = re.search(r"(?i)\bdeath of\s+(.+?)(?:\s+at\b|$|:)", title)
    if match:
        return _name_key(match.group(1)) or _dedupe_key(story.title)
    return _dedupe_key(story.title)


def _event_key(story: EntertainmentStory) -> str:
    if (
        _is_preconfirmed(story)
        or _title_reports_death(story.title)
        or re.search(r"(?i)\bmourns?\b", story.title)
        or is_death_obituary_or_mourning(story)
    ):
        return "death:" + _death_cluster_key(story)
    name = _movie_name(story.title)
    if name:
        return "movie:" + _dedupe_key(name)
    return "title:" + _dedupe_key(story.title)


def _skip_reason(story: EntertainmentStory) -> str:
    blob = f"{story.title} {story.summary}"
    if not is_morning_safe(story.title, story.summary):
        return "not morning-safe"
    if _is_review_item(story):
        return "review item"
    if _SPEC_RE.search(blob):
        return "spec-script sale"
    if _WRITERS_LAB_RE.search(blob):
        return "writers lab"
    if _CAST_LIST_RE.search(blob):
        return "cast list"
    if _is_unlistenable(story):
        return "industry item"
    if _OLD_DEATH_MENTION_RE.search(story.title):
        return "old death mention, not breaking"
    return ""


def _upcoming_weekday(now: datetime, weekday: int) -> datetime:
    delta = (weekday - now.weekday()) % 7
    return (now + timedelta(days=delta)).replace(hour=12, minute=0, second=0, microsecond=0)


def _parse_when_date(when: str, now: datetime) -> datetime | None:
    text = _clean_text(when).lower()
    if not text:
        return None
    weekdays = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }
    for name, index in weekdays.items():
        if re.search(rf"\b{name}\b", text):
            found = _upcoming_weekday(now, index)
            if "next" in text and found.date() == now.date():
                return found + timedelta(days=7)
            return found
    match = re.search(
        r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2})(?:\s*,\s*(\d{4}))?\b",
        text,
    )
    if not match:
        return None
    month = {
        "jan": 1,
        "feb": 2,
        "mar": 3,
        "apr": 4,
        "may": 5,
        "jun": 6,
        "jul": 7,
        "aug": 8,
        "sep": 9,
        "oct": 10,
        "nov": 11,
        "dec": 12,
    }[match.group(1)]
    day = int(match.group(2))
    year = int(match.group(3)) if match.group(3) else now.year
    try:
        found = datetime(year, month, day, 12, tzinfo=timezone.utc)
    except ValueError:
        return None
    if match.group(3) is None and found.date() < now.date():
        return None
    return found


def _opening_at(story: EntertainmentStory, now: datetime) -> datetime | None:
    when = _theater_when(f"{story.title} {story.summary}")
    if not when:
        return None
    return _parse_when_date(when, now)


def _opens_within_week(story: EntertainmentStory, now: datetime) -> bool:
    opening = _opening_at(story, now)
    if opening is None:
        return False
    delta = (opening.date() - now.date()).days
    return 0 <= delta <= OPENING_DAYS


def _opens_this_friday(story: EntertainmentStory, now: datetime) -> bool:
    opening = _opening_at(story, now)
    if opening is None:
        return False
    return opening.date() == _upcoming_weekday(now, 4).date()


def _is_breaking_news(story: EntertainmentStory) -> bool:
    if _is_movie_item(story) or _is_review_item(story) or _is_unlistenable(story):
        return False
    if is_death_obituary_or_mourning(story) or _title_reports_death(story.title):
        return False
    if _BOX_OFFICE_RE.search(story.title):
        return False
    return _BREAKING_NEWS_RE.search(f"{story.title} {story.summary}") is not None


def _fill_tier(story: EntertainmentStory) -> int:
    if _is_movie_item(story):
        return 0
    blob = f"{story.title} {story.summary}"
    if _STREAMING_RE.search(blob):
        return 1
    if _BOX_OFFICE_RE.search(blob):
        return 2
    return 3


def _news_slot(story: EntertainmentStory, now: datetime) -> str:
    if _is_movie_item(story) or _opens_within_week(story, now):
        return SLOT_FILM_NEWS
    if story.source_id == "deadline" or story.kind == "entertainment_news":
        return SLOT_DEADLINE
    return SLOT_EXTRA


def _merge_death(announcements: list[EntertainmentStory], outlets: list[str]) -> EntertainmentStory:
    def sort_key(story: EntertainmentStory) -> tuple[int, datetime, int]:
        graphic = 1 if _SENSITIVE_CAUSE_RE.search(f"{story.title} {story.summary}") else 0
        published = _as_utc(story.published) if story.published else _FAR_FUTURE
        return (graphic, published, -len(story.summary or ""))

    best = min(announcements, key=sort_key)
    return replace(best, confirmed_outlets=tuple(outlets), slot=SLOT_TMZ)


def _verify_death_cluster(
    group: list[EntertainmentStory],
    now: datetime,
) -> tuple[EntertainmentStory | None, str]:
    preconfirmed = [story for story in group if _is_preconfirmed(story)]
    if preconfirmed:
        story = preconfirmed[0]
        age = _age_hours(story.published, now)
        if age is not None and age > DEATH_BREAKING_HOURS:
            return None, "old obituary, not breaking"
        return _with_slot(story, SLOT_TMZ), "confirmed death leads"

    announcements = [
        story
        for story in group
        if _title_reports_death(story.title) and not _is_rumor(story) and not _is_social(story)
    ]
    reputable = [story for story in announcements if _is_reputable(story)]
    outlets: list[str] = []
    for story in reputable:
        key = _outlet_key(story)
        if key and key not in outlets:
            outlets.append(key)
    if len(outlets) < 2:
        if any(_is_social(story) for story in group) and len(outlets) < 1:
            return None, "social post, death not verified"
        if any(_is_rumor(story) for story in group) and len(outlets) < 2:
            return None, "rumor, death not verified"
        if len(outlets) == 1:
            return None, "single source, death not verified"
        return None, "death not verified"

    dated = [story.published for story in reputable if story.published is not None]
    if not dated:
        return None, "death has no publication date"
    newest = max(_as_utc(moment) for moment in dated)
    oldest = min(_as_utc(moment) for moment in dated)
    if (now - newest).total_seconds() > DEATH_BREAKING_HOURS * 3600:
        return None, "old obituary, not breaking"
    if (newest - oldest).total_seconds() > DEATH_BREAKING_HOURS * 3600:
        return None, "old obituary, not breaking"
    return _merge_death(reputable, outlets), "confirmed by " + " and ".join(outlets)


def _emit_selection_log(log: list[dict[str, str]]) -> None:
    selected = sum(1 for row in log if row["status"] == "selected")
    rejected = sum(1 for row in log if row["status"] == "rejected")
    merged = sum(1 for row in log if row["status"] == "merged")
    LOGGER.info(
        "Entertainment selection: %s selected, %s rejected, %s merged",
        selected,
        rejected,
        merged,
    )
    for row in log:
        if row["status"] == "considered":
            continue
        LOGGER.info(
            "entertainment %s | %s | %s | %s",
            row["status"],
            row["source"],
            row["title"],
            row["reason"],
        )


def rank_entertainment_stories(
    stories: list[EntertainmentStory],
    *,
    limit: int = ENTERTAINMENT_STORY_COUNT,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Collect a pool, then rank it. The log stays out of the spoken script.

    Deaths need two independent reputable sources and a recent publication
    date. Everything else is ranked: breaking headlines, movies opening
    within seven days (Friday first), then streaming, box office, and other
    entertainment to fill.
    """
    clock = _as_utc(now)
    log: list[dict[str, str]] = []
    resolved: set[int] = set()

    def note(story: EntertainmentStory, status: str, reason: str) -> None:
        log.append(
            {
                "title": story.title,
                "source": _source_label(story),
                "status": status,
                "reason": reason,
            }
        )
        if status != "considered":
            resolved.add(id(story))

    for story in stories:
        note(story, "considered", "in the pool")

    if limit < 1:
        for story in stories:
            note(story, "rejected", "no stories requested")
        _emit_selection_log(log)
        return {"stories": [], "log": log}

    usable: list[EntertainmentStory] = []
    for story in stories:
        reason = _skip_reason(story)
        if reason:
            note(story, "rejected", reason)
            continue
        usable.append(story)

    clusters: dict[str, list[EntertainmentStory]] = {}
    rest: list[EntertainmentStory] = []
    for story in usable:
        death_related = (
            _is_preconfirmed(story)
            or _title_reports_death(story.title)
            or re.search(r"(?i)\bmourns?\b", _clean_text(story.title)) is not None
            or is_death_obituary_or_mourning(story)
        )
        if death_related:
            clusters.setdefault(_death_cluster_key(story), []).append(story)
        else:
            rest.append(story)

    verified: list[EntertainmentStory] = []
    for group in clusters.values():
        merged, reason = _verify_death_cluster(group, clock)
        if merged is None:
            for story in group:
                note(story, "rejected", reason)
            continue
        for story in group:
            note(story, "merged", reason)
        verified.append(merged)

    kept: dict[str, EntertainmentStory] = {}
    for story in rest:
        key = _event_key(story)
        current = kept.get(key)
        if current is None:
            kept[key] = story
            continue
        if _recency(story, clock) + 0.01 < _recency(current, clock):
            note(current, "merged", "duplicate headline")
            kept[key] = story
        else:
            note(story, "merged", "duplicate headline")

    openings: list[EntertainmentStory] = []
    breaking: list[EntertainmentStory] = []
    fills: list[EntertainmentStory] = []
    for story in kept.values():
        if _opens_within_week(story, clock):
            openings.append(story)
        elif (age := _age_hours(story.published, clock)) is not None and age > FRESH_HOURS:
            note(story, "rejected", "older than 24 hours")
        elif _is_breaking_news(story):
            breaking.append(story)
        elif _is_movie_item(story) or _is_fill_entertainment(story):
            fills.append(story)
        else:
            note(story, "rejected", "not a headline, opening, or fill")

    verified.sort(key=lambda story: _recency(story, clock))
    breaking.sort(key=lambda story: _recency(story, clock))
    openings.sort(
        key=lambda story: (
            0 if _opens_this_friday(story, clock) else 1,
            _opening_at(story, clock) or _FAR_FUTURE,
            _recency(story, clock),
        )
    )
    fills.sort(key=lambda story: (_fill_tier(story), _recency(story, clock)))

    chosen: list[EntertainmentStory] = []
    chosen_keys: set[str] = set()

    def take(story: EntertainmentStory, reason: str, slot: str) -> bool:
        key = _event_key(story)
        if not key or key in chosen_keys or len(chosen) >= limit:
            return False
        chosen_keys.add(key)
        chosen.append(_with_slot(story, slot))
        note(story, "selected", reason)
        return True

    verified.sort(key=lambda story: (-len(story.confirmed_outlets), _recency(story, clock)))
    reserve_for_other_news = bool(openings or breaking)
    death_budget = len(verified)
    if reserve_for_other_news:
        death_budget = min(death_budget, 2)
    death_budget = min(death_budget, limit)
    for story in verified[:death_budget]:
        take(story, "confirmed death leads", SLOT_TMZ)

    deaths_taken = len(chosen)
    if openings and (breaking or deaths_taken):
        opening_slots = min(2, len(openings), max(0, limit - deaths_taken))
        headline_slots = min(len(breaking), max(0, 2 - deaths_taken))
        room = max(0, limit - deaths_taken)
        if headline_slots + opening_slots > room:
            headline_slots = min(headline_slots, max(0, room - opening_slots))
    elif openings:
        opening_slots = min(len(openings), max(0, limit - deaths_taken))
        headline_slots = 0
    else:
        opening_slots = 0
        headline_slots = min(len(breaking), max(0, limit - deaths_taken))

    for story in breaking[:headline_slots]:
        take(story, "major headline", _news_slot(story, clock))
    opening_taken = 0
    for story in openings:
        if opening_taken >= opening_slots:
            break
        if take(story, "opens within seven days", SLOT_FILM_NEWS):
            opening_taken += 1
    for story in breaking[headline_slots:]:
        take(story, "major headline", _news_slot(story, clock))
    for story in openings:
        take(story, "opens within seven days", SLOT_FILM_NEWS)
    for story in verified[death_budget:]:
        take(story, "confirmed death", SLOT_TMZ)
    for story in fills:
        take(story, "fill", _news_slot(story, clock))

    for story in stories:
        if id(story) not in resolved:
            note(story, "rejected", "ranked below the four stories")

    _emit_selection_log(log)
    return {"stories": chosen, "log": log}


def select_entertainment_stories(
    stories: list[EntertainmentStory],
    *,
    limit: int = ENTERTAINMENT_STORY_COUNT,
    now: datetime | None = None,
) -> list[EntertainmentStory]:
    """Up to four ranked stories. A verified death leads."""
    return rank_entertainment_stories(stories, limit=limit, now=now)["stories"]


def _is_google_news_url(url: str) -> bool:
    return "news.google.com/rss/search" in str(url or "").lower()


def _google_source(url: str) -> dict[str, str]:
    return {
        "id": "google_news",
        "name": "Google News",
        "kind": "search",
        "slot": "",
        "url": url,
    }


def collect_entertainment_report(
    xml_by_url: dict[str, str | BaseException] | None = None,
    *,
    fetch: bool = False,
    timeout: float = 12.0,
    limit: int = ENTERTAINMENT_STORY_COUNT,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Parse every feed item plus supplemental search, then rank.

    Pass `xml_by_url` for offline fixtures. Set `fetch` to download the
    three station feeds and the Google News searches. Each request fails
    on its own. The returned log is for the operator, not the script.
    """
    payloads: dict[str, str | BaseException] = {}
    if xml_by_url is not None:
        payloads = dict(xml_by_url)
    elif fetch:
        targets = list(ENTERTAINMENT_SOURCES) + [
            _google_source(google_news_rss_url(query)) for query in ENTERTAINMENT_SEARCH_QUERIES
        ]
        for source in targets:
            url = source["url"]
            try:
                payloads[url] = _fetch_feed_xml(url, timeout=timeout)
            except (URLError, OSError, TimeoutError, ValueError) as exc:
                payloads[url] = exc

    stories: list[EntertainmentStory] = []
    seen_urls: set[str] = set()
    for source in ENTERTAINMENT_SOURCES:
        seen_urls.add(source["url"])
        payload = payloads.get(source["url"])
        if payload is None or isinstance(payload, BaseException):
            continue
        stories.extend(parse_feed_xml(str(payload), source))
    for url, payload in payloads.items():
        if url in seen_urls or payload is None or isinstance(payload, BaseException):
            continue
        if not _is_google_news_url(url):
            continue
        stories.extend(parse_feed_xml(str(payload), _google_source(url)))
    return rank_entertainment_stories(stories, limit=limit, now=now)


def collect_entertainment_stories(
    xml_by_url: dict[str, str | BaseException] | None = None,
    *,
    fetch: bool = False,
    timeout: float = 12.0,
    limit: int = ENTERTAINMENT_STORY_COUNT,
    now: datetime | None = None,
) -> list[EntertainmentStory]:
    """Gather ranked entertainment stories. Each feed fails on its own.

    Pass `xml_by_url` for offline fixtures. Set `fetch` to download live feeds.
    """
    return collect_entertainment_report(
        xml_by_url,
        fetch=fetch,
        timeout=timeout,
        limit=limit,
        now=now,
    )["stories"]


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
# A headline that is itself a death, obituary, or mourning item.
# "Killed it" is slang and is removed before this runs. A movie title word
# inside a sale blurb does not count: only the headline is checked.
_DEATH_ITEM_RE = re.compile(
    r"(?i)\b(?:"
    r"obituar(?:y|ies)|"
    r"in memoriam|"
    r"in mourning|"
    r"mourn(?:s|ed|ing)|"
    r"pass(?:es|ed) away|"
    r"passing of|"
    r"dies|died|"
    r"dead at|"
    r"found dead|"
    r"death of|"
    r"(?:'s|’s)\s+death"
    r")\b"
)


def _death_not_in_headline(sentence: str, title: str) -> bool:
    """A blurb must not declare a death the headline never reported."""
    if not _DEATH_CLAIM_RE.search(sentence or ""):
        return False
    return _HEADLINE_DEATH_RE.search(title or "") is None


def is_death_obituary_or_mourning(story: EntertainmentStory) -> bool:
    """True when the headline is a death, obituary, or mourning item.

    A blurb that adds a death the headline never reported does not count.
    A "weeks after" follow-up is not treated as a new death.
    """
    title = _KILLED_IT_RE.sub(" ", _clean_text(story.title))
    if _OLD_DEATH_MENTION_RE.search(title):
        return False
    return _DEATH_ITEM_RE.search(title) is not None or _title_reports_death(title)


def stories_need_straight_open(stories: list[EntertainmentStory]) -> bool:
    """Any death, obituary, or mourning story straightens the whole open."""
    return any(
        is_death_obituary_or_mourning(story)
        for story in list(stories or [])[:ENTERTAINMENT_STORY_COUNT]
    )


def michael_open_lines(stories: list[EntertainmentStory] | None = None) -> list[str]:
    """Death day: the straight open only. Normal day: that line, then one beat."""
    if stories_need_straight_open(list(stories or [])):
        return [MICHAEL_STRAIGHT_OPEN]
    return [MICHAEL_STRAIGHT_OPEN, MICHAEL_BEAT]


def _story_sentences(text: str, limit: int = 2) -> list[str]:
    kept: list[str] = []
    for sentence in _take_sentences(text, 8):
        if _is_arrival_only(sentence) or _FORBIDDEN_SPOKEN_RE.search(sentence):
            continue
        if re.match(r"(?i)\s*spoiler alert\b", sentence):
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
        if _SENSITIVE_CAUSE_RE.search(sentence):
            continue
        kept.append(sentence)
    if kept:
        return " ".join(kept)
    return _headline_sentence(story.title)


def spoken_story(story: EntertainmentStory) -> str:
    """On-air beat for one slot. Outlet names are not added."""
    if _is_unlistenable(story):
        return ""
    if is_death_obituary_or_mourning(story):
        spoken = _spoken_general(story)
    elif (
        story.slot == SLOT_FILM_NEWS
        or story.kind in {"film_news", "film"}
        or story.source_id == "variety_film"
        or _is_movie_item(story)
    ):
        spoken = _spoken_film_news(story)
    else:
        spoken = _spoken_general(story)
    if _FORBIDDEN_SPOKEN_RE.search(spoken):
        kept = [sentence for sentence in _take_sentences(spoken, 8) if not _FORBIDDEN_SPOKEN_RE.search(sentence)]
        spoken = " ".join(kept)
    if story.outlet:
        spoken = _strip_publisher_suffix(spoken.rstrip("."), story.outlet)
        if spoken and spoken[-1:] not in ".!?":
            spoken += "."
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
    selected = list(stories or [])[:ENTERTAINMENT_STORY_COUNT]
    lines = michael_open_lines(selected)
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


def _prompt_label(story: EntertainmentStory) -> str:
    if is_death_obituary_or_mourning(story):
        return "Death, obituary, or mourning item. It leads. Read it straight. No joke."
    if _is_movie_item(story) or story.slot == SLOT_FILM_NEWS or story.kind in {"film_news", "film"}:
        return (
            "New movie. Its own short paragraph: a hook, the title, "
            "the opening day only if supplied, the stars only if supplied, and what it is about."
        )
    return "Entertainment item in one or two plain sentences."


def format_entertainment_prompt(
    stories: list[EntertainmentStory],
    *,
    rules: str = DEFAULT_ENTERTAINMENT_REPORT_RULES,
) -> str:
    """Local-AI prompt: sports-style rules plus only the supplied stories."""
    selected = list(stories)[:ENTERTAINMENT_STORY_COUNT]
    lines = [rules.strip(), "", "SUPPLIED STORIES:"]
    filled = 0
    if not selected:
        lines.append("1. (skipped — do not invent this slot.)")
    for index, story in enumerate(selected, start=1):
        spoken = spoken_story(story)
        if not spoken:
            lines.append(f"{index}. {_prompt_label(story)} (skipped — do not invent this slot.)")
            continue
        filled += 1
        lines.append(f"{index}. {_prompt_label(story)} {spoken}")
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
        "Short sentences. No bullet points. "
        "When four stories are supplied, aim for about 350 to 450 words. "
        "Shorter if fewer stories qualify. Use only the supplied facts."
    )
    if stories_need_straight_open(list(stories)):
        lines.append(
            "A supplied story is a death, obituary, or mourning item. "
            'Open with exactly "Thanks, Dave. Michael G here with the entertainment report." '
            "Do not add a comical beat. "
            "No coffee, no classic rock, no popcorn joke, no grandkids joke, no dog joke, and no husband joke. "
            "Do not follow the normal-day conversational beat. This open has no joke. "
            "The death story itself stays respectful. "
            "Not sarcastic about death or illness."
        )
    else:
        lines.append(
            'Open with "Thanks, Dave. Michael G here with the entertainment report." '
            "Then one short conversational beat that sounds like him talking, using coffee or classic rock. "
            "One sentence. Not a disconnected gag. "
            "One short beat. Not a biography. Do not read the degrees or the universities. "
            "Not the same sentence every day. "
            "Not sarcastic about death or illness. Not a long monologue. "
            "Do not invent a movie title or a person's death for the joke."
        )
    lines.append(
        "Thank Dave. Do not thank Mo at the start. Dave is the person he thanks. "
        "After the stories, turn the show over to DJ Mo."
    )
    lines.append(f"DJ Mo's next line is: {MO_THANKS}")
    return "\n".join(lines)


def mo_thanks_line(thanks: str = "") -> str:
    """Mo thanks Michael. A bare thanks picks up the weekday 7:15 mention."""
    text = _WS_RE.sub(" ", str(thanks or "")).strip()
    if not text or re.fullmatch(r"(?i)thanks,?\s+michael\s+g\.?", text):
        return MO_THANKS
    if re.search(r"(?i)\bmichael\s+g\b", text) and re.search(r"(?i)\bthanks\b", text):
        return text
    return MO_THANKS


def build_morning_flow(
    stories: list[EntertainmentStory] | None = None,
    *,
    sports_close: str = "",
    mo_thanks: str = "",
    rules: str = DEFAULT_ENTERTAINMENT_REPORT_RULES,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Morning order after the hard-news block: Dave, Michael G, then DJ Mo."""
    ranked = rank_entertainment_stories(list(stories or []), now=now)
    selected = ranked["stories"]
    dave_close = sports_close_hands_to_michael(sports_close)
    michael_script = michael_g_script(selected)
    thanks = mo_thanks_line(mo_thanks)
    return {
        "order": ["news", "dave_sports", "michael_g_entertainment", "mo_thanks"],
        "story_count": len(selected),
        "stories": selected,
        "selection_log": ranked["log"],
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
        *michael_open_lines([]),
        "[Four stories when the feeds supply them. A death leads. Other stories are new movies when the feeds have them. Do not invent stories in this preview.]",
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
    has_straight_death_open = (
        "whole open is straight" in lowered_rules
        and "no coffee" in lowered_rules
        and "no classic rock" in lowered_rules
    )
    has_conversational_beat = (
        "coffee or classic rock" in lowered_rules
        and "not a disconnected gag" in lowered_rules
        and "does not read his biography" in lowered_rules
        and "not the same sentence every day" in lowered_rules
    )
    has_locked_handoff = (
        "does not thank mo at the start" in lowered_rules
        and "dave is the person he thanks" in lowered_rules
        and "turns it over to mo" in lowered_rules
        and "weekdays at 7:15" in lowered_rules
    )
    has_verified_deaths = "two independent" in lowered_rules and "350" in lowered_rules
    if (
        not has_movie_shape
        or mentions_reviews_feed
        or not has_intro
        or not has_straight_death_open
        or not has_conversational_beat
        or not has_locked_handoff
        or not has_verified_deaths
    ):
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
    report = collect_entertainment_report(fetch=True)
    package = build_morning_flow(report["stories"])
    # The collect log still has the stories that were rejected before the handoff.
    package["selection_log"] = report["log"]
    print(package["script"])
    print()
    print(package["michael_g_prompt"])
    logging.basicConfig(level=logging.INFO)
    _emit_selection_log(report["log"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

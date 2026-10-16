"""Bailey's midday Hidden Boston + Good News Wag segment.

This lived on the Office PC news engine (D:\\MPR\\Engines\\News\\Powershell\\RunNews.ps1),
not in mos-radio git. When midday was rewritten to insert Michael G, Studio kept only
Bailey's close line. This module restores the spoken midday page:

1. Hidden Boston restaurant / food spots (favorites feed, rotated)
2. Bailey's Good News Wag lead-in
3. Heartwarming animal stories from the Good News Network feeds
4. Verbatim Love you, bye close

Michael G stays at four entertainment stories. Morning desk is unchanged.
"""

from __future__ import annotations

import html
import logging
import random
import re
from dataclasses import dataclass
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

logger = logging.getLogger("moplace.studio.bailey")

HIDDEN_BOSTON_URL = "https://www.hiddenboston.com/favorites.xml"
GOOD_NEWS_FEEDS: tuple[tuple[str, str], ...] = (
    ("GOOD NEWS NETWORK DOGS", "https://www.goodnewsnetwork.org/tag/dogs/feed/"),
    (
        "GOOD NEWS NETWORK ANIMALS",
        "https://www.goodnewsnetwork.org/category/news/animals/feed/",
    ),
    ("DOG WITH BLOG", "https://dogwithblog.in/feed/"),
)

HIDDEN_BOSTON_POOL = 3
HIDDEN_BOSTON_SPEAK = 2
ANIMAL_PER_FEED = 1

BAILEY_HIDDEN_BOSTON_OPEN = "Here is what's happening from Hidden Boston."
BAILEY_GOOD_NEWS_WAG = (
    "Well, that's a little look at what's hiding around Boston! "
    "You never know what interesting things you'll discover right in your own backyard. "
    "Now, you know I have a soft spot for our four-legged friends, so let's switch gears "
    "to something that always puts a little wag in my tail. "
    "It's time for Bailey's Good News Wag! "
    "We're rounding up some heartwarming animal stories, happy tails, and good news that'll "
    "remind you there's still plenty of kindness in this world. "
    "So, let's see who's making the world a little brighter today!"
)
BAILEY_LAST_LINE = (
    "Alright, everyone, that's gonna do it for me today! "
    "Thanks for spending a little time with me here at Mo's Place Radio. "
    "Keep smiling, be kind to one another, and if you see a dog today, give that good boy "
    "or girl a little extra love from Bailey! "
    "I'll catch you next time with more fun, more music, and more reasons to wag that tail. "
    "Love you, bye!"
)

_USER_AGENT = "MoPlaceStudio/2.0"
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_GNN_SKIP_CAT = re.compile(
    r"(?i)\b(celebrities|celebrity|entertainment|music|movies|film|television|concerts?|musician)\b"
)
_GNN_SKIP_TEXT = re.compile(
    r"(?i)\b(kelly clarkson|dolly parton|album|concert|box office|musician|celebrity|celebrities|"
    r"netflix|grammy|oscar|emmy|music feud|tv show|television series)\b"
)
_GNN_HISTORY = re.compile(r"(?i)this day in history|on this day|^good news in history\b")
_GNN_ANIMAL_CAT = re.compile(r"(?i)\b(animals?|wildlife|pets?|dogs?|cats?|birds?|reptiles?)\b")
_GNN_ANIMAL_TITLE = re.compile(
    r"(?i)\b(dogs?|puppies|puppy|cats?|kittens?|kitten|birds?|owls?|tortoises?|turtles?|"
    r"gorillas?|gazelles?|horses?|whales?|dolphins?|elephants?|pandas?|otters?|"
    r"sloth bears?|gliders?|wildlife)\b"
)


@dataclass(frozen=True)
class BaileyStory:
    title: str
    summary: str
    source_id: str
    kind: str  # "hidden_boston" or "animal"


def _clean(value: str | None) -> str:
    text = _TAG_RE.sub(" ", html.unescape(str(value or "")))
    text = (
        text.replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2013", "-")
        .replace("\u2014", "-")
    )
    return _WS_RE.sub(" ", text).strip(" -")


def _wag_speakable(value: str | None) -> str:
    text = _clean(value)
    text = re.sub(r"\s*The post .+ appeared first on .+$", "", text)
    text = re.sub(r"\s*\[\s*(?:\.\.\.|\u2026)\s*\]\s*", " ", text)
    return _WS_RE.sub(" ", text).strip(" -")


def _fetch_xml(url: str, *, timeout: float = 12.0) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": _USER_AGENT,
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def _gnn_is_entertainment(title: str, summary: str, cats: list[str]) -> bool:
    blob = " ".join([title, summary, *cats])
    if any(_GNN_SKIP_CAT.search(c or "") for c in cats):
        return True
    return bool(_GNN_SKIP_TEXT.search(blob))


def _gnn_is_history(title: str, cats: list[str]) -> bool:
    if _GNN_HISTORY.search(title or ""):
        return True
    return any(_GNN_HISTORY.search(c or "") for c in cats)


def _gnn_is_animal(title: str, summary: str, cats: list[str]) -> bool:
    if any(_GNN_ANIMAL_CAT.search(c or "") for c in cats):
        return True
    return bool(_GNN_ANIMAL_TITLE.search(title or ""))


def parse_hidden_boston_xml(xml_text: str) -> list[BaileyStory]:
    """Every place in the favorites feed. Caller rotates; do not invent spots."""
    root = ET.fromstring(xml_text)
    stories: list[BaileyStory] = []
    seen: set[str] = set()
    for item in root.findall("./channel/item"):
        title = _clean(item.findtext("title"))
        if not title:
            continue
        key = title.casefold()
        if key in seen:
            continue
        seen.add(key)
        stories.append(
            BaileyStory(
                title=title,
                summary=_clean(item.findtext("description")),
                source_id="hidden_boston",
                kind="hidden_boston",
            )
        )
    return stories


def pick_hidden_boston(
    places: list[BaileyStory],
    *,
    pool: int = HIDDEN_BOSTON_POOL,
    speak: int = HIDDEN_BOSTON_SPEAK,
    rng: random.Random | None = None,
) -> list[BaileyStory]:
    """Rotate through the favorites pool so Bailey does not repeat the same few."""
    if not places:
        return []
    picker = rng or random.Random()
    chosen_pool = picker.sample(places, k=min(max(1, pool), len(places)))
    return chosen_pool[: max(1, min(speak, len(chosen_pool)))]


def parse_animal_feed_xml(xml_text: str, *, source_id: str, limit: int = ANIMAL_PER_FEED) -> list[BaileyStory]:
    """Usable Good News Wag items: animal-friendly, not entertainment or history."""
    root = ET.fromstring(xml_text)
    stories: list[BaileyStory] = []
    seen: set[str] = set()
    for item in root.findall("./channel/item"):
        title = _wag_speakable(item.findtext("title"))
        summary = _wag_speakable(item.findtext("description"))
        if len(summary) > 700:
            summary = summary[:700].rsplit(" ", 1)[0].strip()
        cats = [
            _clean(c.text)
            for c in item.findall("category")
            if _clean(getattr(c, "text", None))
        ]
        if not title or not summary:
            continue
        key = title.casefold()
        if key in seen:
            continue
        if _gnn_is_history(title, cats) or _gnn_is_entertainment(title, summary, cats):
            continue
        # Prefer animal-tagged items; Dog With Blog is already animal-themed.
        if source_id != "dog_with_blog" and not _gnn_is_animal(title, summary, cats):
            continue
        seen.add(key)
        stories.append(
            BaileyStory(
                title=title,
                summary=summary,
                source_id=source_id,
                kind="animal",
            )
        )
        if len(stories) >= max(1, limit):
            break
    return stories


def _spoken_hidden_boston(story: BaileyStory) -> str:
    title = story.title.strip()
    summary = story.summary.strip()
    if summary:
        if summary[-1:] not in ".!?":
            summary += "."
        return f"{title}. {summary}"
    if title[-1:] not in ".!?":
        title += "."
    return title


def _spoken_animal(story: BaileyStory) -> str:
    title = story.title.strip().rstrip(".")
    summary = story.summary.strip()
    if summary:
        if summary[-1:] not in ".!?":
            summary += "."
        # Avoid reading the headline twice when the summary already opens with it.
        if summary.casefold().startswith(title.casefold()):
            return summary
        return f"{title}. {summary}"
    return f"{title}."


def bailey_midday_script(
    *,
    hidden_boston: list[BaileyStory] | None = None,
    animals: list[BaileyStory] | None = None,
) -> str:
    """Spoken Bailey midday page. Never invents restaurants or animal stories."""
    food = [s for s in list(hidden_boston or []) if s.kind == "hidden_boston"]
    wag = [s for s in list(animals or []) if s.kind == "animal"]
    parts: list[str] = []

    if food:
        parts.append(BAILEY_HIDDEN_BOSTON_OPEN)
        for story in food[:HIDDEN_BOSTON_SPEAK]:
            spoken = _spoken_hidden_boston(story)
            if spoken:
                parts.append(spoken)

    if wag:
        parts.append(BAILEY_GOOD_NEWS_WAG)
        for story in wag:
            spoken = _spoken_animal(story)
            if spoken:
                parts.append(spoken)
    elif food:
        # Food ran; keep the Wag bridge so midday still hands into her close warmly.
        parts.append(BAILEY_GOOD_NEWS_WAG)

    parts.append(BAILEY_LAST_LINE)
    return "\n\n".join(parts)


def collect_bailey_report(
    xml_by_url: dict[str, str | BaseException] | None = None,
    *,
    fetch: bool = False,
    timeout: float = 12.0,
    rng: random.Random | None = None,
) -> dict[str, Any]:
    """Gather Hidden Boston + animal stories. Each feed fails on its own."""
    payloads: dict[str, str | BaseException] = {}
    targets = [("hidden_boston", HIDDEN_BOSTON_URL)] + [
        (name.casefold().replace(" ", "_"), url) for name, url in GOOD_NEWS_FEEDS
    ]
    if xml_by_url is not None:
        payloads = dict(xml_by_url)
    elif fetch:
        for _source_id, url in targets:
            try:
                payloads[url] = _fetch_xml(url, timeout=timeout)
            except (URLError, OSError, TimeoutError, ValueError) as exc:
                payloads[url] = exc
                logger.warning("Bailey feed skipped (%s): %s", url, exc)

    places: list[BaileyStory] = []
    hb_payload = payloads.get(HIDDEN_BOSTON_URL)
    if isinstance(hb_payload, str):
        try:
            places = parse_hidden_boston_xml(hb_payload)
        except ET.ParseError as exc:
            logger.warning("Hidden Boston parse failed: %s", exc)

    food = pick_hidden_boston(places, rng=rng)

    animals: list[BaileyStory] = []
    seen_titles: set[str] = set()
    for name, url in GOOD_NEWS_FEEDS:
        source_id = name.casefold().replace(" ", "_")
        payload = payloads.get(url)
        if not isinstance(payload, str):
            continue
        try:
            rows = parse_animal_feed_xml(payload, source_id=source_id, limit=ANIMAL_PER_FEED)
        except ET.ParseError as exc:
            logger.warning("Animal feed parse failed (%s): %s", name, exc)
            continue
        for row in rows:
            key = row.title.casefold()
            if key in seen_titles:
                continue
            seen_titles.add(key)
            animals.append(row)

    script = bailey_midday_script(hidden_boston=food, animals=animals)
    return {
        "hidden_boston": food,
        "animals": animals,
        "script": script,
        "has_content": bool(food or animals),
    }


def bailey_feed_urls() -> list[str]:
    return [HIDDEN_BOSTON_URL, *[url for _name, url in GOOD_NEWS_FEEDS]]

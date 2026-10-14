"""Dave's sports copy for the morning newscast.

Speak a team only when it plays or when supplied news is real.
Patriots, Red Sox, Celtics, Bruins, and Lowell Spinners stay silent
when they have no game and no news. Never invent a score, an opponent,
or an idle-team line.

Lowell Spinners games come from the schedule RSS. MLB playoff games and
news come from the Fox Sports MLB RSS. Other major headlines come from
the general Fox Sports RSS, skipping items the MLB feed already covered.
A down feed is skipped.
"""

from __future__ import annotations

import html
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable
from urllib.error import URLError
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

logger = logging.getLogger("moplace.studio.sports")

FOX_MLB_RSS_URL = (
    "https://api.foxsports.com/v2/content/optimized-rss"
    "?partnerKey=MB0Wehpmuj2lUhuRhQaafhBjAJqaPU244mlTDK1i"
    "&size=30&tags=fs%2Fmlb"
    "&_hp5_cdc=479232849%3B2254849013005665%3B6960053605144110%3B1791964238458%3B"
)
FOX_SPORTS_RSS_URL = (
    "https://api.foxsports.com/v2/content/optimized-rss"
    "?partnerKey=MB0Wehpmuj2lUhuRhQaafhBjAJqaPU244mlTDK1i"
    "&size=30"
    "&_hp5_cdc=479232849%3B2254849013005665%3B6960053605144110%3B1791964238458%3B"
)
SPINNERS_SCHEDULE_RSS_URL = "https://www.lowellspinners.com/sports/bsb/2025-26/schedule?print=rss"

STATION_TZ = ZoneInfo("America/New_York")
_USER_AGENT = "MoPlaceStudio/2.0"
_PLAYOFF_LIMIT = 3
_HEADLINE_LIMIT = 3

# Station order. Spinners schedule lines are built separately.
_TEAM_ORDER = ("Patriots", "Red Sox", "Celtics", "Bruins", "Lowell Spinners")
_TEAM_KEYS = (
    ("patriots", "Patriots"),
    ("red sox", "Red Sox"),
    ("celtics", "Celtics"),
    ("bruins", "Bruins"),
    ("lowell spinners", "Lowell Spinners"),
    ("spinners", "Lowell Spinners"),
)

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_IDLE_RE = re.compile(
    r"(?i)\b("
    r"not playing|no games?|nothing to report|nothing to say|"
    r"are idle|is idle|have no game|has no game|"
    r"aren'?t playing|isn'?t playing|"
    r"off today|don'?t play|do not play|"
    r"no news|not scheduled|nothing on the|day off"
    r")\b"
)
_NEWS_SIGNAL_RE = re.compile(
    r"(?i)\b("
    r"vs\.?|versus|host|against|final|won|win|lost|beat|defeated|"
    r"signed|injured|injury|trade|traded|playoff|postseason|series|"
    r"next game"
    r")\b|\d+\s*[-–]\s*\d+"
)
_PLAYOFF_RE = re.compile(
    r"(?i)\b("
    r"playoffs?|postseason|world series|"
    r"alcs|nlcs|alds|nlds|"
    r"wild[\s-]?card|"
    r"division series|championship series|"
    r"league championship|league division"
    r")\b"
)
_PROMO_RE = re.compile(
    r"(?i)\b("
    r"promo code|promocode|"
    r"fanduel|kalshi|polymarket|underdog|draftkings|betmgm|caesars|"
    r"sign up|signing up|\bodds\b|"
    r"favorite\s+'?dogs|best bets"
    r")\b"
)
# UCLA and other college nicknames are not the NHL Bruins.
_NOT_BOSTON_BRUINS_RE = re.compile(r"(?i)\b(ucla|belmont|badgers|big ten|college football)\b")
_DESC_WHEN_RE = re.compile(
    r"(?i)\bon\s+([A-Za-z]{3,9}\s+\d{1,2},\s+\d{4})(?:\s+at\s+(\d{1,2}:\d{2}\s*[AP]M))?"
)
_XML_DECL_ENCODING = re.compile(r"(<\?xml[^?]*?)\s+encoding\s*=\s*['\"][^'\"]+['\"]", re.I)
_TIME_RE = re.compile(r"(?i)\bat\s+(\d{1,2}(?::\d{2})?\s*[AP]M)\b")

SPORTS_SILENCE_RULE = (
    "Speak about the Patriots, Red Sox, Celtics, Bruins, and Lowell Spinners "
    "only when they play or when there is actual news. "
    "If a team has no game and no news, stay silent. "
    "Do not say they are not playing, that they have no game, that there is "
    "nothing to report, or that they are idle."
)
SPORTS_PLAYOFF_RULE = (
    "During the MLB postseason, include current MLB playoff games and news "
    "from the supplied Fox Sports MLB feed — series results, scores, and "
    "storylines. Prefer the freshest items. "
    "If that feed is down, skip the playoff copy and continue."
)
SPORTS_GENERAL_FOX_RULE = (
    "Include major sports headlines from the general Fox Sports feed "
    "when they are not already covered by the MLB playoff feed. "
    "If that feed is down, skip it. Do not invent scores."
)
SPORTS_SPINNERS_RULE = (
    "Lowell Spinners baseball comes from the schedule feed. "
    "Mention today's game, or the next scheduled game when the feed gives "
    "the date and opponent. "
    "If the feed is down or has no game to announce, skip them. "
    "Never invent a score or an opponent."
)
DEFAULT_SPORTS_GAME_RULES = " ".join(
    (
        SPORTS_PLAYOFF_RULE,
        SPORTS_GENERAL_FOX_RULE,
        "Always include notable athlete deaths or memorials when they appear "
        "in supplied sources.",
        SPORTS_SILENCE_RULE,
        SPORTS_SPINNERS_RULE,
        "Do not invent scores, opponents, or idle-team filler.",
    )
)
SPORTS_GENERAL_PERSONALITY = (
    "Also include major headlines from the general Fox Sports feed "
    "when they are not already covered by the MLB playoff feed."
)
SPORTS_PERSONALITY_CLAUSE = (
    "Dave reads sports only from supplied games and news. "
    "During the MLB postseason, include playoff games and news from the Fox Sports MLB feed. "
    f"{SPORTS_GENERAL_PERSONALITY} "
    "If the Patriots, Red Sox, Celtics, Bruins, or Lowell Spinners have no game and no news, stay silent."
)

# Older sports copy that told Dave to announce a next game for every idle team.
_LEGACY_NEXT_GAME_MARK = "their next game is"


def ensure_sports_personality_rules(rules: str) -> str:
    """Add Dave's silence and playoff clause once. Leave other wording in place."""
    current = _WS_RE.sub(" ", str(rules or "")).strip()
    if not current:
        return f"Lead anchor opens every newscast. {SPORTS_PERSONALITY_CLAUSE}"
    lower = current.lower()
    needs_core = "stay silent" not in lower or "playoff" not in lower
    needs_general = "general fox" not in lower
    if not needs_core and not needs_general:
        return current
    if current[-1] not in ".!?":
        current += "."
    extra = SPORTS_PERSONALITY_CLAUSE if needs_core else SPORTS_GENERAL_PERSONALITY
    return f"{current} {extra}"


def ensure_sports_game_rules(rules: str) -> str:
    """Use the silence rules. Replace the old next-game filler when Spinners are absent."""
    text = _WS_RE.sub(" ", str(rules or "")).strip()
    if not text:
        return DEFAULT_SPORTS_GAME_RULES
    lower = text.lower()
    if _LEGACY_NEXT_GAME_MARK in lower and "lowell spinners" not in lower:
        return DEFAULT_SPORTS_GAME_RULES
    extra: list[str] = []
    if not any(token in lower for token in ("mlb playoff", "mlb postseason", "world series", "playoff games")):
        extra.append(SPORTS_PLAYOFF_RULE)
    if "stay silent" not in lower and "do not say they are not playing" not in lower:
        extra.append(SPORTS_SILENCE_RULE)
    if "spinners" not in lower:
        extra.append(SPORTS_SPINNERS_RULE)
    if "general fox" not in lower:
        extra.append(SPORTS_GENERAL_FOX_RULE)
    if not extra:
        return text
    return f"{text} {' '.join(extra)}".strip()


@dataclass
class _FeedItem:
    title: str
    summary: str
    published: datetime | None


@dataclass
class _SpinnersGame:
    title: str
    opponent: str
    away: bool
    when: datetime | None
    time_label: str
    status: str

    @property
    def local_date(self) -> date | None:
        if self.when is None:
            return None
        return self.when.astimezone(STATION_TZ).date()


def _clean_text(value: str) -> str:
    text = html.unescape(str(value or ""))
    text = _TAG_RE.sub(" ", text)
    text = text.replace("\xa0", " ")
    return _WS_RE.sub(" ", text).strip()


def is_idle_filler(text: str) -> bool:
    """True when a line only says a team is off, with no game and no news."""
    cleaned = _clean_text(text)
    if not cleaned or not _IDLE_RE.search(cleaned):
        return False
    if _NEWS_SIGNAL_RE.search(cleaned):
        return False
    return True


def _local_name(tag: str) -> str:
    name = tag.rsplit("}", 1)[-1].lower()
    return name.rsplit(":", 1)[-1]


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


def _parse_description_when(description: str) -> tuple[datetime | None, str]:
    match = _DESC_WHEN_RE.search(description)
    if not match:
        time_match = _TIME_RE.search(description)
        return None, time_match.group(1).upper().replace("  ", " ") if time_match else ""
    raw_date = match.group(1)
    time_label = (match.group(2) or "").upper().replace("  ", " ")
    parsed: datetime | None = None
    for fmt in ("%B %d, %Y", "%b %d, %Y"):
        try:
            parsed = datetime.strptime(raw_date, fmt).replace(tzinfo=STATION_TZ)
            break
        except ValueError:
            continue
    if parsed and time_label:
        try:
            clock = datetime.strptime(time_label.replace(" ", ""), "%I:%M%p")
            parsed = parsed.replace(hour=clock.hour, minute=clock.minute)
        except ValueError:
            pass
    return parsed, time_label


def _parse_root(xml_text: str) -> ET.Element | None:
    text = _XML_DECL_ENCODING.sub(r"\1", str(xml_text or "").strip())
    if not text:
        return None
    try:
        return ET.fromstring(text)
    except ET.ParseError:
        logger.warning("Sports feed XML could not be parsed")
        return None


def _rss_items(xml_text: str) -> list[ET.Element]:
    root = _parse_root(xml_text)
    if root is None:
        return []
    channel = root.find("channel")
    parent = channel if channel is not None else root
    items = [node for node in list(parent) if _local_name(node.tag) == "item"]
    if items:
        return items
    return [node for node in root.iter() if _local_name(node.tag) in {"item", "entry"}]


def _feed_items(xml_text: str) -> list[_FeedItem]:
    items: list[_FeedItem] = []
    for node in _rss_items(xml_text):
        title = _clean_text(_child_text(node, ("title",)))
        summary = _clean_text(_child_text(node, ("description", "summary", "content")))
        if len(summary) > 280:
            summary = summary[:277].rstrip() + "..."
        published = _parse_datetime(_child_text(node, ("pubDate", "published", "updated", "date")))
        if title:
            items.append(_FeedItem(title=title, summary=summary, published=published))
    return items


def _team_name(value: str) -> str:
    text = _clean_text(value).lower()
    for key, label in _TEAM_KEYS:
        if key == "bruins":
            if not re.search(r"\bbruins\b", text) or _NOT_BOSTON_BRUINS_RE.search(text):
                continue
            return label
        if key == "spinners":
            if re.search(r"\bspinners\b", text):
                return label
            continue
        if key in text:
            return label
    return ""


def _sentence(text: str) -> str:
    cleaned = _clean_text(text)
    if not cleaned:
        return ""
    if cleaned[-1] not in ".!?":
        cleaned += "."
    return cleaned


def _mention_line(team: str, text: str) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", _clean_text(text))
    kept = [part for part in (_sentence(sentence) for sentence in sentences) if part and not is_idle_filler(part)]
    spoken = " ".join(kept)
    if not spoken:
        return ""
    if team and team.lower() not in spoken.lower() and "spinners" not in spoken.lower():
        spoken = f"The {team}: {spoken}"
    return spoken


def _team_note_lines(notes: list[dict[str, Any]] | None) -> list[str]:
    grouped: dict[str, list[str]] = {team: [] for team in _TEAM_ORDER}
    other: list[str] = []
    for note in notes or []:
        if not isinstance(note, dict):
            continue
        text = str(note.get("text") or note.get("title") or "")
        team = _team_name(str(note.get("team") or "")) or _team_name(text)
        line = _mention_line(team, text)
        if not line:
            continue
        if team in grouped:
            grouped[team].append(line)
        else:
            other.append(line)
    lines: list[str] = []
    for team in _TEAM_ORDER:
        lines.extend(grouped[team])
    lines.extend(other)
    return lines


def _is_playoff(item: _FeedItem) -> bool:
    return _PLAYOFF_RE.search(f"{item.title} {item.summary}") is not None


def _freshness(item: _FeedItem) -> tuple[int, float]:
    if item.published is None:
        return (1, 0.0)
    return (0, -item.published.timestamp())


def _item_key(item: _FeedItem) -> str:
    return re.sub(r"[^a-z0-9]+", " ", item.title.lower()).strip()


def _is_promo(item: _FeedItem) -> bool:
    return _PROMO_RE.search(f"{item.title} {item.summary}") is not None


def _playoff_lines(items: list[_FeedItem]) -> list[str]:
    playoff = [
        item
        for item in items
        if _is_playoff(item) and not is_idle_filler(item.title) and not _is_promo(item)
    ]
    playoff.sort(key=_freshness)
    lines: list[str] = []
    seen: set[str] = set()
    for item in playoff:
        line = _sentence(item.title)
        key = line.lower()
        if not line or key in seen:
            continue
        seen.add(key)
        lines.append(line)
        if len(lines) >= _PLAYOFF_LIMIT:
            break
    return lines


def _team_news_from_items(items: list[_FeedItem]) -> list[str]:
    """Local-team headlines that are not already playoff copy."""
    notes: list[dict[str, str]] = []
    for item in sorted(items, key=_freshness):
        if _is_playoff(item) or _is_promo(item) or is_idle_filler(item.title):
            continue
        team = _team_name(f"{item.title} {item.summary}")
        if not team:
            continue
        notes.append({"team": team, "text": item.title})
    return _team_note_lines(notes)


def _major_headline_lines(items: list[_FeedItem]) -> list[str]:
    """Freshest general-feed headlines that are not local-team or playoff copy."""
    lines: list[str] = []
    seen: set[str] = set()
    for item in sorted(items, key=_freshness):
        if _is_promo(item) or is_idle_filler(item.title):
            continue
        if _team_name(f"{item.title} {item.summary}"):
            continue
        line = _sentence(item.title)
        key = line.lower()
        if not line or key in seen:
            continue
        seen.add(key)
        lines.append(line)
        if len(lines) >= _HEADLINE_LIMIT:
            break
    return lines


def _opponent_from_title(title: str) -> tuple[str, bool]:
    match = re.search(r"(?i)^(.+?)\s+vs\.?\s+(.+?)(?:\s+final\b.*)?$", title)
    if not match:
        return "", False
    left = _clean_text(match.group(1))
    right = _clean_text(match.group(2))
    if re.search(r"(?i)lowell spinners|\bspinners\b", left) and not re.search(r"(?i)spinners", right):
        return re.sub(r"(?i)^the\s+", "", right).strip(), True
    if re.search(r"(?i)lowell spinners|\bspinners\b", right) and not re.search(r"(?i)spinners", left):
        return re.sub(r"(?i)^the\s+", "", left).strip(), False
    return "", False


def _parse_spinners_game(node: ET.Element) -> _SpinnersGame | None:
    title = _clean_text(_child_text(node, ("title",)))
    description = _clean_text(_child_text(node, ("description", "summary")))
    if not title or title.lower() == "2026 schedule":
        return None
    raw_opponent = _clean_text(_child_text(node, ("opponent",)))
    away = raw_opponent.lower().startswith("at ")
    opponent = re.sub(r"(?i)^at\s+", "", raw_opponent).strip()
    opponent = re.sub(r"(?i)^the\s+", "", opponent).strip()
    if not opponent or re.search(r"(?i)spinners", opponent):
        opponent, title_away = _opponent_from_title(title)
        away = title_away
    if not opponent:
        return None
    when = _parse_datetime(_child_text(node, ("date", "pubDate", "published")))
    described, time_label = _parse_description_when(description)
    if when is None:
        when = described
    elif described is not None and described.tzinfo is not None:
        # Prefer the feed's stated local clock when the timestamp is only a date boundary.
        when = described
    if not time_label and when is not None:
        local = when.astimezone(STATION_TZ)
        hour = local.strftime("%I").lstrip("0") or "12"
        minute = local.strftime("%M")
        ampm = local.strftime("%p")
        time_label = f"{hour} {ampm}" if minute == "00" else f"{hour}:{minute} {ampm}"
    blob = f"{title} {description}".lower()
    # A makeup that was "postponed from" an earlier date and then played is a final.
    if re.search(r"\bfinal\b", blob):
        status = "final"
    elif "cancel" in blob:
        status = "cancelled"
    elif "postpon" in blob:
        status = "postponed"
    else:
        status = "scheduled"
    return _SpinnersGame(
        title=title,
        opponent=opponent,
        away=away,
        when=when,
        time_label=time_label,
        status=status,
    )


def _format_date(day: date) -> str:
    return f"{day.strftime('%A')}, {day.strftime('%B')} {day.day}"


def _spinners_game_line(game: _SpinnersGame, *, today: date) -> str:
    opponent = game.opponent
    if game.status == "final":
        title = re.sub(r"(?i)\s+final\b", ", final", game.title).strip(" ,")
        title = title.replace(" - ", ", ")
        return _sentence(title)
    where = f"at the {opponent}" if game.away else f"the {opponent}"
    clock = f" at {game.time_label}" if game.time_label else ""
    if game.status == "cancelled":
        return _sentence(f"The Lowell Spinners' game against the {opponent} is cancelled")
    if game.status == "postponed":
        return _sentence(f"The Lowell Spinners' game against the {opponent} is postponed")
    if game.local_date == today:
        return _sentence(f"The Lowell Spinners play {where} today{clock}")
    if game.local_date is None:
        return ""
    if game.away:
        return _sentence(f"The Lowell Spinners' next game is {_format_date(game.local_date)} at the {opponent}{clock}")
    return _sentence(
        f"The Lowell Spinners' next game is {_format_date(game.local_date)} against the {opponent}{clock}"
    )


def spinners_lines(xml_text: str, *, today: date) -> list[str]:
    """Today's Spinners game, or the next scheduled game. Otherwise nothing."""
    games = [game for node in _rss_items(xml_text) if (game := _parse_spinners_game(node))]
    dated = [game for game in games if game.local_date is not None]
    dated.sort(key=lambda game: game.when or datetime.min.replace(tzinfo=timezone.utc))
    today_games = [game for game in dated if game.local_date == today]
    if today_games:
        return [line for game in today_games if (line := _spinners_game_line(game, today=today))]
    upcoming = [game for game in dated if game.local_date and game.local_date > today and game.status == "scheduled"]
    if upcoming:
        line = _spinners_game_line(upcoming[0], today=today)
        return [line] if line else []
    cancelled = [
        game
        for game in dated
        if game.local_date
        and game.local_date > today
        and game.status in {"cancelled", "postponed"}
    ]
    if cancelled:
        line = _spinners_game_line(cancelled[0], today=today)
        return [line] if line else []
    return []


def _decode_xml_bytes(raw: bytes) -> str:
    head = raw[:240].lower()
    if b"iso-8859-1" in head or b"latin-1" in head:
        return raw.decode("iso-8859-1", errors="replace")
    return raw.decode("utf-8", errors="replace")


def _fetch_feed(url: str, timeout: float) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": _USER_AGENT,
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        return _decode_xml_bytes(response.read())


def _load_feed(
    xml_text: str | BaseException | None,
    url: str,
    *,
    fetch: bool,
    timeout: float,
    fetcher: Callable[[str, float], str] | None,
) -> str:
    if isinstance(xml_text, BaseException):
        logger.warning("Sports feed skipped: %s", xml_text)
        return ""
    if xml_text is not None:
        return str(xml_text)
    if not fetch:
        return ""
    try:
        if fetcher is not None:
            return fetcher(url, timeout)
        return _fetch_feed(url, timeout)
    except (URLError, OSError, TimeoutError, ValueError) as exc:
        logger.warning("Sports feed unavailable (%s): %s", url, exc)
        return ""


def _dedupe(lines: list[str]) -> list[str]:
    kept: list[str] = []
    seen: set[str] = set()
    for line in lines:
        text = _sentence(line)
        if not text or is_idle_filler(text):
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        kept.append(text)
    return kept


def build_dave_sports_script(
    *,
    today: date | None = None,
    spinners_xml: str | BaseException | None = None,
    fox_xml: str | BaseException | None = None,
    fox_general_xml: str | BaseException | None = None,
    other_xml: list[str | BaseException] | None = None,
    team_notes: list[dict[str, Any]] | None = None,
    fetch: bool = False,
    timeout: float = 8.0,
    fetcher: Callable[[str, float], str] | None = None,
) -> list[str]:
    """Spoken sports lines. Idle teams are omitted. Feeds fail soft."""
    station_today = today or datetime.now(STATION_TZ).date()
    spinners_payload = _load_feed(
        spinners_xml,
        SPINNERS_SCHEDULE_RSS_URL,
        fetch=fetch,
        timeout=timeout,
        fetcher=fetcher,
    )
    fox_payload = _load_feed(
        fox_xml,
        FOX_MLB_RSS_URL,
        fetch=fetch,
        timeout=timeout,
        fetcher=fetcher,
    )
    general_payload = _load_feed(
        fox_general_xml,
        FOX_SPORTS_RSS_URL,
        fetch=fetch,
        timeout=timeout,
        fetcher=fetcher,
    )
    mlb_items = _feed_items(fox_payload)
    covered = {_item_key(item) for item in mlb_items if _item_key(item)}
    general_items: list[_FeedItem] = []
    for item in _feed_items(general_payload):
        key = _item_key(item)
        if not key or key in covered:
            continue
        covered.add(key)
        general_items.append(item)
    for payload in other_xml or []:
        if isinstance(payload, BaseException):
            logger.warning("Sports feed skipped: %s", payload)
            continue
        for item in _feed_items(str(payload)):
            key = _item_key(item)
            if not key or key in covered:
                continue
            covered.add(key)
            general_items.append(item)

    lines = _team_note_lines(team_notes)
    lines.extend(_team_news_from_items(mlb_items + general_items))
    if spinners_payload:
        lines.extend(spinners_lines(spinners_payload, today=station_today))
    lines.extend(_playoff_lines(mlb_items))
    lines.extend(_major_headline_lines(general_items))
    return _dedupe(lines)


def format_sports_story(lines: list[str] | None) -> str:
    """One sports beat with idle filler removed. Empty when there is nothing to read."""
    if not lines:
        return ""
    return " ".join(_dedupe(list(lines)))

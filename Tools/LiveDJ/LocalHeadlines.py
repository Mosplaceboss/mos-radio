"""Today-only local headline asides for Bailey, Kathy, and Johnny J LiveDJ breaks.

Pulls from a local RSS feed (default: WCVB top stories), keeps items dated today
in America/New_York, filters out grim/sensitive topics, and caches a short list
of speakable headlines.

LiveDJ injects these as optional source material so the host can sound current
without turning the break into a newscast. If nothing usable is available, the
break still runs and the host skips the news aside.

Deploy to: D:\\MPR\\Engines\\LiveDJ\\Scripts\\LocalHeadlines.py
"""

from __future__ import annotations

import html
import json
import re
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

try:
    from platform_paths import LIVE_BASE as BASE
except ImportError:  # pragma: no cover - production Scripts folder has platform_paths
    _mpr = Path(r"D:\MPR")
    BASE = _mpr if _mpr.exists() else Path(tempfile.gettempdir()) / "MosPlaceRadio_LocalHeadlines"

OUTPUT_PATH = BASE / "Knowledge" / "LocalHeadlinesToday.json"
STATION_TZ = ZoneInfo("America/New_York")
RSS_URL = "https://www.wcvb.com/topstories-rss"
USER_AGENT = "MosPlaceRadioStudio/1.0 (local radio production; Mo's Place Radio)"
MAX_HEADLINES = 3
FETCH_TIMEOUT_SEC = 15

# Hosts that may receive a casual today-only news aside.
ENABLED_HOSTS = {
    "bailey",
    "kathy",
    "johnny j",
    "johnnyj",
    "johnny",
}

# Conversational break types only — not handoffs, format changes, or history segments.
ALLOWED_EVENT_TYPES = {
    "check-in",
    "weekend check-in",
    "show open",
    "coming up",
    "coming up next",
    "music story",
    "listener memory",
    "artist spotlight",
    "final half hour",
    "today's countdown",
    "news check-in",
}

_LOCAL_RE = re.compile(
    r"(?i)\b("
    r"Boston|Massachusetts|Mass\.|New England|Merrimack|Worcester|Springfield|"
    r"Cambridge|Somerville|Quincy|Lynn|Lowell|Lawrence|Haverhill|Salem|"
    r"Patriots|Red Sox|Celtics|Bruins|Revolution|Cape Cod|Berkshire|"
    r"MBTA|Logan|Fenway|TD Garden|New Hampshire|Vermont|Rhode Island|Maine|"
    r"Connecticut|Hartford|Providence|Portland"
    r")\b"
)

_SKIP_RE = re.compile(
    r"(?i)\b("
    r"kill(?:s|ed|ing)?|murder|homicide|shooting|shot dead|stab(?:bed|bing)?|"
    r"rape|sexual assault|sex offender|child sex|molest|"
    r"suicide|overdose|execution|executed|death penalty|deaths?|"
    r"terror(?:ist|ism)?|bombing|hijack(?:er|ing)?|hostage|"
    r"massacre|genocide|war crime|deadly|fatal(?:ity|ities)?|"
    r"crash kills|dies in|found dead|autopsy|arraignment|extradition"
    r")\b"
)

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _clean_text(value: str) -> str:
    text = html.unescape(str(value or ""))
    text = _TAG_RE.sub(" ", text)
    text = text.replace("\xa0", " ")
    return _WS_RE.sub(" ", text).strip()


def normalize_host(host: str) -> str:
    text = str(host or "").strip().lower()
    text = re.sub(r"[_\-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if text.startswith("dj "):
        text = text[3:].strip()
    aliases = {
        "johnny j.": "johnny j",
        "johnnyjay": "johnny j",
        "johnny jay": "johnny j",
    }
    return aliases.get(text, text)


def station_today(*, when: date | datetime | None = None) -> date:
    if isinstance(when, datetime):
        if when.tzinfo is None:
            return when.replace(tzinfo=STATION_TZ).astimezone(STATION_TZ).date()
        return when.astimezone(STATION_TZ).date()
    if isinstance(when, date):
        return when
    return datetime.now(STATION_TZ).date()


def _read_cache() -> dict[str, Any] | None:
    if not OUTPUT_PATH.exists():
        return None
    try:
        data = json.loads(OUTPUT_PATH.read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _write_cache(data: dict[str, Any]) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(OUTPUT_PATH)


def _parse_pub_date(raw: str) -> datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        parsed = parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError):
        parsed = None
    if parsed is None:
        for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(text.replace("Z", "+0000"), fmt)
                break
            except ValueError:
                continue
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(STATION_TZ)


def _item_text(item: ET.Element, names: tuple[str, ...]) -> str:
    for name in names:
        node = item.find(name)
        if node is not None and (node.text or "").strip():
            return str(node.text)
        # RSS/Atom with namespaces
        for child in item:
            local = child.tag.rsplit("}", 1)[-1]
            if local == name and (child.text or "").strip():
                return str(child.text)
    return ""


def _score_headline(title: str, summary: str) -> int:
    blob = f"{title} {summary}"
    score = 10
    if _LOCAL_RE.search(blob):
        score += 40
    if re.search(r"(?i)\b(Patriots|Red Sox|Celtics|Bruins)\b", blob):
        score += 15
    if re.search(r"(?i)\b(weather|festival|parade|school|traffic|MBTA)\b", blob):
        score += 10
    # Soft national interest still usable, but prefer local.
    if not _LOCAL_RE.search(blob):
        score -= 5
    return score


def _is_speakable(title: str, summary: str) -> bool:
    blob = f"{title} {summary}"
    if not title or len(title) < 12:
        return False
    if _SKIP_RE.search(blob):
        return False
    return True


def parse_rss_items(xml_text: str, *, today: date) -> list[dict[str, str]]:
    """Parse RSS/Atom XML into today's speakable headlines."""
    root = ET.fromstring(xml_text)
    items: list[ET.Element] = []
    if root.tag.rsplit("}", 1)[-1].lower() == "rss" or root.find("channel") is not None:
        channel = root.find("channel")
        items = list(channel.findall("item")) if channel is not None else list(root.iter("item"))
    else:
        items = [node for node in root.iter() if node.tag.rsplit("}", 1)[-1].lower() == "entry"]

    ranked: list[tuple[int, dict[str, str]]] = []
    seen: set[str] = set()
    for item in items:
        title = _clean_text(_item_text(item, ("title",)))
        summary = _clean_text(_item_text(item, ("description", "summary", "content")))
        pub_raw = _item_text(item, ("pubDate", "published", "updated", "date"))
        published = _parse_pub_date(pub_raw)
        if published is None or published.date() != today:
            continue
        if not _is_speakable(title, summary):
            continue
        key = re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        blurb = summary
        if len(blurb) > 180:
            blurb = blurb[:177].rstrip() + "…"
        spoken = title
        if len(spoken) > 140:
            spoken = spoken[:137].rstrip() + "…"
        entry = {
            "title": spoken,
            "summary": blurb,
            "published": published.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }
        ranked.append((_score_headline(title, summary), entry))

    ranked.sort(key=lambda row: (-row[0], row[1]["title"]))
    # Prefer at least one local story when available; otherwise keep soft top stories.
    local = [entry for score, entry in ranked if score >= 40]
    chosen = local[:MAX_HEADLINES] if local else [entry for _, entry in ranked[:MAX_HEADLINES]]
    return chosen


def _fetch_rss_text(url: str = RSS_URL) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
        },
    )
    with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT_SEC) as response:
        return response.read().decode("utf-8", errors="replace")


def refresh_local_headlines(
    *,
    when: date | datetime | None = None,
    force: bool = False,
    rss_url: str = RSS_URL,
    xml_text: str | None = None,
) -> dict[str, Any]:
    """Refresh the daily cache. Fail-soft: empty headlines keep the break on air."""
    day = station_today(when=when)
    day_key = day.isoformat()

    cached = _read_cache()
    if (
        not force
        and xml_text is None
        and cached
        and str(cached.get("date") or "") == day_key
        and isinstance(cached.get("headlines"), list)
        and cached.get("headlines")
        and not str(cached.get("error") or "").strip()
    ):
        return cached

    result: dict[str, Any] = {
        "date": day_key,
        "updated": datetime.now(STATION_TZ).strftime("%Y-%m-%dT%H:%M:%S"),
        "timezone": "America/New_York",
        "source": rss_url if xml_text is None else "inline_xml",
        "hosts": sorted(ENABLED_HOSTS),
        "headlines": [],
        "error": "",
    }
    try:
        payload = xml_text if xml_text is not None else _fetch_rss_text(rss_url)
        result["headlines"] = parse_rss_items(payload, today=day)
        if not result["headlines"]:
            result["error"] = "No usable today-only headlines after filtering"
    except Exception as exc:
        result["error"] = str(exc)
        if cached and str(cached.get("date") or "") == day_key and cached.get("headlines"):
            result["headlines"] = list(cached.get("headlines") or [])
            result["error"] = f"{exc} (served cached headlines)"

    _write_cache(result)
    return result


def load_local_headlines(*, when: date | datetime | None = None) -> list[str]:
    data = refresh_local_headlines(when=when, force=False)
    headlines = data.get("headlines") if isinstance(data, dict) else None
    if not isinstance(headlines, list):
        return []
    lines: list[str] = []
    for item in headlines:
        if isinstance(item, str):
            text = item.strip()
            if text:
                lines.append(text)
            continue
        if not isinstance(item, dict):
            continue
        title = _clean_text(str(item.get("title") or ""))
        summary = _clean_text(str(item.get("summary") or ""))
        if not title:
            continue
        if summary and summary.lower() not in title.lower():
            lines.append(f"{title} — {summary}")
        else:
            lines.append(title)
    return lines


def wants_local_headlines(
    *,
    host: str = "",
    event_type: str = "",
    mission: str = "",
) -> bool:
    """True when this break should receive today's local-headline source material."""
    if normalize_host(host) not in ENABLED_HOSTS:
        return False

    event = str(event_type or "").strip().lower()
    mission_l = str(mission or "").strip().lower()

    if any(
        needle in mission_l
        for needle in (
            "today's news",
            "todays news",
            "local headline",
            "local news aside",
            "looking at the news",
            "news aside",
        )
    ):
        return True

    if event in ALLOWED_EVENT_TYPES:
        return True

    # Legacy / unlabeled conversational breaks for enabled hosts.
    if not event and mission_l:
        blocked = ("handoff", "show close", "format change", "this day in music", "on this day in the 70")
        if any(token in mission_l for token in blocked):
            return False
        return True
    return False


def format_prompt_block(
    headlines: list[str],
    *,
    when: date | datetime | None = None,
    host: str = "",
) -> str:
    day = station_today(when=when)
    label = day.strftime("%B %d, %Y")
    host_label = str(host or "").strip() or "the host"

    if not headlines:
        return (
            f"TODAY'S LOCAL NEWS ASIDE SOURCE ({label}):\n"
            f"(none available — {host_label} should skip any news mention and do the normal break only; "
            "do not invent headlines or news details.)"
        )

    lines = "\n".join(f"- {item}" for item in headlines)
    return (
        f"TODAY'S LOCAL NEWS ASIDE SOURCE ({label}) — OPTIONAL, TODAY ONLY:\n"
        f"{lines}\n"
        "USAGE FOR THIS BREAK:\n"
        f"- {host_label} should do the normal break mission first (time, music, personality).\n"
        "- At most ONE short casual mention of a single story from the list above.\n"
        "- Sound like a real person who glanced at the news today — not a newscaster.\n"
        "- Do not name the news outlet. Do not ramble. Do not stack multiple stories.\n"
        "- Use only the supplied headline/blurb — do not invent details, quotes, or outcomes.\n"
        "- Prefer a light local / New England angle when more than one story is listed.\n"
        "- If nothing fits the mood of the break, skip the news aside entirely."
    )


def prompt_block_for_break(
    *,
    host: str = "",
    event_type: str = "",
    mission: str = "",
    when: date | datetime | None = None,
) -> str:
    """Engine helper: return an inject block or empty string when not applicable."""
    if not wants_local_headlines(host=host, event_type=event_type, mission=mission):
        return ""
    headlines = load_local_headlines(when=when)
    return format_prompt_block(headlines, when=when, host=host)


if __name__ == "__main__":
    data = refresh_local_headlines(force=True)
    print(json.dumps(data, indent=2, ensure_ascii=False))

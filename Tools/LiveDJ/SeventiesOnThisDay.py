"""Factual On This Day in the 1970s source for DJ Casey LiveDJ breaks.

Priority:
1. Operator files in D:\\MPR\\On this Day 1970's
2. Wikimedia On This Day feed, filtered to years 1970-1979 and cached

Operator folder supports dated / batch layouts:
  - 07-30.txt, July 30.txt, OnThisDay1970s_July30.txt
  - Batch files with section headers such as "JULY 30"

Content can be music, movies, sports, pop culture, world events — popular
1970s material. Facts outside 1970-1979 are dropped. Sensitive topics are
filtered. The AI must not invent details.
"""

from __future__ import annotations

import json
import re
import urllib.request
from datetime import date, datetime
from pathlib import Path
from typing import Any

from platform_paths import LIVE_BASE as BASE

OUTPUT_PATH = BASE / "Knowledge" / "SeventiesOnThisDay.json"
OPERATOR_DIR = Path(r"D:\MPR\On this Day 1970's")
API_URL = "https://api.wikimedia.org/feed/v1/wikipedia/en/onthisday/all/{month:02d}/{day:02d}"
USER_AGENT = "MosPlaceRadioStudio/1.0 (local radio production; Mo's Place Radio)"
MAX_FACTS = 5
YEAR_MIN = 1970
YEAR_MAX = 1979

_MONTH_NAMES = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}

_SECTION_HEADER_RE = re.compile(
    r"^\s*=*\s*(january|february|march|april|may|june|july|august|september|october|november|december)"
    r"\s+(\d{1,2})\b",
    re.I,
)
_FACT_START_RE = re.compile(r"^(\d{4})\s*[-–—:]\s*(.+)$")
_END_MARK_RE = re.compile(
    r"end of batch|sources used for verification|note:\s*this is the beginning",
    re.I,
)
_FILENAME_DAY_RE = re.compile(
    r"(january|february|march|april|may|june|july|august|september|october|november|december)"
    r"[_\s\-]?(\d{1,2})\b",
    re.I,
)

_SKIP_RE = re.compile(
    r"(?i)\b("
    r"kill(?:s|ed|ing)?|massacre|murder|earthquake|landslide|war of|battle of|"
    r"sex offender|child sex|serial killer|genocide|holocaust|rape|"
    r"executed|assassination|bombing|terrorist|suicide|flash fire"
    r")\b"
)

_POPULAR_RE = re.compile(
    r"(?i)\b("
    r"song|album|single|Billboard|No\.?\s*1|chart|concert|band|singer|"
    r"movie|film|Oscar|Emmy|Grammy|television|TV|series|actor|actress|"
    r"NASA|Apollo|Space Shuttle|Olympic|Super Bowl|World Series|"
    r"disco|rock|pop|funk|soul|Motown|Saturday Night Live|Star Wars|"
    r"president|premiered|released|debut"
    r")\b"
)


def _clean_text(value: str) -> str:
    text = (value or "").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _in_decade(year: int) -> bool:
    return YEAR_MIN <= year <= YEAR_MAX


def _read_cache() -> dict[str, Any]:
    try:
        if OUTPUT_PATH.is_file():
            data = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {}


def _write_cache(data: dict[str, Any]) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(OUTPUT_PATH)


def _day_from_filename(path: Path) -> tuple[int, int] | None:
    match = _FILENAME_DAY_RE.search(path.stem.replace(".", " "))
    if not match:
        return None
    month = _MONTH_NAMES.get(match.group(1).lower(), 0)
    day_num = int(match.group(2))
    if month < 1 or day_num < 1 or day_num > 31:
        return None
    return month, day_num


def _parse_year_facts(raw: str, *, whole_file: bool = False) -> list[str]:
    facts: list[str] = []
    lines = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if not whole_file and _END_MARK_RE.search(stripped):
            break
        if not whole_file and _SECTION_HEADER_RE.match(stripped) and facts:
            break
        match = _FACT_START_RE.match(stripped)
        if not match:
            i += 1
            continue
        year = int(match.group(1))
        body = match.group(2).strip()
        i += 1
        while i < len(lines):
            nxt = lines[i].strip()
            if not nxt:
                break
            if _FACT_START_RE.match(nxt) or _SECTION_HEADER_RE.match(nxt) or _END_MARK_RE.search(nxt):
                break
            if re.match(r"(?i)^(sources|birthdays|suggested|notable)", nxt):
                break
            body = f"{body} {nxt}".strip()
            i += 1
        body = _clean_text(body)
        if not _in_decade(year) or not body or _SKIP_RE.search(body):
            continue
        line = f"{year}: {body}"
        if line not in facts:
            facts.append(line)
        if len(facts) >= MAX_FACTS:
            break
    return facts


def _parse_batch_section(raw: str, day: date) -> list[str]:
    lines = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    collecting = False
    chunk: list[str] = []
    for line in lines:
        stripped = line.strip()
        header = _SECTION_HEADER_RE.match(stripped)
        if header:
            month = _MONTH_NAMES.get(header.group(1).lower(), 0)
            day_num = int(header.group(2))
            if collecting:
                break
            collecting = month == day.month and day_num == day.day
            continue
        if _END_MARK_RE.search(stripped) and collecting:
            break
        if collecting:
            chunk.append(line)
    if not chunk:
        return []
    return _parse_year_facts("\n".join(chunk), whole_file=True)


def _text_file_candidates(day: date) -> list[Path]:
    month_name = day.strftime("%B")
    return [
        OPERATOR_DIR / f"{day.month:02d}-{day.day:02d}.txt",
        OPERATOR_DIR / f"{month_name} {day.day}.txt",
        OPERATOR_DIR / f"{month_name}_{day.day}.txt",
        OPERATOR_DIR / f"OnThisDay1970s_{month_name}{day.day}.txt",
        OPERATOR_DIR / f"OnThisDay1970s_{month_name}_{day.day}.txt",
    ]


def _load_facts_from_operator(day: date) -> tuple[list[str], str]:
    if not OPERATOR_DIR.is_dir():
        return [], ""

    for path in _text_file_candidates(day):
        if not path.is_file():
            continue
        try:
            raw = path.read_text(encoding="utf-8-sig")
        except Exception:
            continue
        facts = _parse_year_facts(raw, whole_file=True)
        if facts:
            return facts, str(path)

    files = sorted(
        OPERATOR_DIR.glob("*.txt"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for path in files:
        if path.name.lower() in {"readme.txt"}:
            continue
        try:
            raw = path.read_text(encoding="utf-8-sig")
        except Exception:
            continue
        file_day = _day_from_filename(path)
        if file_day == (day.month, day.day):
            facts = _parse_year_facts(raw, whole_file=True)
            if facts:
                return facts, str(path)
        if _SECTION_HEADER_RE.search(raw):
            facts = _parse_batch_section(raw, day)
            if facts:
                return facts, str(path)
    return [], ""


def _fetch_payload(day: date) -> dict[str, Any]:
    url = API_URL.format(month=day.month, day=day.day)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _score(section: str, text: str, year: int) -> int:
    score = 0
    if section == "events":
        score += 40
    elif section == "selected":
        score += 35
    elif section == "births":
        score += 15
    elif section == "deaths":
        score += 5
    if _POPULAR_RE.search(text):
        score += 25
    if 1973 <= year <= 1977:
        score += 5
    return score


def _fact_from_item(section: str, item: dict[str, Any]) -> tuple[int, str] | None:
    try:
        year = int(item.get("year"))
    except (TypeError, ValueError):
        return None
    if not _in_decade(year):
        return None
    text = _clean_text(str(item.get("text") or ""))
    if not text or _SKIP_RE.search(text):
        return None
    if len(text) > 220:
        text = text[:217].rstrip() + "…"
    return _score(section, text, year), f"{year}: {text}"


def _select_facts(payload: dict[str, Any]) -> list[str]:
    ranked: list[tuple[int, str]] = []
    seen: set[str] = set()
    for section in ("events", "selected", "births", "deaths"):
        for item in payload.get(section) or []:
            if not isinstance(item, dict):
                continue
            parsed = _fact_from_item(section, item)
            if not parsed:
                continue
            score, line = parsed
            key = re.sub(r"[^a-z0-9]+", " ", line.lower())[:80]
            if key in seen:
                continue
            seen.add(key)
            ranked.append((score, line))
    ranked.sort(key=lambda row: (-row[0], row[1]))
    return [line for _, line in ranked[:MAX_FACTS]]


def refresh_seventies_on_this_day(
    *, when: date | datetime | None = None, force: bool = False
) -> dict[str, Any]:
    """Refresh the daily cache. Operator text files win over Wikipedia."""
    if isinstance(when, datetime):
        day = when.date()
    elif isinstance(when, date):
        day = when
    else:
        day = date.today()

    day_key = day.isoformat()
    text_facts, text_source = _load_facts_from_operator(day)
    if text_facts:
        result: dict[str, Any] = {
            "date": day_key,
            "month": day.month,
            "day": day.day,
            "updated": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "source": f"text_file:{text_source}",
            "year_range": f"{YEAR_MIN}-{YEAR_MAX}",
            "facts": text_facts,
            "error": "",
        }
        _write_cache(result)
        return result

    cached = _read_cache()
    if (
        not force
        and cached
        and str(cached.get("date") or "") == day_key
        and isinstance(cached.get("facts"), list)
        and cached.get("facts")
        and not str(cached.get("source") or "").startswith("text_file:")
    ):
        return cached

    result = {
        "date": day_key,
        "month": day.month,
        "day": day.day,
        "updated": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "source": "wikimedia_onthisday_1970s",
        "year_range": f"{YEAR_MIN}-{YEAR_MAX}",
        "facts": [],
        "error": "",
    }
    try:
        payload = _fetch_payload(day)
        result["facts"] = _select_facts(payload)
        if not result["facts"]:
            result["error"] = "No clear 1970-1979 items found for this date"
    except Exception as exc:
        result["error"] = str(exc)
        if cached and str(cached.get("date") or "") == day_key and cached.get("facts"):
            result["facts"] = list(cached.get("facts") or [])
            result["error"] = f"{exc} (served cached facts)"

    _write_cache(result)
    return result


def load_seventies_facts(*, when: date | datetime | None = None) -> list[str]:
    data = refresh_seventies_on_this_day(when=when, force=False)
    facts = data.get("facts") if isinstance(data, dict) else None
    if not isinstance(facts, list):
        return []
    return [str(item).strip() for item in facts if str(item).strip()]


def wants_seventies_on_this_day(*, event_type: str = "", mission: str = "") -> bool:
    event = str(event_type or "").strip().lower()
    mission_l = str(mission or "").strip().lower()
    if event in {
        "on this day in the 70s",
        "on this day in the 1970s",
        "70s on this day",
        "1970s on this day",
    }:
        return True
    if "on this day" in mission_l and ("70" in mission_l or "1970" in mission_l):
        return True
    return False


def format_prompt_block(facts: list[str], *, when: date | datetime | None = None) -> str:
    if isinstance(when, datetime):
        label = when.strftime("%B %d")
    elif isinstance(when, date):
        label = when.strftime("%B %d")
    else:
        label = date.today().strftime("%B %d")

    if not facts:
        return (
            f"ON THIS DAY IN THE 1970s SOURCE ({label}):\n"
            "(none available — skip this segment; do not invent any 1970s history.)"
        )
    lines = "\n".join(f"- {fact}" for fact in facts)
    return (
        f"ON THIS DAY IN THE 1970s SOURCE ({label}) — FACTUAL ONLY, YEARS 1970-1979:\n"
        f"{lines}"
    )


if __name__ == "__main__":
    data = refresh_seventies_on_this_day(force=True)
    print(json.dumps(data, indent=2, ensure_ascii=False))

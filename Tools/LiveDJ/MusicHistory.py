"""Factual This Day in Music History source for LiveDJ.

Priority:
1. Operator files in D:\\MPR\\This Day in History
2. Knowledge folder text files
3. Wikipedia On This Day feed (Wikimedia API), music-filtered and cached

Operator folder supports:
  - Dated files: 2026-07-30.txt, 07-30.txt, July 30.txt
  - Batch files like OnThisDayInMusic_Batch01_January1-2.txt with
    section headers such as "JANUARY 1" / "JULY 30"

LiveDJ injects these as source material so the AI can talk about music history
without inventing facts. If nothing is available, the break still runs and the
host should skip that topic.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path
from typing import Any

from platform_paths import LIVE_BASE as BASE

OUTPUT_PATH = BASE / "Knowledge" / "MusicHistoryToday.json"
TEXT_TODAY_PATH = BASE / "Knowledge" / "MusicHistoryToday.txt"
TEXT_DIR = BASE / "Knowledge" / "MusicHistory"
OPERATOR_DIR = Path(r"D:\MPR\This Day in History")
API_URL = "https://api.wikimedia.org/feed/v1/wikipedia/en/onthisday/all/{month:02d}/{day:02d}"
USER_AGENT = "MosPlaceRadioStudio/1.0 (local radio production; Mo's Place Radio)"
MAX_FACTS = 5

_MONTH_NAMES = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
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

# Occupations / roles that mark a birth or death as music-related.
_OCCUPATION_RE = re.compile(
    r"\b("
    r"singer|songwriter|musician|guitarist|drummer|bassist|pianist|composer|"
    r"rapper|vocalist|saxophonist|violinist|cellist|conductor|record producer|"
    r"music producer|disc jockey|bandleader|banjo|harmonica|trumpeter|"
    r"blues guitarist|country singer|folk singer|jazz|motown"
    r")\b",
    re.I,
)

# Event text must look like a music industry milestone, not a disaster page
# that happened to mention a song.
_EVENT_RE = re.compile(
    r"\b("
    r"album|single|recorded|Billboard|concert|Top of the Pops|"
    r"released .+album|number[- ]one|No\. ?1|hit single|music show|"
    r"Grammy|Sun Studio|record label|vinyl|chart(?:s|ed|ing)?"
    r")\b",
    re.I,
)

_SKIP_EVENT_RE = re.compile(
    r"\b("
    r"killed|killing|massacre|earthquake|landslide|war |battle|"
    r"sank|exploded|football|World Cup|hurricane|tornado|murder"
    r")\b",
    re.I,
)

# Keep these off the air even if Wikipedia lists them under music.
_SKIP_PERSON_RE = re.compile(
    r"\b("
    r"sex offender|child sex|convicted|murderer|serial killer"
    r")\b",
    re.I,
)

# Prefer well-known names when ranking births (optional boost, not a whitelist).
_NAME_BOOST = (
    "Johnny Cash",
    "Elvis Presley",
    "The Beatles",
    "Beatles",
    "Rolling Stones",
    "Bruce Springsteen",
    "Springsteen",
    "Bob Dylan",
    "Dylan",
    "Frank Sinatra",
    "Sinatra",
    "Jimi Hendrix",
    "Hendrix",
    "David Bowie",
    "Bowie",
    "Prince",
    "Madonna",
    "Michael Jackson",
    "Aretha Franklin",
    "Aretha",
    "Stevie Wonder",
    "James Brown",
    "Chuck Berry",
    "Little Richard",
    "AC/DC",
    "Led Zeppelin",
    "Pink Floyd",
    "Queen",
    "U2",
    "Eagles",
    "Fleetwood Mac",
    "Jimmy Buffett",
    "Buffett",
    "Kate Bush",
    "Buddy Guy",
    "Paul Anka",
)


def _page_description(item: dict[str, Any]) -> str:
    parts: list[str] = []
    for page in item.get("pages") or []:
        if not isinstance(page, dict):
            continue
        parts.append(str(page.get("description") or "").strip())
    return " ".join(p for p in parts if p)


def _page_extract(item: dict[str, Any]) -> str:
    for page in item.get("pages") or []:
        if isinstance(page, dict) and page.get("extract"):
            return str(page.get("extract") or "").strip()
    return ""


def _clean_text(value: str) -> str:
    text = (value or "").replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _is_music_birth_or_death(item: dict[str, Any]) -> bool:
    text = _clean_text(str(item.get("text") or ""))
    desc = _page_description(item)
    blob = f"{text} {desc}"
    if _SKIP_PERSON_RE.search(blob):
        return False
    return bool(_OCCUPATION_RE.search(desc) or _OCCUPATION_RE.search(text))


def _is_music_event(item: dict[str, Any]) -> bool:
    text = _clean_text(str(item.get("text") or ""))
    if not text or _SKIP_EVENT_RE.search(text):
        return False
    if _SKIP_PERSON_RE.search(text):
        return False
    return bool(_EVENT_RE.search(text) or _OCCUPATION_RE.search(text))


def _score(section: str, item: dict[str, Any]) -> int:
    text = _clean_text(str(item.get("text") or ""))
    score = 0
    if section == "events":
        score += 40
    elif section == "selected":
        score += 30
    elif section == "births":
        score += 20
    elif section == "deaths":
        score += 5  # usable, but not preferred for upbeat breaks
    text_l = text.lower()
    for name in _NAME_BOOST:
        # Word-boundary style match so "Elvis" does not boost "Elvis Crespo" alone
        # unless the full boosted name appears; single-token names still need edges.
        pattern = r"(?<![A-Za-z])" + re.escape(name.lower()) + r"(?![A-Za-z])"
        if re.search(pattern, text_l):
            score += 25
            break
    year = item.get("year")
    try:
        y = int(year)
        if 1950 <= y <= 2015:
            score += 5
    except (TypeError, ValueError):
        pass
    return score


def _fact_line(section: str, item: dict[str, Any]) -> str | None:
    year = item.get("year")
    text = _clean_text(str(item.get("text") or ""))
    if year is None or not text:
        return None
    try:
        year_i = int(year)
    except (TypeError, ValueError):
        return None
    if section == "births":
        kind = "Birthday"
    elif section == "deaths":
        kind = "Passed away"
    else:
        kind = "On this day"
    # Keep the spoken-friendly fact short; Producer still gets the full line.
    if len(text) > 220:
        text = text[:217].rstrip() + "…"
    return f"{kind} ({year_i}): {text}"


def _select_facts(payload: dict[str, Any]) -> list[str]:
    ranked: list[tuple[int, str, dict[str, Any]]] = []
    for section, checker in (
        ("events", _is_music_event),
        ("selected", _is_music_event),
        ("births", _is_music_birth_or_death),
        ("deaths", _is_music_birth_or_death),
    ):
        for item in payload.get(section) or []:
            if not isinstance(item, dict):
                continue
            if not checker(item):
                continue
            line = _fact_line(section, item)
            if not line:
                continue
            ranked.append((_score(section, item), section, item))

    ranked.sort(key=lambda row: row[0], reverse=True)
    facts: list[str] = []
    seen: set[str] = set()
    for _score_val, section, item in ranked:
        line = _fact_line(section, item)
        if not line:
            continue
        key = line.lower()
        if key in seen:
            continue
        seen.add(key)
        facts.append(line)
        if len(facts) >= MAX_FACTS:
            break
    return facts


def _fetch_payload(when: date) -> dict[str, Any]:
    url = API_URL.format(month=when.month, day=when.day)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read().decode("utf-8", errors="replace")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise RuntimeError("Unexpected On This Day payload")
    return data


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


def _text_file_candidates(day: date) -> list[Path]:
    """Prefer operator-written text files over the Wikipedia feed."""
    month_name = day.strftime("%B")  # July
    return [
        OPERATOR_DIR / f"{day.isoformat()}.txt",
        OPERATOR_DIR / f"{day.month:02d}-{day.day:02d}.txt",
        OPERATOR_DIR / f"{month_name} {day.day}.txt",
        OPERATOR_DIR / f"{month_name}_{day.day}.txt",
        TEXT_DIR / f"{day.isoformat()}.txt",
        TEXT_DIR / f"{day.month:02d}-{day.day:02d}.txt",
        TEXT_TODAY_PATH,
    ]


def _parse_simple_lines(raw: str) -> list[str]:
    facts: list[str] = []
    for line in raw.splitlines():
        text = line.strip()
        if not text or text.startswith("#") or set(text) <= {"=", "-", " "}:
            continue
        if _END_MARK_RE.search(text):
            break
        text = re.sub(r"^[-*•]\s*", "", text)
        text = re.sub(r"^(fact|on this day)\s*[:\-]\s*", "", text, flags=re.I)
        text = text.strip()
        if text and text not in facts:
            facts.append(text)
        if len(facts) >= MAX_FACTS:
            break
    return facts


def _day_from_filename(path: Path) -> tuple[int, int] | None:
    match = _FILENAME_DAY_RE.search(path.stem.replace(".", " "))
    if not match:
        return None
    month = _MONTH_NAMES.get(match.group(1).lower(), 0)
    day_num = int(match.group(2))
    if month < 1 or day_num < 1 or day_num > 31:
        return None
    return month, day_num


def _extract_year_facts(raw: str, *, whole_file: bool = False) -> list[str]:
    """Collect year-leading facts from a single-day file or an active section."""
    facts: list[str] = []
    current: list[str] = []
    collecting = whole_file

    def flush() -> None:
        nonlocal current
        if not current:
            return
        text = _clean_text(" ".join(current))
        current = []
        if not text:
            return
        match = _FACT_START_RE.match(text)
        if match:
            text = f"{match.group(1)}: {match.group(2).strip()}"
        if text not in facts:
            facts.append(text)

    for line in raw.splitlines():
        stripped = line.strip()
        if _END_MARK_RE.search(stripped):
            flush()
            break

        header = _SECTION_HEADER_RE.match(stripped)
        if header and not whole_file:
            flush()
            # Section switching is handled by the caller for multi-day batches.
            continue

        if not collecting and not whole_file:
            continue
        if not stripped or set(stripped) <= {"=", "-", " "}:
            continue
        if stripped.lower().startswith("birthdays"):
            flush()
            break

        start = _FACT_START_RE.match(stripped)
        if start:
            flush()
            current = [stripped]
            collecting = True
        elif current:
            current.append(stripped)

    flush()
    return facts[:MAX_FACTS]


def _parse_batch_section(raw: str, day: date) -> list[str]:
    """Extract facts for one calendar day from a batch-style master file."""
    target_month = day.month
    target_day = day.day
    in_section = False
    facts: list[str] = []
    current: list[str] = []

    def flush() -> None:
        nonlocal current
        if not current:
            return
        text = _clean_text(" ".join(current))
        current = []
        if not text:
            return
        match = _FACT_START_RE.match(text)
        if match:
            text = f"{match.group(1)}: {match.group(2).strip()}"
        if text not in facts:
            facts.append(text)

    for line in raw.splitlines():
        stripped = line.strip()
        if _END_MARK_RE.search(stripped):
            if in_section:
                flush()
            break

        header = _SECTION_HEADER_RE.match(stripped)
        if header:
            if in_section:
                flush()
                in_section = False
                if len(facts) >= MAX_FACTS:
                    break
            month = _MONTH_NAMES.get(header.group(1).lower(), 0)
            day_num = int(header.group(2))
            in_section = month == target_month and day_num == target_day
            continue

        if not in_section:
            continue
        if not stripped or set(stripped) <= {"=", "-", " "}:
            continue
        if stripped.lower().startswith("birthdays"):
            flush()
            break

        start = _FACT_START_RE.match(stripped)
        if start:
            flush()
            current = [stripped]
        elif current:
            current.append(stripped)

    if in_section:
        flush()
    return facts[:MAX_FACTS]


def _load_facts_from_operator_batches(day: date) -> tuple[list[str], str]:
    if not OPERATOR_DIR.is_dir():
        return [], ""
    # Newest files first so later edits win when overlapping.
    files = sorted(
        OPERATOR_DIR.glob("*.txt"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for path in files:
        name = path.name.lower()
        if name in {"readme.txt"}:
            continue
        try:
            raw = path.read_text(encoding="utf-8-sig")
        except Exception:
            continue

        file_day = _day_from_filename(path)
        if file_day == (day.month, day.day):
            # Single-day operator file such as OnThisDayInMusic_July30.txt
            facts = _extract_year_facts(raw, whole_file=True)
            if facts:
                return facts, str(path)

        if _SECTION_HEADER_RE.search(raw):
            facts = _parse_batch_section(raw, day)
            if facts:
                return facts, str(path)
    return [], ""


def _load_facts_from_text_file(day: date) -> tuple[list[str], str]:
    """Return (facts, source_path) from operator/dated text, else batch files."""
    for path in _text_file_candidates(day):
        if not path.is_file():
            continue
        try:
            raw = path.read_text(encoding="utf-8-sig")
        except Exception:
            continue
        file_day = _day_from_filename(path)
        if file_day == (day.month, day.day) or path == TEXT_TODAY_PATH:
            facts = _extract_year_facts(raw, whole_file=True)
            if not facts:
                facts = _parse_simple_lines(raw)
        elif _SECTION_HEADER_RE.search(raw):
            facts = _parse_batch_section(raw, day)
        else:
            facts = _parse_simple_lines(raw)
        if facts:
            return facts, str(path)

    return _load_facts_from_operator_batches(day)

def refresh_music_history(*, when: date | datetime | None = None, force: bool = False) -> dict[str, Any]:
    """Refresh the daily cache. Text files win over Wikipedia when present."""
    if isinstance(when, datetime):
        day = when.date()
    elif isinstance(when, date):
        day = when
    else:
        day = date.today()

    day_key = day.isoformat()
    text_facts, text_source = _load_facts_from_text_file(day)
    if text_facts:
        result: dict[str, Any] = {
            "date": day_key,
            "month": day.month,
            "day": day.day,
            "updated": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "source": f"text_file:{text_source}",
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
        "source": "wikimedia_onthisday",
        "facts": [],
        "error": "",
    }
    try:
        payload = _fetch_payload(day)
        result["facts"] = _select_facts(payload)
        if not result["facts"]:
            result["error"] = "No clear music-history items found for this date"
    except Exception as exc:
        result["error"] = str(exc)
        # Keep yesterday's facts only if they are for the same calendar day.
        if cached and str(cached.get("date") or "") == day_key and cached.get("facts"):
            result["facts"] = list(cached.get("facts") or [])
            result["error"] = f"{exc} (served cached facts)"

    _write_cache(result)
    return result


def load_music_history_facts(*, when: date | datetime | None = None) -> list[str]:
    data = refresh_music_history(when=when, force=False)
    facts = data.get("facts") if isinstance(data, dict) else None
    if not isinstance(facts, list):
        return []
    return [str(item).strip() for item in facts if str(item).strip()]


def wants_music_history(*, event_type: str = "", mission: str = "") -> bool:
    """True when this break should receive factual music-history source material."""
    event = str(event_type or "").strip().lower()
    mission_l = str(mission or "").strip().lower()
    if event in {"this day in music history", "music history"}:
        return True
    if "this day in music" in mission_l:
        return True
    if "music history" in mission_l and ("this day" in mission_l or "today" in mission_l or "factual" in mission_l):
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
            f"THIS DAY IN MUSIC HISTORY SOURCE ({label}):\n"
            "(none available — skip music-history content for this break; do not invent any.)"
        )
    lines = "\n".join(f"- {fact}" for fact in facts)
    return f"THIS DAY IN MUSIC HISTORY SOURCE ({label}) — FACTUAL ONLY:\n{lines}"


if __name__ == "__main__":
    data = refresh_music_history(force=True)
    print(json.dumps(data, indent=2, ensure_ascii=False))

"""
Verify the BIRTHDAYS entries in the operator's "This Day in History" drafts.

The drafts list artist birthdays by hand. Those names are on-format and worth
airing, but a hand-typed date is not a source, so every entry is checked against
Wikidata's date-of-birth claim (P569) before it is allowed to become a fact.

Output: music_birthday_verified.json, keyed by "MM-DD". Nothing is written back
into the day files here; enrich_music_history_days.py consumes the JSON.

Usage:
    python verify_music_birthdays.py            # verify everything (uses cache)
    python verify_music_birthdays.py --refresh   # ignore cached lookups
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

OPERATOR_DIR = Path(r"D:\MPR\This Day in History")
OUT_PATH = Path(__file__).with_name("music_birthday_verified.json")
CACHE_PATH = Path(__file__).with_name("_wikidata_dob_cache.json")

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "MosPlaceRadioStudio/1.0 (local radio production; Mo's Place Radio)"
# The per-name search API rate-limits almost immediately, so names are verified
# in batches through the query service instead.
BATCH_SIZE = 50
REQUEST_PACING_SECONDS = 2.0
SEARCH_PACING_SECONDS = 3.0
MAX_PER_DAY = 5

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}

DAY_FILE_RE = re.compile(
    r"^OnThisDayInMusic_(january|february|march|april|may|june|july|august"
    r"|september|october|november|december)(\d{1,2})\.txt$",
    re.I,
)
# The drafts came through a few different editors, so bullets arrive as a real
# bullet, a hyphen, or a mojibake replacement character.
BULLET_RE = re.compile(r"^[\u2022\u00b7\-\*\uFFFD\?]+\s*(.+)$")
ENTRY_RE = re.compile(
    r"^(?P<name>.+?)\s*\((?P<born>\d{4})"          # Name (1950
    r"(?:\s*[\u2013\u2014\-]\s*(?:\d{4}|present))?\)"  # optional -2022 / -present
    r"(?:\s*[\u2013\u2014\-]+\s*(?P<band>.+))?$"    # optional - Heart
)

# Roles that confirm a Wikidata hit is a music figure rather than a namesake.
MUSIC_DESC_RE = re.compile(
    r"(?i)\b(singer|songwriter|musician|guitarist|drummer|bassist|pianist|"
    r"composer|rapper|vocalist|band|record producer|music|saxophonist|"
    r"keyboardist|fiddler|banjo|violinist|cellist|conductor|dj|"
    r"multi-instrumentalist|performer|entertainer|actress|actor)\b"
)
# The station's format, used only to rank which verified entries survive the trim.
FOCUS_RE = re.compile(
    r"(?i)\b(country|rock|pop|folk|bluegrass|singer-songwriter|guitarist|"
    r"drummer|bassist|keyboardist)\b"
)


def read_text(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def birthday_entries(text: str) -> list[str]:
    entries: list[str] = []
    inside = False
    for line in text.replace("\r\n", "\n").split("\n"):
        stripped = line.strip()
        if re.match(r"(?i)^BIRTHDAYS\b", stripped):
            inside = True
            continue
        if not inside:
            continue
        if stripped.startswith("=") or re.match(
            r"(?i)^(SUGGESTED|NOTABLE|SOURCES|ON THIS DAY)", stripped
        ):
            break
        match = BULLET_RE.match(stripped)
        if match:
            entries.append(match.group(1).strip())
    return entries


def collect_drafts() -> dict[tuple[int, int], list[tuple[str, int, str]]]:
    """Map (month, day) -> [(name, stated_year, band)] from drafts and backups."""
    found: dict[tuple[int, int], list[tuple[str, int, str]]] = {}
    for path in sorted(OPERATOR_DIR.glob("OnThisDayInMusic_*.txt")):
        match = DAY_FILE_RE.match(path.name)
        if not match:
            continue
        key = (MONTHS[match.group(1).lower()], int(match.group(2)))

        entries = birthday_entries(read_text(path))
        if not entries:
            # Enrichment rewrote the file and dropped the section; the original
            # draft is still on disk as the .bak the enricher left behind.
            backup = path.with_suffix(".txt.bak")
            if backup.is_file():
                entries = birthday_entries(read_text(backup))

        parsed: list[tuple[str, int, str]] = []
        for entry in entries:
            entry_match = ENTRY_RE.match(entry)
            if not entry_match:
                continue
            name = re.sub(r"\s+", " ", entry_match.group("name")).strip(" -\u2013\u2014")
            band = (entry_match.group("band") or "").strip(" -\u2013\u2014")
            band = re.sub(r"\s+", " ", band)
            if name:
                parsed.append((name, int(entry_match.group("born")), band))
        if parsed:
            found[key] = parsed
    return found


SPARQL_TEMPLATE = """
SELECT ?name ?item ?dob ?desc
       (GROUP_CONCAT(DISTINCT ?occLabel; separator=", ") AS ?occs) WHERE {
  VALUES ?name { %s }
  ?item rdfs:label|skos:altLabel ?name .
  ?item wdt:P569 ?dob .
  OPTIONAL { ?item wdt:P106 ?occ . ?occ rdfs:label ?occLabel . FILTER(LANG(?occLabel) = "en") }
  OPTIONAL { ?item schema:description ?desc . FILTER(LANG(?desc) = "en") }
}
GROUP BY ?name ?item ?dob ?desc
"""


def sparql(query: str, attempts: int = 5) -> list[dict]:
    body = urllib.parse.urlencode({"query": query, "format": "json"}).encode("utf-8")
    delay = 10.0
    for attempt in range(attempts):
        request = urllib.request.Request(
            SPARQL_ENDPOINT,
            data=body,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/sparql-results+json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                data = json.loads(response.read().decode("utf-8"))
            return data.get("results", {}).get("bindings", [])
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504) and attempt < attempts - 1:
                print(f"  query service busy ({exc.code}), waiting {delay:.0f}s...", flush=True)
                time.sleep(delay)
                delay *= 2
                continue
            raise
        except Exception as exc:
            if attempt < attempts - 1:
                print(f"  retry after {type(exc).__name__}, waiting {delay:.0f}s...", flush=True)
                time.sleep(delay)
                delay *= 2
                continue
            raise
    return []


def lookup_batch(names: list[str]) -> dict[str, list[dict]]:
    """Verify a batch of names in one query; returns name -> candidate records."""
    values = " ".join('"%s"@en' % n.replace("\\", "").replace('"', '\\"') for n in names)
    rows = sparql(SPARQL_TEMPLATE % values)

    found: dict[str, list[dict]] = {name: [] for name in names}
    for row in rows:
        name = row.get("name", {}).get("value", "")
        if name not in found:
            continue
        found[name].append({
            "qid": row.get("item", {}).get("value", "").rsplit("/", 1)[-1],
            "dob": row.get("dob", {}).get("value", ""),
            "description": row.get("desc", {}).get("value", ""),
            "occupations": row.get("occs", {}).get("value", ""),
        })
    return found


def name_variants(name: str) -> list[str]:
    """Spellings worth trying: as written, then without a quoted nickname."""
    variants = [name]
    without_nickname = re.sub(r'\s*"[^"]*"\s*', " ", name)
    without_nickname = re.sub(r"\s+", " ", without_nickname).strip()
    if without_nickname and without_nickname != name:
        variants.append(without_nickname)
    without_suffix = re.sub(r"(?i)\s+(sr|jr)\.?$", "", name).strip()
    if without_suffix and without_suffix not in variants:
        variants.append(without_suffix)
    return variants


SEARCH_API = "https://www.wikidata.org/w/api.php"


def api_get(params: dict[str, str], attempts: int = 3) -> dict:
    url = SEARCH_API + "?" + urllib.parse.urlencode({**params, "format": "json"})
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    delay = 10.0
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception:
            if attempt < attempts - 1:
                time.sleep(delay)
                delay *= 2
                continue
            raise
    return {}


def lookup_by_search(name: str) -> list[dict]:
    """Fallback for names whose Wikidata label is spelled differently.

    SPARQL matches labels exactly, so "B.B. King" misses "B. B. King" and an
    unaccented "Celine Dion" misses "Celine Dion". The search API is fuzzy but
    rate-limits hard, so it is only used for the few names SPARQL could not find.
    """
    search = api_get({
        "action": "wbsearchentities",
        "search": name,
        "language": "en",
        "uselang": "en",
        "limit": "5",
        "type": "item",
    })
    time.sleep(SEARCH_PACING_SECONDS)
    qids = [hit["id"] for hit in (search.get("search") or [])[:4]]
    if not qids:
        return []

    entities = api_get({
        "action": "wbgetentities",
        "ids": "|".join(qids),
        "props": "claims|descriptions",
        "languages": "en",
    })
    time.sleep(SEARCH_PACING_SECONDS)

    candidates: list[dict] = []
    for qid in qids:
        entity = (entities.get("entities") or {}).get(qid) or {}
        description = ((entity.get("descriptions") or {}).get("en") or {}).get("value", "")
        occupations = ""
        for claim in (entity.get("claims") or {}).get("P569", []):
            snak = (claim.get("mainsnak") or {}).get("datavalue", {}).get("value") or {}
            if snak.get("precision", 0) < 11:
                continue
            candidates.append({
                "qid": qid,
                "dob": snak.get("time", ""),
                "description": description,
                "occupations": occupations,
            })
    return candidates


def parse_dob(time_string: str) -> tuple[int, int, int] | None:
    """Accept both Wikidata JSON (+1950-06-19T..) and SPARQL (1950-06-19T..) forms."""
    match = re.match(r"^\+?(\d{4})-(\d{2})-(\d{2})T", time_string or "")
    if not match:
        return None
    year, month, day = (int(g) for g in match.groups())
    if month < 1 or day < 1:
        # Wikidata pads imprecise dates as 00; those cannot confirm a day.
        return None
    return year, month, day


def short_role(description: str) -> str:
    """Turn a Wikidata description into an on-air role phrase.

    Wikidata appends life dates, e.g. "American guitarist (born 1943)", which
    would otherwise read on air as "...(born 1943) George Benson was born."
    """
    role = re.sub(r"\s*\((?:born\s*)?\d{4}[^)]*\)", "", description)
    role = role.split(",")[0].strip()
    role = re.sub(r"(?i)\s+from\s+.*$", "", role).strip(" -\u2013\u2014")
    return role


# Draft "band" fields sometimes hold a role instead, e.g. "Jazz legend", which
# would read as "Ella Fitzgerald of Jazz legend was born."
ROLE_NOT_BAND_RE = re.compile(
    r"(?i)\b(legend|legendary|icon|iconic|pioneer|great|superstar|star|artist|"
    r"singer|songwriter|guitarist|drummer|bassist|pianist|producer|vocalist|"
    r"frontman|frontwoman|solo|composer|rapper|crooner|virtuoso)\b"
)


def main() -> int:
    refresh = "--refresh" in sys.argv
    cache: dict[str, list[dict]] = {}
    if CACHE_PATH.is_file() and not refresh:
        try:
            cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            cache = {}

    drafts = collect_drafts()
    total_entries = sum(len(v) for v in drafts.values())
    print(f"draft birthday entries: {total_entries} across {len(drafts)} days", flush=True)

    wanted = sorted({name for entries in drafts.values() for name, _, _ in entries})
    pending = [name for name in wanted if name not in cache]
    print(f"names to look up: {len(pending)} of {len(wanted)} (rest cached)", flush=True)

    for start in range(0, len(pending), BATCH_SIZE):
        batch = pending[start : start + BATCH_SIZE]
        try:
            cache.update(lookup_batch(batch))
        except Exception as exc:
            print(f"  BATCH FAILED at {start}: {type(exc).__name__}: {exc}", flush=True)
            for name in batch:
                cache.setdefault(name, [])
        CACHE_PATH.write_text(json.dumps(cache, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"  looked up {min(start + BATCH_SIZE, len(pending))}/{len(pending)}", flush=True)
        time.sleep(REQUEST_PACING_SECONDS)

    unmatched = [name for name in wanted if not cache.get(name)]
    if unmatched:
        print(f"search fallback for {len(unmatched)} names SPARQL could not match", flush=True)
        for name in unmatched:
            found: list[dict] = []
            for variant in name_variants(name):
                try:
                    found = lookup_by_search(variant)
                except Exception as exc:
                    print(f"  fallback failed {variant}: {type(exc).__name__}", flush=True)
                    found = []
                if found:
                    break
            if found:
                cache[name] = found
        CACHE_PATH.write_text(json.dumps(cache, indent=1, ensure_ascii=False), encoding="utf-8")

    verified: dict[str, list[dict]] = {}
    rejected: list[dict] = []

    for (month, day) in sorted(drafts):
        for name, stated_year, band in drafts[(month, day)]:
            match = None
            for candidate in cache.get(name) or []:
                parsed = parse_dob(candidate.get("dob", ""))
                if not parsed:
                    continue
                year, cand_month, cand_day = parsed
                if (cand_month, cand_day) != (month, day):
                    continue
                if year != stated_year:
                    continue
                role_text = f"{candidate.get('description', '')} {candidate.get('occupations', '')}"
                if not MUSIC_DESC_RE.search(role_text):
                    continue
                match = (candidate, year)
                break

            if not match:
                rejected.append({
                    "day": f"{month:02d}-{day:02d}",
                    "name": name,
                    "stated_year": stated_year,
                    "candidates": [
                        f"{c.get('qid')} {c.get('dob')} {c.get('description')}"
                        for c in (cache.get(name) or [])
                    ],
                })
                continue

            candidate, year = match
            role = short_role(candidate.get("description") or candidate.get("occupations", ""))
            if band and ROLE_NOT_BAND_RE.search(band):
                fact = f"{year} - {band[0].upper()}{band[1:]} {name} was born."
            elif band:
                fact = f"{year} - {name} of {band} was born."
            elif role:
                fact = f"{year} - {role[0].upper()}{role[1:]} {name} was born."
            else:
                fact = f"{year} - {name} was born."

            verified.setdefault(f"{month:02d}-{day:02d}", []).append({
                "year": year,
                "name": name,
                "band": band,
                "qid": candidate["qid"],
                "description": candidate.get("description", ""),
                "fact": fact,
                "focus": bool(
                    FOCUS_RE.search(
                        f"{candidate.get('description', '')} "
                        f"{candidate.get('occupations', '')} {band}"
                    )
                ),
            })

    CACHE_PATH.write_text(json.dumps(cache, indent=1, ensure_ascii=False), encoding="utf-8")

    # On-format entries first, so trimming a long day keeps country/rock/pop.
    for key, items in verified.items():
        items.sort(key=lambda item: (not item["focus"], item["year"]))
        verified[key] = items[:MAX_PER_DAY]

    OUT_PATH.write_text(
        json.dumps(
            {"verified": verified, "rejected": rejected},
            indent=1,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    kept = sum(len(v) for v in verified.values())
    print(f"\nverified {kept} birthdays across {len(verified)} days", flush=True)
    print(f"rejected {len(rejected)} entries (date mismatch or not a music figure)", flush=True)
    print(f"wrote {OUT_PATH}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

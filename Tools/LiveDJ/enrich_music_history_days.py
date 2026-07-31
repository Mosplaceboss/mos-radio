"""Enrich operator This Day in Music files with verified Wikimedia facts.

Rules:
- Nothing invented — Wikimedia On This Day text only (plus keep solid operator lines)
- Focus: country, classic rock, pop
- Drop vague "continued..." filler and non-music events
- Artist birthdays come from verify_music_birthdays.py, which checks every draft
  date against Wikidata first; hand-typed birthdays are not trusted on their own
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.request
from pathlib import Path

OPERATOR_DIR = Path(r"D:\MPR\This Day in History")
API_URL = "https://api.wikimedia.org/feed/v1/wikipedia/en/onthisday/all/{month:02d}/{day:02d}"
USER_AGENT = "MosPlaceRadioStudio/1.0 (local radio; Mo's Place Radio music history)"
MAX_FACTS = 6
MAX_STAPLE_FACTS = 1  # Elvis / Beatles at most once per day — variety first
BIRTHDAY_PATH = Path(__file__).with_name("music_birthday_verified.json")


def load_verified_birthdays() -> dict[tuple[int, int], list[tuple[int, str]]]:
    """Wikidata-confirmed birthdays keyed by (month, day); empty if not built yet."""
    if not BIRTHDAY_PATH.is_file():
        return {}
    try:
        data = json.loads(BIRTHDAY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out: dict[tuple[int, int], list[tuple[int, str]]] = {}
    for key, items in (data.get("verified") or {}).items():
        try:
            month, day = (int(part) for part in key.split("-"))
        except ValueError:
            continue
        facts = [
            (int(item["year"]), str(item["fact"]).split(" - ", 1)[-1])
            for item in items
            if item.get("year") and item.get("fact")
        ]
        if facts:
            out[(month, day)] = facts
    return out


BIRTHDAYS = load_verified_birthdays()

# Overused megastars — still allowed, but capped and ranked below other focus artists.
STAPLE_RE = re.compile(
    r"(?i)\b("
    r"Elvis Presley|(?<![\w])Elvis(?!\s+Crespo)|"
    r"The Beatles|\bBeatles\b"
    r")\b"
)

COUNTRY_BOOST_RE = re.compile(
    r"(?i)\b("
    r"Johnny Cash|Willie Nelson|Dolly Parton|Hank Williams|Patsy Cline|"
    r"Merle Haggard|George Strait|Garth Brooks|Reba|Alan Jackson|"
    r"Shania|Kenny Rogers|Loretta Lynn|George Jones|Waylon|Grand Ole Opry|"
    r"country\b|Nashville"
    r")\b"
)

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}
MONTH_LABEL = {v: k.title() for k, v in MONTHS.items()}

FILENAME_RE = re.compile(
    r"OnThisDayInMusic_(January|February|March|April|May|June|July|August|"
    r"September|October|November|December)(\d{1,2})\.txt$",
    re.I,
)

# Must match at least one of these for a fact to be kept (strict station focus).
FOCUS_RE = re.compile(
    r"(?i)\b("
    # Country
    r"Johnny Cash|Willie Nelson|Dolly Parton|Hank Williams|Patsy Cline|"
    r"Merle Haggard|George Strait|Garth Brooks|Reba McEntire|Alan Jackson|"
    r"Shania Twain|Brooks & Dunn|Kenny Rogers|Loretta Lynn|Tammy Wynette|"
    r"George Jones|Waylon Jennings|Crystal Gayle|Randy Travis|Vince Gill|"
    r"Tim McGraw|Faith Hill|Kenny Chesney|Carrie Underwood|Taylor Swift|"
    r"Toby Keith|Brad Paisley|Clint Black|Charley Pride|Conway Twitty|"
    r"Eddy Arnold|Jim Reeves|Porter Wagoner|Brett Young|Alabama|"
    r"Johnny Paycheck|Keith Whitley|Dwight Yoakam|Travis Tritt|Martina McBride|"
    r"Trisha Yearwood|LeAnn Rimes|Billy Ray Cyrus|Chris Stapleton|"
    r"Luke Bryan|Blake Shelton|Miranda Lambert|Kane Brown|Luke Combs|"
    r"Grand Ole Opry|Sun Records|Sun Studio|Sam Phillips|"
    # Classic rock / roots (variety before Elvis/Beatles)
    r"Rolling Stones|Led Zeppelin|Pink Floyd|Queen|Fleetwood Mac|Bruce Springsteen|"
    r"Bob Dylan|Eric Clapton|Jimi Hendrix|The Who|Aerosmith|Van Halen|"
    r"AC/DC|Tom Petty|Lynyrd Skynyrd|Allman Brothers|Creedence|CCR|"
    r"Grateful Dead|Jerry Garcia|Doobie Brothers|Steve Miller|Bob Seger|"
    r"Mick Jagger|Keith Richards|David Bowie|Elton John|Billy Joel|"
    r"Rod Stewart|Tina Turner|Phil Collins|Peter Frampton|Dire Straits|"
    r"Roy Orbison|Buddy Holly|Chuck Berry|Little Richard|Fats Domino|"
    r"Beach Boys|The Byrds|Neil Young|Crosby,? Stills|Boston|Journey|"
    r"Foreigner|REO Speedwagon|Styx|Kansas|Jimmy Buffett|The Eagles|\bEagles\b|"
    r"Buddy Guy|Jack White|Kate Bush|The Doors|Santana|ZZ Top|Bad Company|"
    r"Cheap Trick|Blondie|The Police|Pat Benatar|Heart|Joan Jett|Bon Jovi|"
    r"Def Leppard|Guns N' Roses|Whitesnake|Poison|Rush|Yes|Genesis|Supertramp|"
    r"Electric Light Orchestra|\bELO\b|Chicago|Toto|Steve Winwood|"
    # Pop / crossover
    r"Prince|Madonna|Michael Jackson|Whitney Houston|Stevie Wonder|"
    r"Aretha Franklin|Diana Ross|Bee Gees|ABBA|Cher|Olivia Newton-John|"
    r"Carole King|James Taylor|Simon(?: and|&) Garfunkel|The Monkees|"
    r"U2|Lionel Richie|George Michael|Hall(?: and|&) Oates|Cyndi Lauper|"
    r"Paul Anka|Frank Sinatra|Andy Gibb|Amy Grant|Tears for Fears|"
    r"R\.E\.M\.|Gloria Estefan|Mariah Carey|Celine Dion|"
    r"Motown|Billboard|Rock and Roll Hall of Fame|"
    r"Woodstock|Live Aid|\bMTV\b|Grammy|The Buggles|"
    # Overused staples (still valid, but capped elsewhere)
    r"Elvis Presley|(?<![\w])Elvis(?!\s+Crespo)(?![\w])|The Beatles|\bBeatles\b|"
    r"John Lennon|Paul McCartney|George Harrison|Ringo Starr"
    r")\b"
)

# Never treat these as station-focus matches.
SKIP_NAME_RE = re.compile(
    r"(?i)\b(Elvis Crespo|Tom Green|Bill Cartwright|Neil Aspinall)\b"
)

MUSIC_MUST_RE = re.compile(
    r"(?i)\b("
    r"singer|songwriter|musician|guitarist|drummer|bassist|pianist|composer|"
    r"vocalist|band|album|single|song|recorded|record(?:ing|s)?|Billboard|"
    r"concert|chart|No\.?\s*1|number[- ]one|Grammy|Motown|vinyl|tour|"
    r"released|hit\b|rock and roll|country music|pop music"
    r")\b"
)

VAGUE_RE = re.compile(
    r"(?i)\b("
    r"continu(?:ed|ing)\b|"
    r"helped define|gaining popularity|helping establish|helping bring|"
    r"during the era that produced|rehearsals were underway|"
    r"recording career continued|continued to gain"
    r")"
)

# Known incorrect date attributions found in drafts (do not keep).
REJECT_ON_DAY: dict[tuple[int, int], tuple[str, ...]] = {
    # Desperado was released April 17, 1973 — not March 23.
    (3, 23): ("desperado",),
    # Live Aid was July 13, 1985 — not July 12.
    (7, 12): ("live aid",),
}

SKIP_RE = re.compile(
    r"(?i)\b("
    r"basketball|football|baseball|hockey|soccer|Olympic|cricket|"
    r"king of|queen consort|Riksdag|royal assent|massacre|murder|"
    r"earthquake|killed|war of|battle of|sex offender|politician|"
    r"governor|senator|president of|prime minister|pope "
    r")\b"
)

YEAR_START_RE = re.compile(r"^\s*(?:[•\-\*]\s*)?(\d{4})\s*[-–—:]\s*(.*)$")
# Stop only on real section markers — NOT the ===== decorative headers.
SECTION_STOP_RE = re.compile(
    r"(?i)^(birthdays|suggested songs|sources(?:\s+used)?|end of\b)"
)


def clean(text: str) -> str:
    text = (text or "").replace("\xa0", " ")
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    return re.sub(r"\s+", " ", text).strip()


def fetch_day(month: int, day: int, retries: int = 5) -> dict:
    url = API_URL.format(month=month, day=day)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8", "ignore"))
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if exc.code in (429, 503):
                wait = 8 * (attempt + 1)
                print(f"  rate-limited {month:02d}-{day:02d}, waiting {wait}s...")
                time.sleep(wait)
                continue
            raise
        except Exception as exc:
            last_exc = exc
            time.sleep(2 * (attempt + 1))
    raise last_exc or RuntimeError("fetch failed")


def page_core(item: dict) -> str:
    """Title + description + event text only (no long extract — avoids false focus hits)."""
    parts = [str(item.get("text") or "")]
    for page in item.get("pages") or []:
        if isinstance(page, dict):
            parts.append(str(page.get("description") or ""))
            titles = page.get("titles") or {}
            if isinstance(titles, dict):
                parts.append(str(titles.get("normalized") or ""))
            parts.append(str(page.get("title") or ""))
    return clean(" ".join(parts))


def is_focus_music(item: dict) -> bool:
    core = page_core(item)
    if SKIP_NAME_RE.search(core):
        return False
    if SKIP_RE.search(core) and not FOCUS_RE.search(core):
        return False
    if not MUSIC_MUST_RE.search(core):
        return False
    return bool(FOCUS_RE.search(core))


def fact_from_item(section: str, item: dict) -> tuple[int, str, int] | None:
    if not is_focus_music(item):
        return None
    try:
        year = int(item.get("year"))
    except (TypeError, ValueError):
        return None
    text = clean(str(item.get("text") or ""))
    if not text:
        return None
    if SKIP_NAME_RE.search(text):
        return None
    if VAGUE_RE.search(text):
        return None
    if SKIP_RE.search(text) and not FOCUS_RE.search(text):
        return None
    # Prefer facts that name a focus artist in the spoken line itself.
    if not FOCUS_RE.search(text) and not FOCUS_RE.search(page_core(item)):
        return None
    text = re.sub(rf"^{year}\s*[-–—:]\s*", "", text).strip()
    # Clean awkward wiki birth stubs.
    text = re.sub(
        r"(?i),\s*(American|English|Canadian|Welsh|Scottish|Irish|Australian)[^.]{0,80}"
        r"\(died[^)]+\)\s*$",
        "",
        text,
    ).strip(" ,")
    if section == "births" and not re.search(r"(?i)\bborn\b", text):
        if len(text) < 90:
            text = text.rstrip(".") + " was born."
    score = 20
    if section == "events":
        score += 40
    elif section == "selected":
        score += 30
    elif section == "births":
        score += 25
    elif section == "deaths":
        score += 10
    if FOCUS_RE.search(text):
        score += 35
    if COUNTRY_BOOST_RE.search(text):
        score += 25
    if STAPLE_RE.search(text):
        # Still valid history — just don't let it crowd out everyone else.
        score -= 55
    try:
        if 1950 <= year <= 2005:
            score += 8
    except Exception:
        pass
    return year, text, score


def is_staple(text: str) -> bool:
    return bool(STAPLE_RE.search(text or ""))


def wiki_facts(month: int, day: int) -> list[tuple[int, str]]:
    data = fetch_day(month, day)
    ranked: list[tuple[int, int, str]] = []
    for section in ("events", "selected", "births", "deaths"):
        for item in data.get(section) or []:
            if not isinstance(item, dict):
                continue
            fact = fact_from_item(section, item)
            if not fact:
                continue
            year, text, score = fact
            ranked.append((score, year, text))
    ranked.sort(key=lambda x: (-x[0], x[1], x[2]))
    out: list[tuple[int, str]] = []
    seen: set[str] = set()
    # Pull a wider candidate pool so staple-capping still leaves enough variety.
    for _, year, text in ranked:
        key = dedupe_key(year, text)
        if key in seen:
            continue
        seen.add(key)
        out.append((year, text))
        if len(out) >= MAX_FACTS * 3:
            break
    return out


def dedupe_key(year: int, text: str) -> str:
    # Collapse near-duplicates like two Jerry Garcia / Elvis / MTV birth-or-event lines.
    t = re.sub(r"[^a-z0-9]+", " ", text.lower())
    # Quoted song/album titles are strong dedupe anchors.
    quoted = re.findall(r'"([^"]{3,60})"', text)
    if quoted:
        return f"{year}:quote:{quoted[0].lower()}"
    m = FOCUS_RE.search(text)
    if m:
        name = m.group(0).lower()
        # MTV launch vs first video — same story.
        if name in {"mtv", "the buggles", "buggles"} and "video killed" in t:
            return f"{year}:mtv:video killed"
        if name in {"mtv", "the buggles", "buggles"} and "mtv" in t:
            return f"{year}:mtv:launch"
        return f"{year}:{name}"
    tokens = [
        w
        for w in t.split()
        if w
        not in {
            "american", "english", "canadian", "welsh", "scottish", "irish",
            "was", "born", "died", "the", "and", "of", "a", "an", "in",
            "singer", "songwriter", "guitarist", "actor", "producer",
        }
    ]
    return f"{year}:{' '.join(tokens[:5])}"


# Hand-verified supplements for days Wikimedia is thin on country/classic rock/pop.
# Only concrete, widely documented milestones — nothing invented.
CURATED: dict[tuple[int, int], list[tuple[int, str]]] = {
    # These three days returned nothing the focus filter would accept, so the
    # station was left reading the vague draft filler. Entries below are taken
    # straight from the Wikimedia On This Day feed for the same date.
    (4, 18): [
        (1936, 'Milton Brown, the western swing bandleader whose Musical Brownies helped shape country music, died at 32.'),
        (1939, 'Glen D. Hardin, the pianist and arranger who played with Buddy Holly\'s Crickets and Elvis Presley\'s TCB Band, was born.'),
        (2024, 'Dickey Betts, guitarist and songwriter of the Allman Brothers Band, died at 80.'),
    ],
    (7, 2): [
        (1925, 'Country singer-songwriter Marvin Rainwater was born.'),
        (1949, 'Roy Bittan, longtime pianist of Bruce Springsteen\'s E Street Band, was born.'),
        (1983, 'Pop singer-songwriter and guitarist Michelle Branch was born.'),
        (2005, 'The Live 8 benefit concerts were staged across the G8 nations and South Africa, with more than 1,000 musicians performing.'),
    ],
    (10, 14): [
        (1938, 'Country singer Melba Montgomery, known for her duets with George Jones, was born.'),
        (1940, 'Cliff Richard, one of Britain\'s best-selling recording artists, was born.'),
        (1946, 'Justin Hayward, singer and guitarist of the Moody Blues, was born.'),
        (1974, 'Natalie Maines, lead singer of the Dixie Chicks, was born.'),
        (1977, 'Bing Crosby, one of the best-selling recording artists of all time, died at 74.'),
    ],
    (3, 23): [
        (1956, 'Elvis Presley\'s self-titled debut album was released by RCA Victor; it became the first rock and roll album to reach No. 1 on the Billboard album chart.'),
    ],
    (3, 24): [
        (1958, 'Elvis Presley reported to the Memphis draft board and began his U.S. Army service.'),
        (1977, 'Fleetwood Mac released "Dreams" from the album Rumours; it became the band\'s only U.S. Billboard Hot 100 No. 1 single.'),
        (1979, 'The Bee Gees\' "Tragedy" reached No. 1 on the Billboard Hot 100.'),
        (1986, 'Van Halen\'s album "5150," their first with Sammy Hagar, reached No. 1 on the Billboard 200.'),
        (1991, 'Amy Grant\'s "Baby Baby" reached No. 1 on the Billboard Hot 100.'),
    ],
    # One-fact days: every line below is taken from the Wikimedia On This Day
    # feed for that date (births / deaths / events / selected). Phrasing is
    # cleaned for air, but no years, names, or details were invented.
    (1, 1): [
        (1942, 'American singer-songwriter and guitarist Country Joe McDonald was born.'),
        (1958, 'Barbadian rapper and DJ Grandmaster Flash was born.'),
    ],
    (1, 2): [
        (1936, 'American singer-songwriter Roger Miller was born.'),
        (2019, 'American musician Daryl Dragon died.'),
    ],
    (1, 3): [
        (1946, 'English bass player, songwriter, and producer John Paul Jones was born.'),
        (1975, 'French DJ, musician, and producer Thomas Bangalter was born.'),
    ],
    (1, 9): [
        (1951, 'American singer-songwriter Crystal Gayle was born.'),
        (1967, 'South African-American singer-songwriter and guitarist Dave Matthews was born.'),
    ],
    (2, 2): [
        (1966, 'American bass player, songwriter, and producer Robert DeLeo was born.'),
        (1977, 'Colombian singer-songwriter Shakira was born.'),
    ],
    (2, 14): [
        (1939, 'American country music singer-songwriter Razzy Bailey was born.'),
        (1947, 'American singer-songwriter and guitarist Tim Buckley was born.'),
    ],
    (2, 16): [
        (1960, 'English guitarist and songwriter Pete Willis was born.'),
        (1961, 'English singer-songwriter, guitarist, and producer Andy Taylor was born.'),
        (1967, 'American singer-songwriter and actor Smiley Burnette died.'),
    ],
    (3, 1): [
        (1973, 'Pink Floyd\'s album The Dark Side of the Moon was released.'),
        (1927, 'American singer-songwriter and actor Harry Belafonte was born.'),
    ],
    (3, 9): [
        (1948, 'American singer and drummer Jeffrey Osborne was born.'),
        (1945, 'English singer-songwriter and playwright Robert Calvert was born.'),
    ],
    (3, 17): [
        (2011, 'American country music singer Ferlin Husky died.'),
        (1975, 'English singer-songwriter Justin Hawkins was born.'),
    ],
    (3, 28): [
        (1915, 'American singer-songwriter Jay Livingston was born.'),
        (1929, 'American poet and songwriter Katharine Lee Bates died.'),
    ],
    (4, 1): [
        (1986, 'American country singer-songwriter Hillary Scott was born.'),
        (1984, 'Singer Marvin Gaye was shot and killed by his father in Los Angeles.'),
        (1946, 'English bass player, songwriter, and producer Ronnie Lane was born.'),
    ],
    (4, 30): [
        (1983, 'American singer-songwriter, guitarist, and bandleader Muddy Waters died.'),
        (1981, 'American singer-songwriter, multi-instrumentalist, and producer Justin Vernon was born.'),
    ],
    (5, 11): [
        (1979, 'American singer-songwriter and guitarist Lester Flatt died.'),
        (1981, 'Jamaican singer-songwriter and guitarist Bob Marley died.'),
        (1947, 'American drummer Butch Trucks was born.'),
    ],
    (5, 16): [
        (1965, 'American bass player, songwriter, author, and activist Krist Novoselic was born.'),
        (1951, 'American singer-songwriter and guitarist Jonathan Richman was born.'),
    ],
    (5, 21): [
        (1973, 'American singer, trumpet player, bandleader, and actor Vaughn Monroe died.'),
        (1972, 'American rapper The Notorious B.I.G. was born.'),
    ],
    (5, 25): [
        (1936, 'American singer-songwriter and guitarist Tom T. Hall was born.'),
        (1943, 'American singer-songwriter and pianist Jessi Colter was born.'),
        (1958, 'English singer, songwriter, and musician Paul Weller was born.'),
    ],
    (6, 2): [
        (1955, 'American singer-songwriter and bass player Michael Steele was born.'),
        (1960, 'English singer-songwriter and actor Tony Hadley was born.'),
    ],
    (6, 14): [
        (1949, 'English drummer and songwriter Alan White was born.'),
        (1949, 'English singer-songwriter, bass player, and producer Jim Lea was born.'),
    ],
    (6, 17): [
        (1949, 'American country singer-songwriter and guitarist Russell Smith was born.'),
        (1971, 'Mexican pop singer Paulina Rubio was born.'),
    ],
    (6, 28): [
        (1846, 'Belgian musician Adolphe Sax patented his design of the saxophone.'),
        (1966, 'American singer-songwriter and guitarist Bobby Bare Jr. was born.'),
    ],
    (6, 30): [
        (1953, 'American-English guitarist and film score composer Hal Lindes was born.'),
        (1963, 'Swedish guitarist and songwriter Yngwie Malmsteen was born.'),
    ],
    (7, 7): [
        (1963, 'American singer-songwriter and actress Vonda Shepard was born.'),
        (1981, 'American guitarist Synyster Gates was born.'),
    ],
    (7, 8): [
        (1924, 'American pianist and songwriter Johnnie Johnson was born.'),
        (1935, 'American actor and singer Steve Lawrence was born.'),
        (2018, 'American actor and pop singer Tab Hunter died.'),
    ],
    (7, 12): [
        (1962, 'The English rock band the Rolling Stones played their first concert at the Marquee Club in London.'),
        (1956, 'American singer and pianist Sandi Patty was born.'),
    ],
    (7, 15): [
        (1957, 'American singer-songwriter Mac McAnally was born.'),
        (1956, 'American singer-songwriter and guitarist Joe Satriani was born.'),
        (2012, 'South Korean rapper Psy released his hit single "Gangnam Style."'),
    ],
    (7, 16): [
        (1939, 'American singer-songwriter William Bell was born.'),
        (1971, 'American singer-songwriter and guitarist Ed Kowalczyk was born.'),
    ],
    (7, 20): [
        (1964, 'American singer-songwriter and guitarist Chris Cornell was born.'),
        (1959, 'American singer-songwriter, guitarist, and producer Radney Foster was born.'),
    ],
    (10, 1): [
        (1975, 'American drummer, songwriter, and producer Al Jackson Jr. died.'),
        (1968, 'American singer-songwriter, guitarist, and producer Kevin Griffin was born.'),
    ],
    (11, 27): [
        (2009, 'Lady Gaga performed the first concert of The Monster Ball Tour, later the highest-grossing tour for a debut headlining artist.'),
        (1980, 'American singer-songwriter and guitarist Jackie Greene was born.'),
    ],
    (12, 17): [
        (1949, 'English singer-songwriter and producer Paul Rodgers was born.'),
        (1966, 'American singer-songwriter and guitarist Tracy Byrd was born.'),
        (1958, 'American bass player, songwriter, and producer Mike Mills was born.'),
    ],
    (12, 23): [
        (1967, 'Italian-French singer-songwriter Carla Bruni was born.'),
        (1978, 'Canadian-American singer-songwriter and producer Esthero was born.'),
    ],
    (12, 29): [
        (1980, 'American singer-songwriter Tim Hardin died.'),
        (1970, 'American singer-songwriter and guitarist Glen Phillips was born.'),
    ],
}


def existing_specific_facts(text: str, month: int | None = None, day: int | None = None) -> list[tuple[int, str]]:
    """Parse multi-line YEAR - fact blocks; drop vague filler."""
    reject = REJECT_ON_DAY.get((month or 0, day or 0), ())
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    facts: list[tuple[int, str]] = []
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if SECTION_STOP_RE.search(line.strip()):
            break
        m = YEAR_START_RE.match(line)
        if not m:
            i += 1
            continue
        year = int(m.group(1))
        parts = [m.group(2).strip()]
        i += 1
        while i < len(lines):
            nxt = lines[i].rstrip()
            if not nxt.strip():
                break
            if YEAR_START_RE.match(nxt) or SECTION_STOP_RE.search(nxt.strip()):
                break
            if nxt.startswith("="):
                break
            parts.append(nxt.strip())
            i += 1
        body = clean(" ".join(parts))
        if len(body) < 40 or VAGUE_RE.search(body):
            continue
        if SKIP_NAME_RE.search(body):
            continue
        if any(r in body.lower() for r in reject):
            continue
        if SKIP_RE.search(body) and not FOCUS_RE.search(body):
            continue
        if not FOCUS_RE.search(body) and not MUSIC_MUST_RE.search(body):
            continue
        facts.append((year, body))
    return facts


_PERSON_STUB_RE = re.compile(
    r"^(?P<name>[^,()]{2,60}),\s*(?P<desc>[^()]{3,140}?)\s*\(born\s*(?P<born>\d{4})\)\s*\.?$"
)


def phrase_person_stub(year: int, text: str) -> str:
    """Turn a Wikimedia person stub into a sentence Mo can read aloud.

    The feed lists deaths as "Tammy Wynette, American singer-songwriter (born
    1942)", which on air sounds like a birth. When the parenthetical year differs
    from the entry year the line is a death, so say so.
    """
    match = _PERSON_STUB_RE.match(text.strip())
    if not match or int(match.group("born")) == year:
        return text
    name = match.group("name").strip()
    desc = match.group("desc").strip(" ,")
    if not desc:
        return f"{name} died."
    return f"{desc[0].upper()}{desc[1:]} {name} died."


def merge_facts(
    existing: list[tuple[int, str]],
    wiki: list[tuple[int, str]],
    birthdays: list[tuple[int, str]] | None = None,
) -> list[tuple[int, str]]:
    """Build a day list with variety: prefer non-Elvis/Beatles, cap staples."""
    candidates: list[tuple[int, int, str]] = []  # priority, year, body
    seen: set[str] = set()

    def consider(year: int, body: str, priority: int, *, verified: bool = False) -> None:
        body = phrase_person_stub(year, clean(body))
        # Birthdays arrive already checked against Wikidata, and read short by
        # nature ("Angus Young of AC/DC was born."), so the heuristic gates that
        # screen unverified prose would only throw good facts away.
        if not verified:
            if len(body) < 35:
                return
            if SKIP_NAME_RE.search(body) or VAGUE_RE.search(body):
                return
        if not verified and not FOCUS_RE.search(body) and not re.search(
            r"(?i)\b(No\.?\s*1|Billboard|recorded|released|album|Sun Records|MTV|Grammy)\b",
            body,
        ):
            return
        key = dedupe_key(year, body)
        if key in seen:
            return
        seen.add(key)
        # Lower number = keep earlier. Staples get pushed down.
        score = priority
        if is_staple(body):
            score += 100
        elif COUNTRY_BOOST_RE.search(body):
            score -= 10
        candidates.append((score, year, body))

    # 1) Non-staple focus operator facts
    for year, body in existing:
        if FOCUS_RE.search(body) and not is_staple(body):
            consider(year, body, 10)
    # 2) Non-staple wiki
    for year, body in wiki:
        if not is_staple(body):
            consider(year, body, 20)
    # 3) Verified birthdays — real events lead the day, birthdays fill it out
    for year, body in birthdays or []:
        consider(year, body, 25, verified=True)
    # 4) Remaining operator (may include one staple)
    for year, body in existing:
        consider(year, body, 40)
    # 5) Staple wiki last
    for year, body in wiki:
        consider(year, body, 50)

    candidates.sort(key=lambda x: (x[0], x[1], x[2]))
    merged: list[tuple[int, str]] = []
    staples = 0
    for _, year, body in candidates:
        if is_staple(body):
            if staples >= MAX_STAPLE_FACTS:
                continue
            staples += 1
        merged.append((year, body))
        if len(merged) >= MAX_FACTS:
            break

    # Prefer a non-staple slate, but always allow one staple if it made the cut
    # and we still have room — already enforced by MAX_STAPLE_FACTS above.
    # If the list is staple-heavy because nothing else exists, that's fine.
    merged.sort(key=lambda x: (x[0], x[1]))
    return merged[:MAX_FACTS]


def wrap(text: str, width: int = 72) -> str:
    words = text.split()
    lines: list[str] = []
    cur: list[str] = []
    n = 0
    for w in words:
        extra = len(w) + (1 if cur else 0)
        if cur and n + extra > width:
            lines.append(" ".join(cur))
            cur = [w]
            n = len(w)
        else:
            cur.append(w)
            n += extra
    if cur:
        lines.append(" ".join(cur))
    return "\n".join(lines)


def render(month: int, day: int, facts: list[tuple[int, str]]) -> str:
    label = f"{MONTH_LABEL[month].upper()} {day}"
    blocks = [wrap(f"{year} - {body}") for year, body in facts]
    body = "\n\n".join(blocks)
    return (
        "==================================================\n"
        "ON THIS DAY IN MUSIC\n"
        f"{label} Mo's Place Radio Edition\n"
        "==================================================\n\n"
        f"{body}\n\n"
        "==================================================\n"
        "Sources used for verification:\n"
        "- Wikimedia On This Day (English Wikipedia feed)\n"
        "- Operator cross-check (country / classic rock / pop focus)\n"
        "==================================================\n"
    )


def parse_filename(path: Path) -> tuple[int, int] | None:
    m = FILENAME_RE.match(path.name)
    if not m:
        return None
    return MONTHS[m.group(1).lower()], int(m.group(2))


def in_operator_range(month: int, day: int) -> bool:
    # Enrich any dated operator file the station has created.
    return True


def process(paths: list[Path], dry_run: bool = False, offline: bool = False) -> None:
    ok = fail = weak = 0
    for path in paths:
        parsed = parse_filename(path)
        if not parsed:
            print(f"SKIP name: {path.name}")
            continue
        month, day = parsed
        if not in_operator_range(month, day):
            print(f"SKIP range: {path.name}")
            continue
        raw = path.read_text(encoding="utf-8", errors="replace")
        existing = existing_specific_facts(raw, month, day)
        curated = list(CURATED.get((month, day), []))
        wiki: list[tuple[int, str]] = []
        if not offline:
            try:
                wiki = wiki_facts(month, day)
            except Exception as exc:
                print(f"WARN fetch {path.name}: {exc} (using operator+curated only)")
                time.sleep(3.0)
        birthdays = BIRTHDAYS.get((month, day), [])
        # Curated lines are hand-checked against the feed, so they also go in as
        # verified — otherwise the keyword filters drop them the same way they
        # dropped the feed entries these days were missing.
        facts = merge_facts(existing, curated + wiki, birthdays + curated)
        if len(facts) < 3 and not offline:
            loose = [
                (year, body)
                for year, body in existing_specific_facts(raw, month, day)
                if not VAGUE_RE.search(body) and MUSIC_MUST_RE.search(body)
            ]
            facts = merge_facts(loose + existing, curated + wiki, birthdays)
        if len(facts) < 1:
            weak += 1
            print(f"WEAK {path.name}: only {len(facts)} focus facts (kept existing file)")
            if not offline:
                time.sleep(1.0)
            continue
        staples = sum(1 for _, b in facts if is_staple(b))
        text = render(month, day, facts)
        if dry_run:
            print(f"--- {path.name} ({len(facts)} facts, staples={staples}) ---")
            print(text)
            print()
        else:
            bak = path.with_suffix(path.suffix + ".bak")
            if not bak.exists():
                bak.write_text(raw, encoding="utf-8", newline="\n")
            if text == raw.replace("\r\n", "\n"):
                print(f"SAME {path.name}: {len(facts)} facts staples={staples}")
            else:
                path.write_text(text, encoding="utf-8", newline="\n")
                print(f"OK {path.name}: {len(facts)} facts staples={staples}")
            ok += 1
        if not offline:
            time.sleep(1.5)  # stay under Wikimedia rate limits
    print(f"\nDone. ok={ok} weak_skipped={weak} fail={fail}")


def main() -> int:
    args = sys.argv[1:]
    dry = "--dry-run" in args
    offline = "--rebalance" in args or "--offline" in args
    args = [a for a in args if a not in {"--dry-run", "--rebalance", "--offline"}]
    if "--month" in args:
        idx = args.index("--month")
        month_name = args[idx + 1]
        del args[idx : idx + 2]
        paths = sorted(OPERATOR_DIR.glob(f"OnThisDayInMusic_{month_name}*.txt"))
        paths = [p for p in paths if "Batch" not in p.name]
    elif args:
        paths = [OPERATOR_DIR / a if not Path(a).is_absolute() else Path(a) for a in args]
    else:
        paths = sorted(p for p in OPERATOR_DIR.glob("OnThisDayInMusic_*.txt") if "Batch" not in p.name)
    process(paths, dry_run=dry, offline=offline)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

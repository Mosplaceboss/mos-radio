"""Rolling break memory for every LiveDJ personality.

Producer asks this module what a break should focus on before the prompt is
built, then records what actually aired. History is per DJ, with station-wide
memory for shared announcements so the next host does not repeat the same
explanation. Topics are tracked by subject, not by exact sentence.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

DEFAULT_STATE = Path(__file__).resolve().parents[1] / "State" / "break_continuity.json"
# When this file is copied to D:\MPR\Engines\LiveDJ\Scripts, parents[1] is the
# LiveDJ engine root and State/ sits beside Scripts/. The workspace copy keeps
# the same relative layout under Tools/ so tests can point at a temp file.

KEEP_BREAKS = 16
KEEP_HOURS = 36
TOO_SOON = timedelta(hours=3)
MAX_HEAVY = 1

_STOP = frozenset(
    """
    that this with from your youre just about have been were they them then than
    into over also more some when what where which would could should really very
    the and for but not are was its it's it's a an of to in on at it we our
    you you're day days month national international world awareness
    """.split()
)

_OPENERS = (
    ("youre_still_here", re.compile(r"(?i)^you(?:'re| are) still here\b")),
    ("hey_there", re.compile(r"(?i)^hey there\b")),
    ("hey_everyone", re.compile(r"(?i)^hey everyone\b")),
    ("hey_friends", re.compile(r"(?i)^hey friends\b")),
    ("hey_folks", re.compile(r"(?i)^hey folks\b")),
)

_CLOSINGS = (
    ("love_to_hear", re.compile(r"(?i)\blove to hear from you\b")),
    ("let_us_know", re.compile(r"(?i)\blet us know what you think\b")),
    ("click_community", re.compile(r"(?i)\bclick(?:ing)?\s+community\b")),
    ("request_song", re.compile(r"(?i)\b(?:request a song|if you(?:'ve| have) got a request|if you have a request)\b")),
)

_MUSIC_RE = re.compile(
    r"(?i)\b(?:coming up|back to the music|still ahead|in the mix|up next)\b"
)
_SONG_RE = re.compile(r"(?i)\bcoming up,?\s+([^.]{3,80})")

_MUST_RANK = {"birthday": 0, "question": 1, "fun_day": 2, "announcement": 3}
_OPTIONAL_RANK = {
    "friends": 0,
    "farmstand": 1,
    "engagement": 2,
    "talking": 3,
    "personal": 4,
    "books": 5,
    "dogs": 6,
    "rss": 7,
    "fun_day": 8,
    "announcement": 9,
}

_CLOSE_EVENTS = {"handoff", "show close", "final half hour"}

_SKIP_TEXT = {
    "friends": (
        "FRIENDS EPISODE (skip on this break):\n"
        "friends_episode: none\n\n"
        "FRIENDS RULES:\n"
        "- Do NOT mention Friends or a last-night episode on this break."
    ),
    "books": (
        "BOOKS (skip on this break):\n"
        "- Do NOT mention a book on this break."
    ),
    "dogs": (
        "DOG (skip on this break):\n"
        "- Do NOT mention the dog on this break."
    ),
    "personal": (
        "PERSONAL TOPIC (skip on this break):\n"
        "personal_topic: none\n\n"
        "- Do NOT add a personal aside on this break."
    ),
    "engagement": (
        "LISTENER QUESTION (skip on this break):\n"
        "- Do NOT ask a listener question or add a call to action on this break."
    ),
    "talking": (
        "LOCAL TALKING POINT (skip on this break):\n"
        "- Do NOT add a local place or event on this break."
    ),
    "farmstand": (
        "FARM STAND (skip on this break):\n"
        "farmstand: none\n"
        "- Do NOT mention the Bakehouse on this break."
    ),
    "question": (
        "QUESTION OF THE DAY (skip on this break):\n"
        "- Do NOT ask the question of the day on this break. Save it for a later break."
    ),
    "birthday": (
        "BIRTHDAYS (skip on this break):\n"
        "- Do NOT read birthdays on this break. A later break will."
    ),
    "announcement": (
        "COMMUNITY ANNOUNCEMENTS (skip on this break):\n"
        "community_announcements: []\n"
        "- Do NOT read a community announcement on this break."
    ),
    "rss": (
        "No extra feed topic on this break. Stay with the one subject already chosen. "
        "Do not add a second headline or local story."
    ),
    "fun_day": (
        "FUN / NATIONAL DAYS (skip on this break):\n"
        "fun_days: none\n"
        "- Do NOT mention today's observance or novelty day on this break."
    ),
}


def make_candidate(
    family: str,
    key: str,
    label: str,
    *,
    must: bool = False,
    heavy: bool = True,
    solemn: bool = False,
    shared: bool = False,
    people: list[str] | None = None,
) -> dict[str, Any]:
    clean_key = _norm_key(key or label)
    names = []
    for person in people or []:
        name = " ".join(str(person or "").split()).strip()
        if name and name.casefold() not in {item.casefold() for item in names}:
            names.append(name)
    item = {
        "family": str(family or "").strip().lower(),
        "key": clean_key,
        "label": " ".join(str(label or key or "").split()).strip(),
        "must": bool(must),
        "heavy": bool(heavy),
        "solemn": bool(solemn),
        "shared": bool(shared),
    }
    if names:
        item["people"] = names
    return item


def candidate_id(item: dict[str, Any]) -> str:
    return f"{item.get('family')}:{item.get('key')}"


class BreakPlan:
    def __init__(
        self,
        candidates: list[dict[str, Any]],
        modes: dict[str, str],
        ending: str,
        *,
        avoid_openers: list[str] | None = None,
        avoid_closings: list[str] | None = None,
        already: list[str] | None = None,
        avoid_songs: list[str] | None = None,
        specialty: bool = False,
        avoid_opening_fingerprints: list[str] | None = None,
        avoid_closing_fingerprints: list[str] | None = None,
    ) -> None:
        self.candidates = list(candidates)
        self.modes = dict(modes)
        self.ending = ending or "music"
        self.avoid_openers = list(avoid_openers or [])
        self.avoid_closings = list(avoid_closings or [])
        self.already = list(already or [])
        self.avoid_songs = list(avoid_songs or [])
        self.specialty = specialty
        self.avoid_opening_fingerprints = list(avoid_opening_fingerprints or [])
        self.avoid_closing_fingerprints = list(avoid_closing_fingerprints or [])

    @property
    def preferred_cta(self) -> str:
        if self.ending == "community":
            return "community"
        if self.ending == "bakehouse":
            return "bakehouse"
        if self.ending == "request":
            return "request"
        return ""

    def mode_for(self, family: str, key: str = "") -> str:
        family_name = str(family or "").strip().lower()
        matches = [
            item
            for item in self.candidates
            if item.get("family") == family_name
            and (not key or item.get("key") == _norm_key(key))
        ]
        if not matches:
            return "absent"
        found = [self.modes.get(candidate_id(item), "skip") for item in matches]
        if "full" in found:
            return "full"
        if "reminder" in found:
            return "reminder"
        return "skip"

    def kept(self, mode: str = "") -> list[dict[str, Any]]:
        wanted = {mode} if mode else {"full", "reminder"}
        return [
            item
            for item in self.candidates
            if self.modes.get(candidate_id(item), "skip") in wanted
        ]

    @property
    def skipped_families(self) -> set[str]:
        families = {str(item.get("family") or "") for item in self.candidates}
        return {family for family in families if family and self.mode_for(family) == "skip"}

    @property
    def heavy_focus(self) -> bool:
        return any(item.get("heavy") for item in self.kept())

    @property
    def direction(self) -> str:
        if self.specialty:
            return "specialty"
        kept = self.kept()
        if not kept:
            return "music"
        return str(kept[0].get("family") or "music")

    @property
    def required_mentions(self) -> list[str]:
        found: list[str] = []

        def add(value: str) -> None:
            name = " ".join(str(value or "").split()).strip()
            if name and name.casefold() not in {item.casefold() for item in found}:
                found.append(name)

        for item in self.kept():
            for person in item.get("people") or []:
                add(str(person))
            if str(item.get("family") or "") == "birthday":
                label = str(item.get("label") or "").strip()
                if label.casefold() not in {"listener birthdays", "birthdays"}:
                    add(label)
        return found

    def _focus_sentence(self, kept: list[dict[str, Any]]) -> str:
        if self.specialty:
            return (
                "Stay on this scheduled segment. Do not add a second story, a personal bit, "
                "a dog joke, or a website closer."
            )
        if not kept:
            return (
                "A relaxed music break in this host's own voice. Not a one-line announcement. "
                "Use the songs and facts supplied in this prompt. Say why something fits, "
                "what it reminds you of, or how the hour feels. "
                "You do not have to introduce yourself, and you do not have to name the next song. "
                "If you name a song, it has to be part of the thought. Do not end on a slogan."
            )
        if len(kept) > 1:
            labels = ", ".join(str(item.get("label") or item.get("family")) for item in kept)
            return (
                f"{labels}. Only if they belong in the same thought. "
                "Do not force a connection, and do not add anything else."
            )
        item = kept[0]
        family = str(item.get("family") or "")
        label = str(item.get("label") or family)
        people = [str(name).strip() for name in (item.get("people") or []) if str(name).strip()]
        if family == "birthday":
            who = ", ".join(people) if people else label
            return (
                f"A short birthday for {who}, in this host's voice. "
                f"Say happy birthday first, then the name: Happy birthday to {who}. "
                "Never say the name before happy birthday, and never say the name and then tack the wish on. "
                "Do not say from all of us. "
                "The birthday is the whole break, not one sentence inside another story. "
                "Do not replace it with a toast or a slogan, and do not mention the dog."
            )
        if self.modes.get(candidate_id(item)) == "reminder":
            return (
                f"A short reminder of {label}. Do not explain it again, and do not add a second subject. "
                "Then back to the music."
            )
        if family == "dogs":
            return (
                f"One short booth moment about {label}. Stay with the dog. "
                "Do not pivot into a song list or a toast."
            )
        if family == "fun_day":
            if item.get("solemn"):
                return (
                    f"{label}. This is a serious observance. Use the supplied note to say "
                    "what the day recognizes, in this host's voice, warm and respectful. "
                    "One real observation. Do not joke, do not invent a statistic or a personal story, "
                    "and do not give medical advice. Do not put a song title or a catchphrase "
                    "in the same breath."
                )
            return (
                f"{label}. Use the supplied note and say what the day actually is. "
                "A couple of natural sentences in this host's voice. "
                "Do not stop after the name, and do not finish with a slogan."
            )
        return (
            f"{label}. Develop it from the facts supplied for it — a reaction, a short story, "
            "or why it matters to a listener. Then the music, if it fits. "
            "Do not stop after naming it, and do not finish with a slogan."
        )

    @property
    def continuity_block(self) -> str:
        kept = self.kept()
        focus = self._focus_sentence(kept)
        lines = [
            "BREAK FOCUS (every DJ — this decides the break; do not cover every available topic):",
            f"- This break: {focus}",
            "- Keep this host's own voice, humor, and interests. Do not slip into a generic announcer.",
            "- Talk like a person between songs. Develop the subject you were given. No news-reader list.",
            "- Do not invent a bridge between unrelated subjects. One subject is better than a forced segue.",
            "- Do not add filler just to make the break longer.",
            "- Do not close with a generic toast, slogan, or \"here's to another year\" line.",
        ]
        if self.direction == "birthday":
            lines.append(
                "- Say the birthday inside the break. Do not make it the only sentence, and do not stop after it."
            )
            lines.append("- Do not mention a dog. A toast is not a birthday greeting.")
        elif self.direction != "dogs":
            lines.append("- Do not mention the dog unless this break's subject is the dog.")
        kept_solemn = any(item.get("solemn") for item in kept)
        if self.direction == "fun_day" and kept_solemn:
            lines.append(
                "- Do not name a song or artist in this break, and do not add a catchphrase."
            )
        elif self.direction == "music":
            lines.append(
                "- A song mention has to say something about the song or the hour. "
                "Do not use \"we've got X coming up\" as the whole break."
            )
        elif self.direction not in {"specialty", "birthday"}:
            lines.append(
                "- Finish the subject first. One look-ahead song may follow if it connects. "
                "Do not add \"just for good measure\" or a slogan after it."
            )
        if self.already:
            lines.append(
                "- Already discussed recently: "
                + "; ".join(self.already[:8])
                + ". Do not retell those."
            )
        reminders = [
            str(item.get("label") or "")
            for item in kept
            if self.modes.get(candidate_id(item)) == "reminder" and item.get("label")
        ]
        if reminders:
            lines.append(
                "- REMINDER ONLY, one short line, no second explanation: " + "; ".join(reminders)
            )
        if self.avoid_openers:
            lines.append("- Do not open with: " + ", ".join(_opener_phrase(key) for key in self.avoid_openers))
        if self.avoid_songs:
            lines.append("- Do not re-introduce these songs: " + "; ".join(self.avoid_songs[:4]))
        lines.append("- " + _ending_line(self.ending, self.avoid_closings))
        return "\n".join(lines)


def skip_block(family: str, label: str = "") -> str:
    text = _SKIP_TEXT.get(str(family or "").strip().lower(), "")
    if not text:
        return ""
    if label and family == "fun_day":
        return (
            "FUN / NATIONAL DAYS (skip on this break):\n"
            "fun_days: none\n"
            f"- Do NOT mention {label} on this break. Listeners already heard it."
        )
    return text


def reminder_block(label: str) -> str:
    title = " ".join(str(label or "").split()).strip()
    return (
        "FUN / NATIONAL DAYS (reminder only — listeners already heard the explanation):\n"
        "fun_days:\n"
        f"- title: {title}\n"
        "  note: none\n\n"
        "FUN DAY RULES:\n"
        "- One short warm reminder of that title. Do not explain the month or the cause again.\n"
        "- Do not repeat an earlier sentence about it.\n"
        "- Then go back to the music."
    )


def plan_break(
    host: str,
    when: datetime | None,
    event_type: str,
    candidates: list[dict[str, Any]] | None = None,
    *,
    specialty: bool = False,
    state_file: Path | None = None,
) -> BreakPlan:
    """Choose one focus for this break from what the selectors already found."""
    moment = when if isinstance(when, datetime) else datetime.now()
    host_key = str(host or "").strip().lower()
    items = [dict(item) for item in (candidates or []) if item.get("key")]
    history = _load_state(state_file)
    host_breaks = _recent_breaks(history, host_key, moment)
    event = str(event_type or "").strip().lower()
    close = any(marker in event for marker in _CLOSE_EVENTS)
    modes: dict[str, str] = {}
    chosen: list[dict[str, Any]] = []

    if close or specialty:
        for item in items:
            modes[candidate_id(item)] = "skip"
        ending = "signoff" if close else "music"
    else:
        # Birthdays and the question of the day come before an observance.
        # A solemn observance comes before a novelty day of the same kind.
        musts = sorted(
            [item for item in items if item.get("must")],
            key=lambda item: (
                _MUST_RANK.get(str(item.get("family")), 9),
                0 if item.get("solemn") else 1,
                str(item.get("label") or ""),
            ),
        )
        for item in musts:
            mode = _delivery_mode(item, host_breaks, history, moment, host_key)
            if mode == "skip":
                modes[candidate_id(item)] = "skip"
                continue
            if len(chosen) >= MAX_HEAVY:
                modes[candidate_id(item)] = "skip"
                continue
            modes[candidate_id(item)] = mode
            chosen.append(item)
        optionals = sorted(
            [item for item in items if not item.get("must") and item.get("heavy", True)],
            key=lambda item: (
                _OPTIONAL_RANK.get(str(item.get("family")), 9),
                str(item.get("label") or ""),
            ),
        )
        previous = host_breaks[0] if host_breaks else {}
        prev_families = {str(topic.get("family") or "") for topic in previous.get("topics") or []}
        prev_ending = str(previous.get("ending") or "")
        if not chosen:
            for item in optionals:
                family = str(item.get("family") or "")
                if family in prev_families:
                    modes[candidate_id(item)] = "skip"
                    continue
                if family in {"friends", "engagement", "question"} and prev_ending == "community":
                    modes[candidate_id(item)] = "skip"
                    continue
                if _delivery_mode(item, host_breaks, history, moment, host_key) == "skip":
                    modes[candidate_id(item)] = "skip"
                    continue
                modes[candidate_id(item)] = "full"
                chosen.append(item)
                break
        for item in items:
            ident = candidate_id(item)
            if ident not in modes:
                modes[ident] = "skip"
        ending = _ending_for(chosen, close=False)

    station_breaks = _station_breaks(history, moment)
    avoid_openers = _recent_openers(station_breaks)
    avoid_closings = _recent_closings(station_breaks)
    already = _recent_labels(host_breaks, history, moment, host_key)
    avoid_songs = _recent_songs(host_breaks)
    return BreakPlan(
        items,
        modes,
        ending,
        avoid_openers=avoid_openers,
        avoid_closings=avoid_closings,
        already=already,
        avoid_songs=avoid_songs,
        specialty=specialty or close,
        avoid_opening_fingerprints=_station_fingerprints(history, "station_openings"),
        avoid_closing_fingerprints=_station_fingerprints(history, "station_closings"),
    )


_COLD_TOAST_RE = re.compile(
    r"(?i)\b(?:here+['’]?s to|hee+r is to|cheers to another|questionable decisions|"
    r"another year of|your speakers are ready|life is better with the music)\b"
)
_GREETING_RE = re.compile(r"(?i)\b(?:hey everyone|hey there|hey folks|hey friends|i'm |i am )\b")
_DOG_BIT_RE = re.compile(
    r"(?i)\b(?:moecarbay|moe[\s-]*car[\s-]*bay|mo[\s-]*ca[\s-]*bay|"
    r"tail(?:'s| is) still wagging|been sniffed)\b"
)
_BIRTHDAY_WORD_RE = re.compile(r"(?i)\bhappy birthday\b")
_ELABORATION_START_RE = re.compile(r"(?i)^(that|it|this|you|and|but|so|because|which|there)\b")
_MUSIC_REASON_RE = re.compile(
    r"(?i)\b(?:because|reminds|remember|favorite|fits the|mood|classic|always loved|the kind of|what i love)\b"
)
_ENTITY_SKIP = frozenset(
    """
    the a an and or but monday tuesday wednesday thursday friday saturday sunday
    january february march april may june july august september october november december
    am pm dj
    """.split()
)


def _person_in_text(text: str, name: str) -> bool:
    clean = " ".join(str(name or "").split()).strip()
    if not clean:
        return False
    if clean.casefold() in str(text or "").casefold():
        return True
    parts = [part for part in re.findall(r"[A-Za-z']+", clean) if len(part) > 2]
    if len(parts) < 2:
        return False
    lowered = str(text or "").casefold()
    return all(part.casefold() in lowered for part in parts)


def _is_cold_toast(sentence: str) -> bool:
    return bool(_COLD_TOAST_RE.search(sentence or ""))


def _is_dog_bit(sentence: str) -> bool:
    return bool(_DOG_BIT_RE.search(sentence or ""))


def _is_bare_music(sentence: str) -> bool:
    if not _MUSIC_RE.search(sentence or ""):
        return False
    return not bool(_MUSIC_REASON_RE.search(sentence or ""))


def _mid_entities(sentence: str) -> set[str]:
    found: set[str] = set()
    for match in re.finditer(r"\b[A-Z][a-zA-Z']+(?:\s+[A-Z][a-zA-Z']+)*", str(sentence or "")):
        if match.start() == 0:
            continue
        words = [word for word in match.group(0).split() if word.casefold() not in _ENTITY_SKIP]
        if words:
            found.add(" ".join(words).casefold())
    return found


_PAD_LINE_RE = re.compile(
    r"(?i)^(?:"
    r"glad you(?:'re| are) still hanging out|"
    r"plenty of good songs still rolling|"
    r"i(?:'m| am) enjoying this stretch of the mix|"
    r"let(?:'s| us) keep it going for a little|"
    r"good company and good music|"
    r"more good music still ahead|"
    r"stick around\b.{0,40}plenty more|"
    r"let(?:'s| us) keep the music rolling"
    r")\b"
)


def _strip_good_measure(sentence: str) -> str:
    """Remove the stock tag. Leave the DJ's own sentence alone."""
    original = " ".join(str(sentence or "").split()).strip()
    if not original or not re.search(r"(?i)just for good measure", original):
        return original
    body = re.sub(r"(?i),?\s*just for good measure", "", original).strip(" ,;:-")
    if not body:
        return original
    if body[-1] not in ".!?":
        body += "."
    return body


def _warm_birthday(names: list[str]) -> str:
    clean = [" ".join(str(name).split()).strip() for name in names if str(name).strip()]
    if not clean:
        return ""
    if len(clean) == 1:
        return f"Happy birthday to {clean[0]}. Hope the day treats you well."
    if len(clean) == 2:
        return f"Happy birthday to {clean[0]} and {clean[1]}. Hope the day treats you both well."
    who = ", ".join(clean[:-1]) + f", and {clean[-1]}"
    return f"Happy birthday to {who}. Hope the day treats every one of you well."


def _rewrite_cold_greeting(sentence: str, names: list[str]) -> str:
    if not _is_cold_toast(sentence) or not _BIRTHDAY_WORD_RE.search(sentence):
        return sentence
    mentioned = [name for name in names if _person_in_text(sentence, name)]
    if mentioned:
        return _warm_birthday(mentioned)
    return sentence


def _is_short_greeting(sentence: str) -> bool:
    return bool(_GREETING_RE.search(sentence or "")) and len(str(sentence or "").split()) <= 18


def _is_allowed_closer(sentence: str, allow_cta: str) -> bool:
    keys = [key for key, pattern in _CLOSINGS if pattern.search(sentence or "")]
    if not keys:
        return False
    allowed = _allowed_closing_keys(allow_cta)
    return all(key in allowed for key in keys)


def _continues_topic(previous: str, current: str) -> bool:
    if _story_relation(previous, current) != "drop":
        return True
    if _is_cold_toast(current) or _is_bare_music(current):
        return False
    if _ELABORATION_START_RE.search(current.strip()) and not _mid_entities(current):
        return True
    if len(current.split()) <= 14 and not _mid_entities(current):
        return True
    return False


def _align_spoken_sentences(
    sentences: list[str],
    *,
    direction: str,
    mentions: list[str],
    labels: list[str],
    allow_cta: str = "",
    solemn: bool = False,
) -> list[str]:
    """Drop toasts, slogans, and stock pads. Keep a real thought intact."""
    kind = str(direction or "").strip().lower()
    names = [" ".join(str(name).split()).strip() for name in mentions if str(name).strip()]
    feature_labels = [label for label in labels if str(label).strip()]
    dog_also_present = any(_is_dog_bit(sentence) for sentence in sentences)
    kept: list[str] = []
    kept_music = False

    def off_topic(sentence: str) -> bool:
        if _is_cold_toast(sentence):
            named_greeting = (
                kind == "birthday"
                and any(_person_in_text(sentence, name) for name in names)
                and bool(_BIRTHDAY_WORD_RE.search(sentence))
            )
            return not named_greeting
        if _is_dog_bit(sentence) and kind not in {"", "dogs"}:
            return True
        return False

    for sentence in sentences:
        if off_topic(sentence):
            continue
        if kind == "specialty":
            kept.append(sentence)
            continue
        if _is_bare_music(sentence):
            if kind == "dogs" or solemn:
                continue
            if kind == "" and dog_also_present:
                continue
            if kept_music:
                continue
            sentence = _strip_good_measure(sentence)
            kept.append(sentence)
            kept_music = True
            continue
        if kind == "birthday" and names and (
            _BIRTHDAY_WORD_RE.search(sentence)
            or any(_person_in_text(sentence, name) for name in names)
        ):
            sentence = _rewrite_cold_greeting(sentence, names)
            kept.append(sentence)
            continue
        label_hit = any(_label_in_text(sentence, label) for label in feature_labels)
        mention_hit = any(_person_in_text(sentence, name) for name in names)
        fragment = len(sentence.split()) <= 5 and not label_hit and not mention_hit
        slogan = solemn and len(sentence.split()) <= 8 and not label_hit and not mention_hit
        if (fragment or slogan) and not _is_allowed_closer(sentence, allow_cta):
            continue
        if _is_allowed_closer(sentence, allow_cta) and not kept:
            continue
        kept.append(sentence)

    if kind == "birthday" and names:
        missing = [name for name in names if not any(_person_in_text(sentence, name) for sentence in kept)]
        if missing:
            insert_at = 1 if kept and _is_short_greeting(kept[0]) else 0
            kept.insert(insert_at, _warm_birthday(missing))
        kept = [
            sentence
            for sentence in kept
            if not (_is_cold_toast(sentence) and not _BIRTHDAY_WORD_RE.search(sentence))
        ]
    return kept


def tighten_spoken_break(
    script: str,
    *,
    labels: list[str] | None = None,
    allow_cta: str = "",
    recent_openers: list[str] | None = None,
    recent_opening_fingerprints: list[str] | None = None,
    recent_closing_fingerprints: list[str] | None = None,
    direction: str = "",
    required_mentions: list[str] | None = None,
    solemn: bool = False,
) -> str:
    """Drop stock pads, toasts, and slogan tags. Keep the spoken thought."""
    text = " ".join(str(script or "").split())
    if not text:
        return text
    sentences = _sentences(text)
    if not sentences:
        return text
    sentences = [sentence for sentence in sentences if not _PAD_LINE_RE.search(sentence.strip())]
    sentences = _drop_fingerprint_edge(sentences, recent_opening_fingerprints or [], at_end=False)
    sentences = _drop_fingerprint_edge(sentences, recent_closing_fingerprints or [], at_end=True)
    sentences = _drop_repeated_openers(sentences, recent_openers or [])
    sentences = _drop_repeated_topics(sentences, labels or [])
    sentences = _drop_unwanted_closers(sentences, allow_cta)
    sentences = _align_spoken_sentences(
        sentences,
        direction=direction,
        mentions=list(required_mentions or []),
        labels=list(labels or []),
        allow_cta=allow_cta,
        solemn=solemn,
    )
    if not sentences:
        if str(direction or "").strip().lower() == "birthday" and required_mentions:
            return _warm_birthday(list(required_mentions))
        return text
    return " ".join(sentences).strip()


_STOCK_OPEN_RE = re.compile(
    r"(?i)^(?:"
    r"hey(?: there| friends| folks| everybody| everyone| music lovers)?\b|"
    r"hi(?: there| everybody| everyone| folks| friends)?\b|"
    r"hello\b|"
    r"welcome(?: in| back| to)\b|"
    r"how(?:'s| is| are) (?:everyone|y'all|you all|you doing|things)\b|"
    r"hope you(?:'re| are| have|'ve| had) (?:having|had|a |doing|enjoying)\b|"
    r"good (?:morning|afternoon|evening)\b|"
    r"thanks for (?:tuning in|joining us|spending|listening|making us)\b|"
    r"y'all ready\b|"
    r"you(?:'re| are) (?:tuned in|listening|here)\b|"
    r"glad you(?:'re| are) (?:here|with us|tuning)\b"
    r")"
)
_SITE_LINE_RE = re.compile(
    r"(?i)\b(?:request a song|mosplace(?:radio)?(?:\.com|\.radio\.com)|"
    r"moe'?s place radio dot com|click(?:ing)?\s+community|love to hear from you|"
    r"keep those requests coming|requests are open|head over to|community section)\b"
)
_HANDOFF_RE = re.compile(
    r"(?i)\b(?:hand(?:ing|s)? off|take(?:s|ing) over|love you, bye|"
    r"woosah|filthy chooches|that(?:'s| is) it for me|signing off)\b"
)
_QUESTION_BAIT_RE = re.compile(r"(?i)^here(?:'s| is) a question\b")
_YEAR_FACT_RE = re.compile(
    r"(?i)(?:\btaking a look back\b|\bthis day in music history\b|"
    r"\bin (?:19|20)\d{2}\b|\bin '(?:\d{2})\b)"
)
_OTHER_FEATURE_RE = re.compile(
    r"(?i)\b(?:awareness month|national [\w' -]{0,40}day|happy birthday|question of the day)\b"
)
_EXTRA_PAD_RE = re.compile(
    r"(?i)^(?:stick around\b|plenty more in the mix\b|hope you are too\b|"
    r"let(?:'s| us) keep the good vibes\b|thanks for listening\b)"
)
_STOCK_FILLER_RE = re.compile(
    r"(?i)\b(?:fresh mix|great tunes|great vibes|keep your ears tuned|"
    r"variety sounds good|all about variety|let the music bring you|"
    r"we(?:'ve| have) got a (?:fresh|great) mix|daily mix is all about)\b"
)
_STATION_ID_RE = re.compile(
    r"(?i)\b(?:on moe'?s place radio|you(?:'re| are) listening to|radio dot com)\b"
)
_ANNOUNCER_WISH_RE = re.compile(
    r"(?i)\b(?:from all of us|on behalf of|the whole crew|everyone here at)\b"
)
_STRETCH_HERE_RE = re.compile(r"(?i)\bhee+r\b")
_FOCUSED_SUBJECTS = frozenset(
    {
        "fun_day",
        "birthday",
        "announcement",
        "question",
        "engagement",
        "personal",
        "rss",
        "talking",
        "friends",
        "books",
        "dogs",
        "farmstand",
    }
)


def recent_opening_hints(
    when: datetime | None = None,
    *,
    state_file: Path | None = None,
    limit: int = 6,
) -> list[str]:
    """Recent first-line fingerprints, so the next break does not reuse them."""
    del when
    history = _load_state(state_file)
    return _station_fingerprints(history, "station_openings")[:limit]


def _note_words(text: str) -> set[str]:
    return {
        word
        for word in re.findall(r"[a-z0-9']+", str(text or "").casefold())
        if len(word) >= 5 and word not in _STOP
    }


def _on_supplied_subject(sentence: str, label: str, note: str) -> bool:
    if label and _label_in_text(sentence, label):
        return True
    supplied = _note_words(note)
    if len(supplied) < 2:
        return False
    return len(supplied & _note_words(sentence)) >= 2


def _birthday_comes_first(text: str, label: str) -> bool:
    """The wish is spoken before the name, or the name is not in the line."""
    if not label:
        return True
    name_at = str(text or "").casefold().find(str(label).casefold())
    if name_at < 0:
        return True
    match = _BIRTHDAY_WORD_RE.search(text or "")
    return bool(match) and match.start() < name_at


def _ordered_birthday_wish(sentence: str, label: str) -> str:
    """Happy birthday, then the name. Never the name and then the wish."""
    wish = _warm_birthday([label]) if label else ""
    if not wish:
        return sentence
    if _ANNOUNCER_WISH_RE.search(sentence) or not _birthday_comes_first(sentence, label):
        return wish
    direct = re.match(
        rf"(?i)^happy birthday,\s+{re.escape(label)}\b",
        sentence.strip(),
    )
    if direct:
        return wish
    return sentence


def _birthday_line(label: str, note: str) -> str:
    """Name and supplied note only. A weekend or a station slogan is not a birthday."""
    wish = _warm_birthday([label]) if label else ""
    detail = " ".join(str(note or "").split()).strip()
    if detail.casefold() in {"", "none"}:
        return wish
    if _BIRTHDAY_WORD_RE.search(detail) and len(detail.split()) <= 8:
        return wish or detail
    if wish and detail.casefold() in wish.casefold():
        return wish
    if detail[-1] not in ".!?":
        detail += "."
    return f"{wish} {detail}".strip() if wish else detail


def _birthday_only(sentences: list[str], label: str, note: str) -> list[str]:
    kept: list[str] = []
    for sentence in sentences:
        if _STOCK_OPEN_RE.search(sentence.strip()) or _STOCK_FILLER_RE.search(sentence):
            continue
        if _SITE_LINE_RE.search(sentence) or _STATION_ID_RE.search(sentence):
            continue
        if label and _label_in_text(sentence, label) and not _BIRTHDAY_WORD_RE.search(sentence):
            continue
        if _BIRTHDAY_WORD_RE.search(sentence):
            sentence = _ordered_birthday_wish(sentence, label)
            if sentence and sentence not in kept:
                kept.append(sentence)
            continue
        if note and _on_supplied_subject(sentence, "", note):
            kept.append(sentence)
    wishes = [sentence for sentence in kept if _BIRTHDAY_WORD_RE.search(sentence)]
    rest = [sentence for sentence in kept if sentence not in wishes]
    if wishes:
        spoken = wishes[0]
        tail: list[str] = []
        for sentence in wishes[1:] + rest:
            if label and not _birthday_comes_first(f"{spoken} {sentence}", label):
                continue
            tail.append(sentence)
            spoken = f"{spoken} {sentence}".strip()
        kept = [wishes[0], *tail]
    if not kept or all(_BIRTHDAY_WORD_RE.search(sentence) for sentence in kept):
        line = _birthday_line(label, note)
        return [line] if line else kept
    joined = " ".join(kept)
    if label and not _birthday_comes_first(joined, label):
        line = _birthday_line(label, note)
        return [line] if line else kept
    return kept


def _grounded_subject_line(label: str, note: str, kind: str) -> str:
    """One spoken line from the supplied subject. No added scene."""
    title = " ".join(str(label or "").split()).strip()
    detail = " ".join(str(note or "").split()).strip()
    if detail.casefold() == "none":
        detail = ""
    if kind == "birthday" and title:
        return _birthday_line(title, detail)
    if detail:
        if title and title.casefold() not in detail.casefold():
            line = f"{title}. {detail}"
        else:
            line = detail
        if line[-1] not in ".!?":
            line += "."
        return line
    if not title:
        return ""
    if title[-1] in ".!?":
        return title
    return f"{title}."


def focus_spoken_break(
    script: str,
    *,
    subject: str = "",
    label: str = "",
    note: str = "",
    allow_cta: str = "",
    recent_opening_fingerprints: list[str] | None = None,
) -> str:
    """Keep one subject. Drop greetings, stock pads, and a second story."""
    text = _STRETCH_HERE_RE.sub("here", " ".join(str(script or "").split()))
    if not text:
        return text
    kind = str(subject or "").strip().lower()
    sentences = [sentence for sentence in _sentences(text) if sentence]
    if not sentences:
        return text
    sentences = [
        sentence
        for sentence in sentences
        if not _PAD_LINE_RE.search(sentence.strip())
        and not _EXTRA_PAD_RE.search(sentence.strip())
        and not _STOCK_FILLER_RE.search(sentence)
    ]
    if kind not in {"show_open", "handoff", "show_close"}:
        sentences = [
            sentence
            for sentence in sentences
            if not _STATION_ID_RE.search(sentence) or _BIRTHDAY_WORD_RE.search(sentence)
        ]
    if kind not in {"show_open"}:
        sentences = [
            sentence
            for sentence in sentences
            if not _STOCK_OPEN_RE.search(sentence.strip())
            or (kind != "birthday" and _on_supplied_subject(sentence, label, note))
        ]
    if kind == "farmstand":
        pass
    elif kind in {"question", "engagement"} or allow_cta == "community":
        sentences = [
            sentence
            for sentence in sentences
            if not re.search(r"(?i)\b(?:request a song|requests are open|keep those requests)\b", sentence)
        ]
    elif allow_cta == "request":
        sentences = [
            sentence
            for sentence in sentences
            if not re.search(r"(?i)\b(?:click(?:ing)?\s+community|love to hear from you)\b", sentence)
        ]
    else:
        sentences = [sentence for sentence in sentences if not _SITE_LINE_RE.search(sentence)]

    if kind == "birthday" and (label or note):
        sentences = _birthday_only(sentences, label, note)
    elif kind in _FOCUSED_SUBJECTS and (label or note):
        expanded: list[str] = []
        started = False
        for sentence in sentences:
            if _on_supplied_subject(sentence, label, note):
                started = True
                expanded.append(sentence)
                continue
            if not started:
                continue
            if _YEAR_FACT_RE.search(sentence):
                break
            if _SITE_LINE_RE.search(sentence):
                if allow_cta == "community" and re.search(
                    r"(?i)\b(?:community|love to hear from you)\b", sentence
                ):
                    expanded.append(sentence)
                    continue
                if allow_cta == "bakehouse" and re.search(r"(?i)bake\s*house", sentence):
                    expanded.append(sentence)
                    continue
                break
            if _STOCK_OPEN_RE.search(sentence.strip()) and not _on_supplied_subject(sentence, label, note):
                break
            if _OTHER_FEATURE_RE.search(sentence) and not _on_supplied_subject(sentence, label, note):
                break
            if "?" in sentence and kind not in {"question", "engagement"}:
                break
            expanded.append(sentence)
        sentences = expanded
    elif kind in {"handoff", "show_close"}:
        sentences = [sentence for sentence in sentences if _HANDOFF_RE.search(sentence)]
    elif kind in {"music", "music_history", "seventies", "blues", "show_open"}:
        kept_music: list[str] = []
        for sentence in sentences:
            if _OTHER_FEATURE_RE.search(sentence) or _QUESTION_BAIT_RE.search(sentence.strip()):
                continue
            if kind not in {"music_history", "seventies"} and _YEAR_FACT_RE.search(sentence):
                continue
            if "?" in sentence and not _on_supplied_subject(sentence, label, note):
                continue
            kept_music.append(sentence)
        sentences = kept_music

    sentences = _drop_fingerprint_edge(sentences, recent_opening_fingerprints or [], at_end=False)
    sentences = [sentence for sentence in sentences if sentence.strip()]
    if not sentences:
        grounded = _grounded_subject_line(label, note, kind)
        return grounded or text
    return " ".join(sentences).strip()


def record_break(
    host: str,
    when: datetime | None,
    script: str,
    candidates: list[dict[str, Any]] | None = None,
    *,
    event_type: str = "",
    planned_modes: dict[str, str] | None = None,
    state_file: Path | None = None,
) -> dict[str, Any]:
    """Remember subjects, closers, and songs from the break that actually aired."""
    moment = when if isinstance(when, datetime) else datetime.now()
    host_key = str(host or "").strip().lower()
    text = str(script or "").strip()
    topics: list[dict[str, Any]] = []
    modes = planned_modes or {}
    for item in candidates or []:
        label = str(item.get("label") or "").strip()
        if not label or not _label_in_text(text, label):
            continue
        planned = modes.get(candidate_id(item), "mentioned")
        depth = planned if planned in {"full", "reminder"} else "mentioned"
        topics.append(
            {
                "family": item.get("family"),
                "key": item.get("key"),
                "label": label,
                "depth": depth,
                "shared": bool(item.get("shared") or item.get("solemn")),
            }
        )
    beverage = ""
    try:
        import beverage_rules

        found = beverage_rules.detect_beverages(text)
        beverage = found[0] if found else ""
    except Exception:
        beverage = ""
    entry = {
        "at": moment.isoformat(timespec="seconds"),
        "event_type": str(event_type or "").strip(),
        "ending": ending_in_script(text),
        "opener": opener_key(text),
        "closings": closing_keys(text),
        "topics": topics,
        "songs": song_mentions(text),
        "beverage": beverage,
    }
    data = _load_state(state_file)
    hosts = data.setdefault("hosts", {})
    recent = [item for item in hosts.get(host_key) or [] if isinstance(item, dict)]
    recent.insert(0, entry)
    hosts[host_key] = _prune(recent, moment)
    sentences = _sentences(text)
    if sentences:
        _remember_station_edge(data, "station_openings", sentences[0])
        _remember_station_edge(data, "station_closings", sentences[-1])
    _save_state(data, state_file)
    return entry


def last_break_beverage(
    host: str,
    when: datetime | None = None,
    *,
    state_file: Path | None = None,
    within_hours: float = 4,
) -> str:
    """Drink named on this host's latest break, if that break was recent."""
    from livedj_daypart import station_now

    moment = station_now(when)
    host_key = str(host or "").strip().lower()
    if not host_key:
        return ""
    history = _load_state(state_file)
    rows = _recent_breaks(history, host_key, moment)
    if not rows:
        return ""
    latest = rows[0]
    at = _parse_time(str(latest.get("at") or ""))
    if at is not None:
        if at > moment or moment - at > timedelta(hours=within_hours):
            return ""
    return str(latest.get("beverage") or "").strip()


def ending_in_script(script: str) -> str:
    keys = set(closing_keys(script))
    if "click_community" in keys or "let_us_know" in keys:
        return "community"
    if "request_song" in keys:
        return "request"
    if re.search(r"(?i)\bbarndoor bake\s*house\b|\bbarn door bake\s*house\b", script or ""):
        if re.search(r"(?i)\bclick\b", script or ""):
            return "bakehouse"
    return "music"


def opener_key(script: str) -> str:
    first = _sentences(script)
    if not first:
        return ""
    for key, pattern in _OPENERS:
        if pattern.search(first[0].strip()):
            return key
    return ""


def closing_keys(script: str) -> list[str]:
    found: list[str] = []
    for key, pattern in _CLOSINGS:
        if pattern.search(script or "") and key not in found:
            found.append(key)
    return found


def song_mentions(script: str) -> list[str]:
    found: list[str] = []
    for match in _SONG_RE.finditer(script or ""):
        title = " ".join(match.group(1).split()).strip(" ,;:-")
        if title and title.casefold() not in {item.casefold() for item in found}:
            found.append(title)
    return found[:4]


def _delivery_mode(
    item: dict[str, Any],
    host_breaks: list[dict[str, Any]],
    history: dict[str, Any],
    when: datetime,
    host_key: str,
) -> str:
    key = str(item.get("key") or "")
    if not key:
        return "skip"
    mentions = _mentions_of(key, item, host_breaks, history, when, host_key)
    if not mentions:
        return "full"
    last = mentions[0]
    last_at = _parse_time(str(last.get("at") or ""))
    sharedish = bool(item.get("shared") or item.get("solemn") or item.get("must"))
    if last_at is not None and when - last_at < TOO_SOON:
        return "skip"
    if not sharedish:
        return "skip"
    today = [row for row in mentions if _same_day(_parse_time(str(row.get("at") or "")), when)]
    if any(str(row.get("depth") or "") == "reminder" for row in today):
        return "skip"
    if today:
        return "reminder"
    return "full"


def _mentions_of(
    key: str,
    item: dict[str, Any],
    host_breaks: list[dict[str, Any]],
    history: dict[str, Any],
    when: datetime,
    host_key: str,
) -> list[dict[str, Any]]:
    shared = bool(item.get("shared") or item.get("solemn"))
    rows: list[dict[str, Any]] = []
    hosts = history.get("hosts") if isinstance(history.get("hosts"), dict) else {}
    source = hosts.items() if shared else ((host_key, host_breaks),)
    for name, breaks in source:
        break_list = breaks if name == host_key and breaks is host_breaks else _recent_breaks(history, str(name), when)
        if name == host_key:
            break_list = host_breaks
        for entry in break_list:
            at = str(entry.get("at") or "")
            for topic in entry.get("topics") or []:
                if str(topic.get("key") or "") != key:
                    continue
                rows.append(
                    {
                        "at": at,
                        "depth": topic.get("depth") or "mentioned",
                        "host": name,
                    }
                )
    rows.sort(key=lambda row: str(row.get("at") or ""), reverse=True)
    return rows


def _ending_for(chosen: list[dict[str, Any]], *, close: bool) -> str:
    if close:
        return "signoff"
    families = {str(item.get("family") or "") for item in chosen}
    if "farmstand" in families:
        return "bakehouse"
    if families & {"question", "engagement", "friends"}:
        return "community"
    return "music"


def _ending_line(ending: str, avoid_closings: list[str]) -> str:
    avoided = ""
    if avoid_closings:
        avoided = " Recent breaks already used: " + ", ".join(avoid_closings) + "."
    if ending == "community":
        return (
            "ENDING: the listener was asked something, so one Community invite is enough. "
            "Do not also invite a song request."
            + avoided
        )
    if ending == "bakehouse":
        return "ENDING: the Bakehouse click only. Do not add Community or a song request." + avoided
    if ending == "request":
        return "ENDING: one song-request invite, then stop." + avoided
    if ending == "signoff":
        return (
            "ENDING: a short sign-off, and then stop. "
            "Do not add another sentence after the sign-off, and do not start a new story or a website pitch."
            + avoided
        )
    return (
        "ENDING: the song or a short thought. Do not add a request, Community, "
        "\"We would love to hear from you,\" or \"Let us know what you think.\""
        + avoided
    )


def _opener_phrase(key: str) -> str:
    phrases = {
        "youre_still_here": "You're still here",
        "hey_there": "Hey there",
        "hey_everyone": "Hey everyone",
        "hey_friends": "Hey friends",
        "hey_folks": "Hey folks",
    }
    return phrases.get(key, key)


def _recent_openers(breaks: list[dict[str, Any]]) -> list[str]:
    found: list[str] = []
    for entry in breaks[:3]:
        key = str(entry.get("opener") or "")
        if key and key not in found:
            found.append(key)
    return found


def _recent_closings(breaks: list[dict[str, Any]]) -> list[str]:
    found: list[str] = []
    for entry in breaks[:3]:
        for key in entry.get("closings") or []:
            if key and key not in found:
                found.append(str(key))
    return found


def _recent_songs(breaks: list[dict[str, Any]]) -> list[str]:
    found: list[str] = []
    for entry in breaks[:3]:
        for title in entry.get("songs") or []:
            if title and title.casefold() not in {item.casefold() for item in found}:
                found.append(str(title))
    return found


def _recent_labels(
    host_breaks: list[dict[str, Any]],
    history: dict[str, Any],
    when: datetime,
    host_key: str,
) -> list[str]:
    found: list[str] = []

    def add(label: str) -> None:
        clean = " ".join(str(label or "").split()).strip()
        if clean and clean.casefold() not in {item.casefold() for item in found}:
            found.append(clean)

    for entry in host_breaks[:4]:
        for topic in entry.get("topics") or []:
            add(str(topic.get("label") or ""))
    hosts = history.get("hosts") if isinstance(history.get("hosts"), dict) else {}
    for name, breaks in hosts.items():
        if str(name) == host_key:
            continue
        for entry in _recent_breaks({"hosts": {name: breaks}}, str(name), when)[:4]:
            at = _parse_time(str(entry.get("at") or ""))
            if at is None or when - at > TOO_SOON:
                continue
            for topic in entry.get("topics") or []:
                if topic.get("shared"):
                    add(str(topic.get("label") or ""))
    return found


_STORY_STOP = frozenset(
    """
    that this with from your just about have been were they them then than
    into over also more some when what where which would could should really
    very the and for but not are was its a an of to in on at it we our you
    """.split()
)
_BRIDGE = "That lines up with this."


def sentence_fingerprint(text: str, words: int = 6) -> str:
    parts = re.sub(r"[^a-z0-9]+", " ", str(text or "").casefold()).split()
    return " ".join(parts[:words])


def _station_breaks(history: dict[str, Any], when: datetime) -> list[dict[str, Any]]:
    hosts = history.get("hosts") if isinstance(history.get("hosts"), dict) else {}
    rows: list[dict[str, Any]] = []
    for name in hosts:
        rows.extend(_recent_breaks(history, str(name), when))
    rows.sort(key=lambda item: str(item.get("at") or ""), reverse=True)
    return rows[:KEEP_BREAKS]


def _station_fingerprints(history: dict[str, Any], key: str) -> list[str]:
    found: list[str] = []
    for item in history.get(key) or []:
        text = str(item or "").strip()
        if text and text not in found:
            found.append(text)
    return found[:8]


def _remember_station_edge(data: dict[str, Any], key: str, sentence: str) -> None:
    if _MUSIC_RE.search(sentence or ""):
        return
    if len(str(sentence or "").split()) > 24:
        return
    fingerprint = sentence_fingerprint(sentence)
    if not fingerprint:
        return
    current = [str(item) for item in data.get(key) or [] if str(item).strip()]
    current = [item for item in current if item != fingerprint]
    current.insert(0, fingerprint)
    data[key] = current[:16]


def _drop_fingerprint_edge(sentences: list[str], fingerprints: list[str], *, at_end: bool) -> list[str]:
    if len(sentences) < 2 or not fingerprints:
        return sentences
    index = -1 if at_end else 0
    sentence = sentences[index]
    if _MUSIC_RE.search(sentence) or len(sentence.split()) > 24:
        return sentences
    if sentence_fingerprint(sentence) in set(fingerprints):
        if at_end:
            return sentences[:-1]
        return sentences[1:]
    return sentences


def _story_tokens(text: str) -> set[str]:
    return {
        word
        for word in re.findall(r"[a-z0-9']+", str(text or "").casefold())
        if len(word) >= 4 and word not in _STORY_STOP
    }


def _is_closer_sentence(sentence: str) -> bool:
    return any(pattern.search(sentence or "") for _key, pattern in _CLOSINGS)


def _story_relation(previous: str, current: str) -> str:
    left = _story_tokens(previous)
    right = _story_tokens(current)
    if len(right) < 2:
        return "continue"
    shared = left & right
    if not shared:
        return "drop"
    novel = right - left
    if len(novel) >= 2 and 1 <= len(shared) <= 2:
        return "bridge"
    return "continue"


def _shape_story_sentences(sentences: list[str]) -> list[str]:
    """Pass the written break through untouched.

    The model writes the transitions. An earlier version of this step inserted a
    canned bridge sentence ("That lines up with this.") and silently dropped
    sentences it judged unrelated, which left breaks disconnected and shorter.
    Repetition is handled by the planner and _drop_repeated_topics instead.
    """
    return list(sentences)


def _drop_repeated_openers(sentences: list[str], recent_openers: list[str]) -> list[str]:
    if not sentences or not recent_openers:
        return sentences
    first = sentences[0].strip()
    for key, pattern in _OPENERS:
        if key in recent_openers and pattern.search(first) and len(first.split()) <= 8:
            return sentences[1:] or sentences
    return sentences


def _drop_repeated_topics(sentences: list[str], labels: list[str]) -> list[str]:
    if len(sentences) < 2:
        return sentences
    distinctive = []
    for label in labels:
        words = [
            word
            for word in re.findall(r"[a-z0-9]+", str(label or "").casefold())
            if len(word) >= 4 and word not in _STOP
        ]
        if words:
            distinctive.append(words)
    drop: set[int] = set()
    seen_label = [False] * len(distinctive)
    for index, sentence in enumerate(sentences):
        if _MUSIC_RE.search(sentence):
            continue
        lowered = sentence.casefold()
        for group_index, words in enumerate(distinctive):
            if all(word in lowered for word in words):
                if seen_label[group_index]:
                    drop.add(index)
                else:
                    seen_label[group_index] = True
        if index in drop:
            continue
        for earlier in range(index):
            if earlier in drop:
                continue
            if _same_explanation(sentences[earlier], sentence):
                drop.add(index)
                break
    return [sentence for index, sentence in enumerate(sentences) if index not in drop]


def _same_explanation(earlier: str, later: str) -> bool:
    if _MUSIC_RE.search(later):
        return False
    left = set(_tokens(earlier))
    right = set(_tokens(later))
    if len(left) < 4 or len(right) < 4:
        return False
    shared = left & right
    if len(shared) < 4:
        return False
    return len(shared) / len(left | right) >= 0.55


def _drop_unwanted_closers(sentences: list[str], allow_cta: str) -> list[str]:
    allowed = _allowed_closing_keys(allow_cta)
    kept: list[str] = []
    dropped_closer = False
    for sentence in sentences:
        keys = [key for key, pattern in _CLOSINGS if pattern.search(sentence)]
        extra = [key for key in keys if key not in allowed]
        if extra and len(sentence.split()) <= 28 and (len(kept) or len(sentences) > 1):
            dropped_closer = True
            continue
        # A short follow-on to a dropped closer ("we'll get to it") has nothing left to refer to.
        if (
            dropped_closer
            and not keys
            and len(sentence.split()) <= 6
            and not _MUSIC_RE.search(sentence)
        ):
            dropped_closer = False
            continue
        dropped_closer = False
        kept.append(sentence)
    return kept or sentences


def _allowed_closing_keys(allow_cta: str) -> set[str]:
    kind = str(allow_cta or "").strip().lower()
    if kind == "community":
        return {"love_to_hear", "let_us_know", "click_community"}
    if kind == "request":
        return {"request_song"}
    return set()


def _label_in_text(text: str, label: str) -> bool:
    needle = " ".join(str(label or "").split()).strip()
    if not needle:
        return False
    if needle.casefold() in str(text or "").casefold():
        return True
    words = [word for word in re.findall(r"[a-z0-9]+", needle.casefold()) if len(word) >= 4 and word not in _STOP]
    if len(words) < 2:
        return False
    lowered = str(text or "").casefold()
    return all(word in lowered for word in words)


def _tokens(text: str) -> list[str]:
    return [
        word
        for word in re.findall(r"[a-z0-9']+", str(text or "").casefold())
        if len(word) >= 4 and word not in _STOP
    ]


def _sentences(script: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", str(script or "").strip()) if part.strip()]


def _norm_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()


def _parse_time(value: str) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _same_day(left: datetime | None, right: datetime) -> bool:
    return bool(left and left.date() == right.date())


def _recent_breaks(history: dict[str, Any], host_key: str, when: datetime) -> list[dict[str, Any]]:
    hosts = history.get("hosts") if isinstance(history.get("hosts"), dict) else {}
    rows = [item for item in hosts.get(host_key) or [] if isinstance(item, dict)]
    kept = []
    for item in rows:
        at = _parse_time(str(item.get("at") or ""))
        if at is None or when - at <= timedelta(hours=KEEP_HOURS):
            kept.append(item)
    return kept[:KEEP_BREAKS]


def _prune(rows: list[dict[str, Any]], when: datetime) -> list[dict[str, Any]]:
    kept = []
    for item in rows:
        at = _parse_time(str(item.get("at") or ""))
        if at is not None and when - at > timedelta(hours=KEEP_HOURS):
            continue
        kept.append(item)
    return kept[:KEEP_BREAKS]


def _load_state(path: Path | None) -> dict[str, Any]:
    target = path or DEFAULT_STATE
    if not target.is_file():
        return {"hosts": {}}
    try:
        data = json.loads(target.read_text(encoding="utf-8-sig"))
    except Exception:
        return {"hosts": {}}
    if not isinstance(data, dict):
        return {"hosts": {}, "station_openings": [], "station_closings": []}
    hosts = data.get("hosts")
    if not isinstance(hosts, dict):
        hosts = {}
    openings = data.get("station_openings")
    closings = data.get("station_closings")
    return {
        "hosts": hosts,
        "station_openings": [str(item) for item in openings] if isinstance(openings, list) else [],
        "station_closings": [str(item) for item in closings] if isinstance(closings, list) else [],
    }


def _save_state(data: dict[str, Any], path: Path | None) -> None:
    target = path or DEFAULT_STATE
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    temporary = target.with_suffix(".tmp")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(target)

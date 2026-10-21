"""Conversational DJ-break structure: coaching + validation.

Standard generated breaks need a natural open, DJ-voiced content, and a clean
exit. Source notes (daily.csv birthdays, fun days, etc.) are facts to paraphrase,
not finished scripts. Station alerts, approved custom scripts, and true short
song intros are exempt from the full open/content/exit gate.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Soft spoken limits (≈150 wpm). Show opens may run a bit longer.
_SOFT_WORD_LIMITS = {
    "show_open": 190,
    "birthday": 140,
    "fun_day": 140,
    "announcement": 140,
    "question": 130,
    "rss": 140,
    "personal": 130,
    "default": 150,
}
_SOFT_SECONDS = {
    "show_open": 80,
    "birthday": 55,
    "fun_day": 55,
    "default": 60,
}
_WORDS_PER_MINUTE = 150.0

_EXEMPT_SUBJECTS = frozenset({"alert", "custom", "authored", "station_alert"})
_EXEMPT_EVENT_TYPES = frozenset({"station alert", "alert"})
_SHORT_INTRO_EVENTS = frozenset(
    {"artist spotlight", "coming up", "coming up next", "music story"}
)
_SHORT_INTRO_SUBJECTS = frozenset({"music", "music_history", "seventies", "blues"})

_ABRUPT_FACT_OPEN = re.compile(
    r"(?i)^\s*(?:"
    r"today is\b|"
    r"it(?:'s| is) (?:national |international )?[\w' .-]{0,40}(?:day|month|birthday)\b|"
    r"happy birthday to\b|"
    r"(?:born|died) (?:on )?(?:this day|october|january|february|march|april|may|june|"
    r"july|august|september|november|december)\b|"
    r"on this day\b|"
    r"celebrity birthday\b|"
    r"fun fact\b|"
    r"did you know that\b"
    r")"
)

_NATURAL_OPEN = re.compile(
    r"(?i)^\s*(?:"
    r"good (?:morning|afternoon|evening)\b|"
    r"hey(?: there| everybody| everyone| folks| friends)?\b|"
    r"hi(?: there| everybody| everyone| folks)?\b|"
    r"hello\b|"
    r"welcome(?: in| back| to|,)?\b|"
    r"(?:dj\s+)?mo(?:e)?(?:\s+here|\s+'?s\s+here|\s+settling|\s+hanging)\b|"
    r"(?:i(?:'m| am)|this is)\s+(?:dj\s+)?(?:mo|moe|kathy|bailey|johnny|dave|flea|pete|casey|larry)\b|"
    r"settling in\b|"
    r"hanging out\b|"
    r"hope (?:that |your |the )?(?:coffee|tea|day|morning|afternoon)\b|"
    r"how(?:'s| is| are) (?:everyone|y'all|you all|your)\b|"
    r"glad (?:you(?:'re| are)|to)\b|"
    r"thanks for (?:tuning|joining|listening|hanging)\b|"
    r"all right[,.]?\s+(?:so\b|we(?:'re| are)\b)|"
    r"so[,.]?\s+(?:i(?:'ve| have)|we(?:'re| are)|looking|checking)\b|"
    r"i was (?:looking|checking|thinking|flipping|going)\b|"
    r"looking through\b|"
    r"noticed\b|"
    r"wanted to (?:share|mention|say)\b"
    r")"
)

_NATURAL_EXIT = re.compile(
    r"(?i)\b(?:"
    r"back to the music\b|"
    r"let(?:'s| us) get (?:back|this|the)\b|"
    r"here(?:'s| is) (?:another|the next|more)\b|"
    r"more (?:music|trop|tunes|songs)\b|"
    r"keep(?:ing)? (?:it |the )?(?:rolling|going|company)\b|"
    r"stick around\b|"
    r"hang(?:ing)? (?:out|tight|with)\b|"
    r"you(?:'re| are) (?:hanging|listening|tuned)\b|"
    r"right here on\b|"
    r"on moe'?s place\b|"
    r"request a song\b|"
    r"mosplaceradio\.com\b|"
    r"coming up\b|"
    r"up next\b|"
    r"later in the mix\b|"
    r"enjoy\b|"
    r"woosah\b|"
    r"all right[,.]?\s+(?:let(?:'s| us)|we)\b|"
    r"that(?:'s| is) (?:enough|it for now|the scoop)\b|"
    r"enough from me\b|"
    r"music(?:'s| is) waiting\b|"
    r"get this morning rolling\b|"
    r"let(?:'s| us) get back\b"
    r")"
)

_GENERIC_ANNOUNCER_OPEN = re.compile(
    r"(?i)^\s*(?:"
    r"greetings(?:[, ]+listeners)?\b|"
    r"ladies and gentlemen\b|"
    r"welcome to another (?:exciting |wonderful )?(?:broadcast|segment|show)\b|"
    r"in today(?:'s|s) segment\b|"
    r"we(?:'re| are) so (?:thrilled|excited|honored)\b|"
    r"as your (?:virtual )?dj\b"
    r")"
)

_GENERIC_ANNOUNCER_EXIT = re.compile(
    r"(?i)\b(?:"
    r"stay tuned for more exciting content\b|"
    r"thank you for your continued support\b|"
    r"this concludes (?:our|this) (?:segment|broadcast)\b|"
    r"until next time,? (?:dear )?listeners\b"
    r")"
)

_HOST_CONFLICT_MARKERS: dict[str, tuple[re.Pattern[str], ...]] = {
    "mo": (
        re.compile(r"(?i)\bfilthy chooches\b"),
        re.compile(r"(?i)\bi(?:'m| am) kathy\b"),
        re.compile(r"(?i)\bi(?:'m| am) bailey\b"),
    ),
    "kathy": (
        re.compile(r"(?i)\bwoosah\b"),
        re.compile(r"(?i)\bi(?:'m| am)(?:\s+dj)?\s+mo\b"),
    ),
    "bailey": (
        re.compile(r"(?i)\bwoosah\b"),
        re.compile(r"(?i)\bfilthy chooches\b"),
        re.compile(r"(?i)\bi(?:'m| am)(?:\s+dj)?\s+mo\b"),
    ),
}

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")


@dataclass
class StructureIssue:
    code: str
    message: str


@dataclass
class StructureResult:
    ok: bool
    issues: list[StructureIssue] = field(default_factory=list)
    required: bool = True
    mode: str = "full"  # full | soft | exempt

    @property
    def reasons(self) -> list[str]:
        return [issue.message for issue in self.issues]


def _norm(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def _norm_cf(text: str) -> str:
    return _norm(text).casefold()


def _sentences(script: str) -> list[str]:
    text = _norm(script)
    if not text:
        return []
    parts = [part.strip() for part in _SENTENCE_SPLIT.split(text) if part.strip()]
    return parts or ([text] if text else [])


def _word_count(script: str) -> int:
    return len(re.findall(r"[A-Za-z0-9']+", script or ""))


def _est_seconds(script: str) -> float:
    return (_word_count(script) / _WORDS_PER_MINUTE) * 60.0


def _event_key(event_type: str) -> str:
    return _norm_cf(event_type)


def _subject_key(subject: str) -> str:
    return _norm_cf(subject).replace(" ", "_")


def is_show_open(event_type: str = "") -> bool:
    return _event_key(event_type) == "show open"


def is_structure_exempt(
    *,
    event_type: str = "",
    subject: str = "",
    station_alert: bool = False,
    authored_script: bool = False,
    custom_script: bool = False,
) -> bool:
    """Station alerts and approved custom/authored scripts keep their own path."""
    if station_alert or authored_script or custom_script:
        return True
    kind = _subject_key(subject)
    if kind in _EXEMPT_SUBJECTS:
        return True
    if _event_key(event_type) in _EXEMPT_EVENT_TYPES:
        return True
    return False


def is_short_song_intro(
    *,
    event_type: str = "",
    subject: str = "",
    soft_short: bool = False,
) -> bool:
    """True short song intros / teases — not a full show-open welcome."""
    if soft_short:
        return True
    event = _event_key(event_type)
    kind = _subject_key(subject)
    if event in _SHORT_INTRO_EVENTS and kind in _SHORT_INTRO_SUBJECTS | {""}:
        return True
    return False


def requires_conversational_structure(
    *,
    event_type: str = "",
    subject: str = "",
    station_alert: bool = False,
    authored_script: bool = False,
    custom_script: bool = False,
) -> bool:
    """Full open / content / exit expected for standard generated breaks."""
    if is_structure_exempt(
        event_type=event_type,
        subject=subject,
        station_alert=station_alert,
        authored_script=authored_script,
        custom_script=custom_script,
    ):
        return False
    if is_short_song_intro(event_type=event_type, subject=subject):
        return False
    kind = _subject_key(subject)
    event = _event_key(event_type)
    if event == "show open" or kind == "show_open":
        return True
    if kind in {
        "birthday",
        "fun_day",
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
        "handoff",
    }:
        return True
    if event in {"check-in", "weekend check-in", "listener memory"}:
        return True
    return kind not in {"", "music"} or bool(event)


def needs_conversational_structure(
    subject: str = "",
    event_type: str = "",
    *,
    station_alert: bool = False,
    authored_script: bool = False,
    custom_script: bool = False,
) -> bool:
    """Positional-friendly alias used by break_continuity.focus_spoken_break."""
    return requires_conversational_structure(
        event_type=event_type,
        subject=subject,
        station_alert=station_alert,
        authored_script=authored_script,
        custom_script=custom_script,
    )


def resolve_subject_kind(
    *,
    event_type: str = "",
    station_alert: bool = False,
    custom_script: bool = False,
    authored_script: bool = False,
    music_history: bool = False,
    blues: bool = False,
    seventies: bool = False,
    birthday: bool = False,
    question: bool = False,
    fun_day: bool = False,
    announcement: bool = False,
    friends: bool = False,
    books: bool = False,
    dogs: bool = False,
    farmstand: bool = False,
    personal: bool = False,
    engagement: bool = False,
    talking: bool = False,
    rss: bool = False,
) -> str:
    """Pick the break subject without letting birthday hijack Show Open structure."""
    if station_alert:
        return "alert"
    if custom_script or authored_script:
        return "custom"
    if music_history:
        return "music_history"
    if blues:
        return "blues"
    if seventies:
        return "seventies"
    # Show Open keeps welcome/exit structure even when a birthday is pending.
    if is_show_open(event_type):
        return "show_open"
    if _event_key(event_type) in {"handoff", "show close", "final half hour"}:
        return "handoff"
    if birthday:
        return "birthday"
    if question:
        return "question"
    if fun_day:
        return "fun_day"
    if announcement:
        return "announcement"
    if friends:
        return "friends"
    if books:
        return "books"
    if dogs:
        return "dogs"
    if farmstand:
        return "farmstand"
    if personal:
        return "personal"
    if engagement:
        return "engagement"
    if talking:
        return "talking"
    if rss:
        return "rss"
    return "music"


# Back-compat alias used by verify / callers that prefer the longer name.
resolve_subject_kind_for_event = resolve_subject_kind


def break_shape_coaching(*, event_type: str = "", subject: str = "") -> str:
    """Shared one-subject coaching suffix — greetings allowed on standard breaks."""
    return break_shape_suffix(event_type=event_type, subject=subject)


def break_shape_suffix(*, event_type: str = "", subject: str = "") -> str:
    event = _event_key(event_type)
    kind = _subject_key(subject) or resolve_subject_kind(event_type=event_type)
    if event == "show open" or kind == "show_open":
        return (
            " Write one flowing show-open in THIS host's personality. Welcome listeners "
            "naturally, deliver today's thought in their voice, and exit cleanly to the music. "
            "Source notes are facts to paraphrase — never read them verbatim. "
            "Do not copy a sample. Do not invent a visit, listener, or place. "
            "Do not add a second holiday, headline, or unsourced story."
        )
    if is_short_song_intro(event_type=event_type, subject=kind):
        return (
            " Keep it a short song intro: brief lead-in, one music beat from supplied facts, "
            "smooth hand back to the song. Do not paste a source note. Do not invent a full welcome."
        )
    return (
        " Write one flowing break in THIS host's personality, already written above: their voice "
        "style, humor, interests, opening style, and closing style. It must sound like that person, "
        "not a generic announcer and not another DJ. A catchphrase from their list is optional, "
        "one at most, and only if it belongs in the thought. "
        "Open with a natural conversational lead-in when this is a standard topic break — "
        "do not start on a raw source fact. "
        "Stay on this one subject until the thought is finished, then give a short natural exit "
        "back to the music. A short break is better than filler. "
        "Do not announce a song that was not supplied, and do not use the same coming-up formula "
        "every break. Use only the facts supplied for this subject — paraphrase source notes; "
        "do not invent a visit, a listener, or a place. "
        "Do not add a second holiday, headline, birthday, weekend story, website, request, or "
        "the weather. Do not announce a song that was not supplied."
    )


def one_subject_coaching(
    subject: str,
    *,
    event_type: str = "",
    label: str = "",
    note: str = "",
    serious: bool = False,
) -> str:
    """ONE SUBJECT line for the prompt. Show Open + birthday stays show-open shaped."""
    kind = _subject_key(subject)
    who = _norm(label) or "the subject"
    if kind == "alert":
        return ""
    if kind in {"music_history", "blues", "seventies"}:
        return "ONE SUBJECT: This music segment."
    if kind == "show_open":
        if label:
            return (
                f"ONE SUBJECT: Show open — welcome listeners, then share {who} conversationally "
                "from the supplied note (paraphrase facts; never read the note verbatim), "
                "then exit to the music."
            )
        return (
            "ONE SUBJECT: Show open — welcome listeners, set the show, deliver today's first "
            "thought in this host's voice, then exit to the music."
        )
    if kind == "birthday":
        return (
            f"ONE SUBJECT: {who}'s birthday. Open conversationally, wish them well "
            "(happy birthday before the name), paraphrase only the supplied note, then exit "
            "to the music. Source notes are facts, not a finished script."
        )
    if kind == "question":
        return f"ONE SUBJECT: The question already supplied ({who}). Ask it like a person."
    if kind == "fun_day":
        if serious:
            return (
                f"ONE SUBJECT: {who}. Use the supplied note. Warm and respectful. "
                "No joke, and no invented medical detail. Paraphrase — do not read the note verbatim."
            )
        return (
            f"ONE SUBJECT: {who}. Use the supplied note conversationally. Do not stop after the name. "
            "Paraphrase — do not read the note verbatim."
        )
    if kind == "announcement":
        return (
            "ONE SUBJECT: The community announcement already supplied. Use its details "
            "conversationally — paraphrase, do not read a bulletin."
        )
    if kind == "friends":
        return f"ONE SUBJECT: The Friends episode already supplied ({who})."
    if kind == "books":
        return f"ONE SUBJECT: The book already supplied ({who})."
    if kind == "dogs":
        return f"ONE SUBJECT: The dog already supplied ({who})."
    if kind == "farmstand":
        return f"ONE SUBJECT: The Bakehouse mention already supplied ({who})."
    if kind == "personal":
        return "ONE SUBJECT: The personal note already supplied. Paraphrase in this host's voice."
    if kind == "engagement":
        return "ONE SUBJECT: The listener question already supplied. Ask it like a person."
    if kind == "talking":
        town = _norm(note)
        place = f"{who} in {town}" if town else who
        return f"ONE SUBJECT: The local place already supplied ({place}). Use only that name and town."
    if kind == "rss":
        return (
            f"ONE SUBJECT: The feed story already supplied ({who}). Use its real details — "
            "paraphrase TOPIC/DETAIL, never read them verbatim."
        )
    if kind == "handoff":
        return "ONE SUBJECT: The handoff / close already required by this event."
    return (
        "ONE SUBJECT: The music. Talk about the hour or a supplied song. "
        "Do not announce a title and stop."
    )


def structure_coaching_text(
    *,
    event_type: str = "",
    subject: str = "",
    label: str = "",
    note: str = "",
    station_alert: bool = False,
    authored_script: bool = False,
) -> str:
    """Extra prompt coaching for open / paraphrase / exit. Empty when exempt."""
    if is_structure_exempt(
        event_type=event_type,
        subject=subject,
        station_alert=station_alert,
        authored_script=authored_script,
    ):
        return ""
    event = _event_key(event_type)
    kind = _subject_key(subject)
    who = _norm(label) or "the subject"
    note_hint = _norm(note)

    if is_short_song_intro(event_type=event_type, subject=subject):
        return (
            "SHORT INTRO SHAPE: Brief conversational lead-in, one music beat from the "
            "supplied facts, then a smooth hand back to the song. Do not paste a source note."
        )

    if event == "show open" or kind == "show_open":
        birthday_bit = ""
        if label or note_hint:
            birthday_bit = (
                f" If a birthday or daily note is supplied ({who}), weave it as one "
                "conversational beat after the welcome — paraphrase the facts; never "
                "read the source note verbatim and never start the break on the fact. "
                "Welcome first, then the content, then exit to the music."
            )
        return (
            "SHOW OPEN SHAPE (required): (1) Natural welcome naming this host and "
            "Moe's Place Radio once, fitting the daypart. (2) Conversational lead-in "
            "into today's first thought. (3) Deliver any supplied daily content in the "
            "host's voice — source notes are facts to paraphrase, not a script to read. "
            "(4) Natural exit back to the music or into the show. "
            "Never open on a raw birthday line, headline, or calendar fact. "
            "Never end mid-thought after the fact."
            + birthday_bit
        )

    if kind == "birthday":
        return (
            f"BIRTHDAY BREAK SHAPE (required): Open with a natural greeting or "
            f"conversational lead-in in THIS host's voice. Lead into {who}'s birthday "
            "like something you noticed and wanted to share. Paraphrase only the "
            "supplied name and note — never invent biography, never read the note "
            "verbatim, never start with 'Today is … birthday'. Wish them well with "
            "happy birthday before the name when you make the wish. Close with a "
            "natural exit back to the music. A station ID may appear once inside the "
            "open or exit when it fits — do not ban greetings on birthday breaks."
        )

    return (
        "STANDARD BREAK SHAPE (required): Natural conversational open or lead-in, "
        "then the supplied subject in this host's voice, then a natural exit or "
        "transition back to the music. Source notes are facts to paraphrase — never "
        "paste them as the finished break. Do not start on a raw fact line. Do not "
        "end abruptly after the fact. Do not force the same greeting every break."
    )


def birthday_extra_coaching(label: str = "", event_type: str = "", **_kwargs) -> str:
    """Birthday-specific add-on. Never bans greetings/station ID on standard breaks."""
    who = _norm(label) or "them"
    if is_show_open(event_type):
        return (
            f" Birthday content: after the welcome, lead into {who} conversationally. "
            f"Say happy birthday first, then the name: Happy birthday to {who}. "
            "Paraphrase only the supplied note — never read it verbatim. Never invent biography. "
            "Never start the whole break on the birthday fact. Never stretch a word: write here, not heeer."
        )
    return (
        f" The birthday is this break's subject. Open conversationally, then wish them well: "
        f"Happy birthday to {who}. Never say the name before happy birthday when you make the wish. "
        "Use only the supplied name and note, paraphrased in this host's voice — never read the note "
        "verbatim. Do not invent biography. Do not mention a weekend, the mix, or variety as filler. "
        "Do not say from all of us. Never stretch a word: write here, not heeer. "
        "End with a natural exit back to the music."
    )


# Alias used by Producer / verify while the call site settles.
birthday_structure_coaching = birthday_extra_coaching


def _note_is_verbatim(script: str, note: str) -> bool:
    detail = _norm_cf(note)
    spoken = _norm_cf(script)
    if len(detail) < 24:
        return False
    if detail in spoken and len(detail.split()) >= 6:
        if spoken == detail or spoken.startswith(detail) or spoken.endswith(detail):
            return True
        note_words = set(re.findall(r"[a-z0-9']+", detail))
        script_words = re.findall(r"[a-z0-9']+", spoken)
        if not note_words or not script_words:
            return False
        overlap = sum(1 for word in script_words if word in note_words)
        if overlap / max(len(script_words), 1) >= 0.85 and len(script_words) <= len(note_words) + 8:
            return True
    return False


def _starts_with_source_fact(script: str, label: str, note: str) -> bool:
    sentences = _sentences(script)
    if not sentences:
        return False
    first = sentences[0]
    if _NATURAL_OPEN.search(first):
        return False
    if _ABRUPT_FACT_OPEN.search(first):
        return True
    label_cf = _norm_cf(label)
    note_cf = _norm_cf(note)
    first_cf = _norm_cf(first)
    if label_cf and first_cf.startswith(label_cf) and len(first.split()) <= 14:
        return True
    if note_cf and (
        first_cf == note_cf
        or first_cf.startswith(note_cf[: min(40, len(note_cf))])
    ):
        return True
    if label_cf and re.match(
        rf"(?i)^{re.escape(label)}\b.{{0,40}}\b(?:was born|born|birthday)\b",
        first,
    ):
        return True
    return False


def _has_natural_open(script: str, *, mode: str) -> bool:
    sentences = _sentences(script)
    if not sentences:
        return False
    head = " ".join(sentences[:2])
    if _NATURAL_OPEN.search(sentences[0]) or _NATURAL_OPEN.search(head):
        return True
    if mode == "soft":
        if re.search(r"(?i)\b(?:that|this|here(?:'s| is)|coming up|love this)\b", sentences[0]):
            return True
    return False


def _has_natural_exit(script: str, *, mode: str) -> bool:
    sentences = _sentences(script)
    if not sentences:
        return False
    if len(sentences) == 1 and mode == "soft":
        return bool(_NATURAL_EXIT.search(sentences[0]))
    tail = " ".join(sentences[-2:])
    if _NATURAL_EXIT.search(sentences[-1]) or _NATURAL_EXIT.search(tail):
        return True
    if re.search(r"(?i)\b(?:music|song|mix|tune|trop|track|spin)\b", sentences[-1]) and not _ABRUPT_FACT_OPEN.search(
        sentences[-1]
    ):
        return True
    return False


def _personality_conflict(script: str, host: str) -> str:
    host_key = _norm_cf(host).replace("dj", "").strip()
    markers = _HOST_CONFLICT_MARKERS.get(host_key) or ()
    for pattern in markers:
        if pattern.search(script or ""):
            return f"Uses wording that conflicts with {host_key or 'this host'}'s voice."
    if _GENERIC_ANNOUNCER_OPEN.search(_norm(script)):
        return "Opens with a generic announcer greeting that conflicts with a real DJ voice."
    if _GENERIC_ANNOUNCER_EXIT.search(script or ""):
        return "Ends with a generic announcer exit that conflicts with a real DJ voice."
    return ""


def validate_break_structure(
    script: str,
    *,
    subject: str = "",
    label: str = "",
    note: str = "",
    event_type: str = "",
    host: str = "",
    station_alert: bool = False,
    authored_script: bool = False,
    custom_script: bool = False,
    paraphrase_expected: bool = True,
) -> StructureResult:
    """Flag incomplete standard breaks. Exempt paths always pass."""
    if is_structure_exempt(
        event_type=event_type,
        subject=subject,
        station_alert=station_alert,
        authored_script=authored_script,
        custom_script=custom_script,
    ):
        return StructureResult(ok=True, required=False, mode="exempt")

    text = _norm(script)
    issues: list[StructureIssue] = []
    kind = _subject_key(subject)
    event = _event_key(event_type)
    short = is_short_song_intro(event_type=event_type, subject=subject)
    required = requires_conversational_structure(
        event_type=event_type,
        subject=subject,
        station_alert=station_alert,
        authored_script=authored_script,
        custom_script=custom_script,
    )
    mode = "soft" if short or not required else "full"

    if not text:
        return StructureResult(
            ok=False,
            issues=[StructureIssue("empty", "Break script is empty.")],
            required=required,
            mode=mode,
        )

    if mode == "full" or (mode == "soft" and (label or note)):
        if paraphrase_expected and note and _note_is_verbatim(text, note):
            issues.append(
                StructureIssue(
                    "verbatim_source_note",
                    "Reads the source note nearly verbatim instead of paraphrasing in DJ voice.",
                )
            )
        if _starts_with_source_fact(text, label, note):
            issues.append(
                StructureIssue(
                    "abrupt_source_fact_start",
                    "Starts abruptly on a source fact with no conversational lead-in.",
                )
            )
        if mode == "full" and not _has_natural_open(text, mode=mode):
            if event == "show open" or kind in {
                "show_open",
                "birthday",
                "fun_day",
                "rss",
                "question",
            }:
                issues.append(
                    StructureIssue(
                        "missing_lead_in",
                        "Missing a natural greeting or conversational lead-in.",
                    )
                )
        if mode == "full" and not _has_natural_exit(text, mode=mode):
            issues.append(
                StructureIssue(
                    "missing_exit",
                    "Ends without a natural exit or transition back to the music/show.",
                )
            )
        elif mode == "soft" and len(_sentences(text)) >= 2 and not _has_natural_exit(text, mode=mode):
            issues.append(
                StructureIssue(
                    "missing_exit",
                    "Short intro ends abruptly without a hand back to the music.",
                )
            )

    conflict = _personality_conflict(text, host)
    if conflict:
        issues.append(StructureIssue("personality_conflict", conflict))

    limit_key = kind if kind in _SOFT_WORD_LIMITS else "default"
    if event == "show open":
        limit_key = "show_open"
    word_limit = _SOFT_WORD_LIMITS.get(limit_key, _SOFT_WORD_LIMITS["default"])
    words = _word_count(text)
    if words > word_limit:
        issues.append(
            StructureIssue(
                "soft_word_limit",
                f"Exceeds soft word limit ({words} > {word_limit}) for {limit_key}.",
            )
        )
    seconds_key = limit_key if limit_key in _SOFT_SECONDS else "default"
    sec_limit = _SOFT_SECONDS.get(seconds_key, _SOFT_SECONDS["default"])
    seconds = _est_seconds(text)
    if seconds > sec_limit + 5:
        issues.append(
            StructureIssue(
                "soft_duration_limit",
                f"Exceeds soft duration (~{seconds:.0f}s > {sec_limit}s) for {seconds_key}.",
            )
        )

    result = StructureResult(ok=not issues, issues=issues, required=required, mode=mode)
    return result


def structure_failure_codes(result: StructureResult | list[str] | None) -> list[str]:
    """Normalize StructureResult (or legacy list) to failure code strings."""
    if result is None:
        return []
    if isinstance(result, list):
        return [str(item) for item in result]
    if getattr(result, "ok", False):
        return []
    return [issue.code for issue in getattr(result, "issues", []) or []]


def format_structure_failure(result: StructureResult) -> str:
    if result.ok:
        return ""
    lines = [f"- {issue.code}: {issue.message}" for issue in result.issues]
    return "Break failed conversational structure validation:\n" + "\n".join(lines)

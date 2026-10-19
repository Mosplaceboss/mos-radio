"""Shared MOSLIVE human-DJ rules — prompt + strip/validate.

One compact source for LiveDJ generate (Producer / livedj_context) and
ai_provider_policy repair/validation. Realistic does not mean making things up.
"""

from __future__ import annotations

import re

HUMAN_DJ_MUST_FOLLOW = """
MOSLIVE HUMAN DJ RULES (MUST FOLLOW):
The goal is a REAL LOCAL RADIO DJ — not an AI assistant, narrator, announcer, or script reader.
REALISTIC DOES NOT MEAN MAKING THINGS UP.

1 SOUND HUMAN — contractions; conversational; mix sentence length; So/And/But/You know/Anyway sparingly; talk TO one listener, not AT them; fragments OK. Not a news anchor (except news), not corporate, not an ad (unless this is a commercial). No perfect paragraphs. Don't over-explain. Don't repeat the station name. Don't overdo um/uh/like/you know.
2 NEVER INVENT FACTS (HARD) — no businesses, restaurants, bars, concerts, venues, events, local happenings, roads, towns, neighborhoods, people, artists, songs, birthdays, news, weather, traffic, sports results, listener comments/requests, station events, personal experiences, visits, or conversations unless THIS prompt supplies them. If it's missing, stay generic and move on. Never Harbor Grill or any unsourced place.
3 NEVER FAKE LOCAL KNOWLEDGE — only named local places from supplied data. No random Dracut/Lowell/Lawrence/Boston businesses.
4 NEVER PRETEND IT HAPPENED — no "I was just talking to…", "I was over at…", "I was at the cafe…", "I was at the bar…", "I was at the corner…", "someone just requested…", "somebody called in…", "I was driving…", "I stopped at…", "I just flipped through the playlist…" unless THIS prompt has that event. No invented first-person scene and no made-up place the host visited. If look-ahead music is supplied, just say coming up.
5 SHORT BREAKS — natural radio rhythm, then back to the music.
6 DON'T TEMPLATE — vary structure; don't make every break perfect or identical; don't force catchphrases.
7 PERSONALITY (this host only) — Mo: friendly NE trop-rock, relaxed, slightly sarcastic. Johnny J: experienced, dry, witty, not overly enthusiastic. Dave: friendly sports/social. Flea: energetic, mischievous. Bailey: funny, witty, warm, easygoing — no invented "I was at the cafe/bar/corner" scene. Never borrow another host's tropes.
8 CATCHPHRASES OPTIONAL — zero or one from this host's personality catchphrase list; shuffle so they are not always the same line; add new lines to that list anytime. Never stack. Don't lean on Hey folks / You're listening to / Coming up next / Right here on / Stick around / Don't go anywhere.
9 REACT TO MUSIC when the song/artist is known — never invent song stories.
10 Real transitions sparingly.
11 NEVER EXPLAIN THE AI — no "as an AI", "virtual DJ", or how you were generated.
12 FACT CONFIDENCE — if it is not explicit, verified, current, and in this prompt, omit it. Never guess.
13 HUMANIZATION TEST — would a listener assume a real local DJ said this? If not, shorter, more conversational, less polished.
14 Don't overdo um/uh/you know/like.

BANNED AI FILLER (never say): Greetings listeners; In today's segment; Let's dive into; Stay tuned for more exciting content; I hope you're having a wonderful day; As an AI; virtual DJ; I just flipped through the playlist; flipping through the playlist.
REQUESTS: Every host. If you invite a song request, say click Request a Song at the top of mosplaceradio.com. Never send a request to Community.
COMMUNITY: Every host. Only when you ask the listener a question (How's your day going? the question of the day, any question) — and it is not a song request — follow it with: Let us know what you think by clicking Community at mosplaceradio.com. We would love to hear from you! No question, no Community line. Say it once per break, never repeated. Never say at the top of. Never say dot com. Never say Moe's Place. Never drop it in the chat. Never name Facebook as the destination.
WEBSITE: Every host. Most breaks stay music-first. At most ONE website aside per break, and only when it fits the moment. Never recite a menu of site features. Never stack a feature list. Skip the aside on Show Open, Handoff, Show Close, Lottery Results, and news reads. If this break already has a listener question, a farmstand mention, or another promo, skip the website aside.
Give one concrete reason to click and name the real section at mosplaceradio.com. Do not invent headlines, horoscope wording, who is playing, game results, or extra game rules. Do not spell out a web address.
Pick zero or one: Games — play while you listen, on the Games page at mosplaceradio.com. Mo's Word — everybody gets the same 5-letter station word, six tries, color clues, and a porch hangman if you miss; new at midnight Eastern. Lyric Drop — a short hint drops and you name the song or artist; eight daily clues, the same set for everyone. Daily Horoscope — what's in the stars, Daily Horoscope on mosplaceradio.com. Community Calendar — the community board on the homepage; do not invent a posted event. Local & World News — the homepage headline scroller; click a headline to open the story; do not invent a headline. Music History — the homepage music section beside the news; do not invent a fact. Also real, still only one: Letters to Casey, Stories, Recipes, What's On Tap Today, Sponsors, or Mo's Friends.
BAND LISTINGS: Bea's Band Listings on mosplaceradio.com change every Wednesday for weekend local shows. If you mention a show, ONE show is enough, and only when this prompt supplies that show. Never read the list. Point listeners to band schedules on mosplaceradio.com. Do not invent a band, room, or town.
THINGS TO DO: Pawpicked Events by Mo Himself. Mention ONE event, never the whole card, and only the event in PAWPICKED TODAY when that block is supplied. If it is not supplied, do not invent a night, room, or town.
BAKEHOUSE: Kathy only. If you mention Barn Door Bake House or Barndoor Bakehouse, invite listeners to click Barndoor Bakehouse at mosplaceradio.com. Never say Facebook. Never say check us out.
ONE CALL TO ACTION: Every host. Zero or one per break — never two. Do not end every break with a website, a request, or "We would love to hear from you." Community only after a real listener question. Request a Song only when this break is inviting a request. Kathy's Barndoor Bakehouse click only when she mentions the Bakehouse. Otherwise end on the music, a short thought, or the subject you were already on.
TIMES: Every host, any hour. If you mention a time, write it like 7 PM, 8:30 PM, or 10 AM (number plus AM or PM). Never o'clock, Oh Clock, or 3:00.
""".strip()

HUMAN_DJ_FINAL_CHECKLIST = """
HUMAN DJ FINAL CHECK (before TTS): contractions? talking TO the listener? zero invented facts/places/visits? zero banned AI filler? would a real local DJ say this? If not, shorten. If you asked the listener a question, say Let us know what you think by clicking Community at mosplaceradio.com. We would love to hear from you! Once per break, only after a question. Never say dot com. Never say Moe's Place. A song request uses click Request a Song. A Barn Door Bake House mention uses click Barndoor Bakehouse at mosplaceradio.com. Zero or one website aside, never a feature list. REALISTIC DOES NOT MEAN MAKING THINGS UP.
""".strip()

# Known invented-place example from the operator spec — fail unless THIS prompt names it.
_BANNED_UNSOURCED_PLACES = (
    "harbor grill",
)

_AI_FILLER_RES = (
    re.compile(r"\bgreetings listeners\b", re.I),
    re.compile(r"\bin today's segment\b", re.I),
    re.compile(r"\blet's dive into\b", re.I),
    re.compile(r"\bstay tuned for more exciting content\b", re.I),
    re.compile(r"\bi hope you're having a wonderful day\b", re.I),
    re.compile(r"\bas an ai\b", re.I),
    re.compile(r"\bvirtual dj\b", re.I),
)

_FAKE_VISIT_RES = (
    re.compile(r"\bi was over at\b", re.I),
    re.compile(r"\bi was just talking to\b", re.I),
    re.compile(r"\bsome(?:one|body)\s+just\s+requested\b", re.I),
    re.compile(r"\bsome(?:one|body)\s+(?:just\s+)?call(?:ed)?\s+in\b", re.I),
    re.compile(r"\bi was driving(?:\s+(?:down|through|by|around))?\b", re.I),
    re.compile(r"\bi stopped at\b", re.I),
)
# Generic first-person scene-setting: "I was at the cafe on the corner."
_INVENTED_SCENE_RE = re.compile(r"\bi was at (?:the|a|an)\b", re.I)
_GENERIC_SCENE_WORDS = frozenset({
    "cafe",
    "cafes",
    "bar",
    "bars",
    "corner",
    "diner",
    "diners",
    "pub",
    "tavern",
    "restaurant",
    "coffee",
    "shop",
    "place",
    "spot",
    "joint",
    "street",
    "block",
    "town",
    "neighborhood",
    "little",
    "local",
    "small",
    "old",
    "one",
})
_SUPPLIED_VISIT_MARKERS = (
    "life memory",
    "personal memory",
    "verified personal fact",
)

_PLAYLIST_FLIP_RE = re.compile(
    r"(?i)\b(?:i(?:'m| am)?\s+)?(?:just\s+)?flipp(?:ed|ing)\s+through\s+the\s+playlist"
    r"(?:\s+here)?"
)
_REQUEST_INVITE_RE = re.compile(
    r"(?i)\b(?:song or a request|have a request|got a request|send a request|"
    r"make a request|want to request|requests are open|all requests|"
    r"request a song|request songs?|"
    r"have a song or|if you have a song|got a song or|"
    r"got a song to share|song to share|have got a song)\b"
)
_MOES_PLACE_RE = re.compile(r"(?i)\bMoe's Place\b")
_LOOSE_REQUEST_CLICK_RE = re.compile(r'(?i)click\s+"?request\s+songs?"?')
_REQUEST_DEST_RE = re.compile(
    r"(?i)click Request a Song at the top of Mo's Place Radio(?:\s+dot\s+com)?"
)
_CHECK_OUT_BAKEHOUSE_RE = re.compile(
    r"(?i)\bcheck(?:\s+us)?\s+out\s+(?:the\s+)?(?:Barn\s+Door|Barndoor)\s+Bake\s*house\b"
    r"(?!\s+at\s+mosplaceradio\.com)"
)
_BAKEHOUSE_LINK_RE = re.compile(
    r"(?i)\bclick the (?:Barn\s+Door|Barndoor)\s+Bake\s*house link\b"
    r"(?!\s+at\s+mosplaceradio\.com)"
)
_BAKEHOUSE_FOR_LINK_RE = re.compile(
    r"(?i)\bclick the link for (?:the\s+)?(?:Barn\s+Door|Barndoor)\s+Bake\s*house\b"
    r"(?!\s+at\s+mosplaceradio\.com)"
)
_BAKEHOUSE_MENTION_RE = re.compile(r"(?i)\b(?:barn\s*door|barndoor)\s+bake\s*house\b")
_BAKEHOUSE_CLICK_RE = re.compile(
    r"(?i)\bclick\s+(?:the\s+link\s+for\s+(?:the\s+)?)?(?:barn\s*door|barndoor)\s+bake\s*house\b"
)
_BAKEHOUSE_VAGUE_CLICK_RE = re.compile(
    r"(?i)^(?:(?:so|and|just|you\s+can|go\s+ahead\s+and)[\s,]+)*"
    r"(?:click|tap|check\s+(?:it|them|us|that|this)\s+out|head\s+(?:over\s+)?to|visit)\b"
    r"(?=[^.!?]*?\b(?:link|mosplaceradio|website|for\s+more)\b)"
)
_OTHER_SITE_SECTION_RE = re.compile(
    r"(?i)\b(?:community|request\s+a\s+song|games?|horoscope|lyric\s+drop|mo's\s+word|"
    r"things\s+to\s+do|band\s+(?:listings|schedules)|calendar|news|music\s+history|recipes|"
    r"stories|sponsors|letters\s+to\s+casey)\b"
)
_DOUBLE_END_PUNCT_RE = re.compile(r"([!?][\"']?)\.(?!\.)")
_STRAIGHT_QUOTES = str.maketrans({"\u2018": "'", "\u2019": "'", "\u02bc": "'", "\u201c": '"', "\u201d": '"'})
_COMMUNITY_PRESENT_RE = re.compile(r"(?i)\b(?:select(?:ing)?|click(?:ing)?)\s+(?:on\s+)?Community\b")
_REQUEST_PRESENT_RE = re.compile(r"(?i)\bclick\s+Request\s+a\s+Song\b")
_COMMUNITY_CTA_LINE = "Let us know what you think by clicking Community at mosplaceradio.com."
_COMMUNITY_THANKS_LINE = "We would love to hear from you!"
_COMMUNITY_INVITE = f"{_COMMUNITY_CTA_LINE} {_COMMUNITY_THANKS_LINE}"
_COMMUNITY_INVITE_SHORT = _COMMUNITY_INVITE
_COMMUNITY_CANONICAL_RE = re.compile(
    r"(?i)^let us know what you think by clicking Community at mosplaceradio\.com\.?$"
)
_COMMUNITY_THANKS_RE = re.compile(r"(?i)^we(?:['\u2018\u2019]d|\s+would)\s+(?:really\s+|just\s+)?love\s+to\s+hear\s+from\s+(?:you|y'?all)\b[\s.!]*$")
_COMMUNITY_INTRO_RE = re.compile(
    r"(?i)^(?:have\s+something\s+on\s+your\s+mind|want\s+to\s+discuss\s+anything(?:\s+we\s+mention)?)\?$"
)
_COMMUNITY_LEAD_RE = re.compile(
    r"(?i)(?:\b(?:please|let'?s\s+get\s+a\s+conversation\s+started|so|and|or|just|then|by|now|you\s+can|feel\s+free\s+to|go\s+ahead\s+and|(?:let\s+us\s+know|tell\s+us)(?:\s+what\s+you\s+think)?|"
    r"to\s+answer|if\s+you\s+(?:want|wanna|would\s+like|'d\s+like)\s+to\s+"
    r"(?:answer|chime\s+in|share|weigh\s+in|talk\s+about\s+it|join\s+in))\b[\s,]*)+$"
)
_STIFF_COMMUNITY_RE = re.compile(
    r"(?i)\bclick\s+Community\s+at\s+the\s+top\s+of\s+"
    r"(?:"
    r"(?:https?://)?(?:www\.)?mosplaceradio\.com"
    r"|Moe'?s\s+Place(?:\s+Radio)?(?:\s+dot\s+com)?"
    r"|Mo'?s\s+Place(?:\s+Radio)?(?:\s+dot\s+com)?"
    r")"
)
_REQUEST_INVITE_LINE = "If you've got a request, click Request a Song at the top of mosplaceradio.com."
_BAKEHOUSE_CTA = "click Barndoor Bakehouse at mosplaceradio.com"
_BAKEHOUSE_INVITE = "Click Barndoor Bakehouse at mosplaceradio.com."
_AUDIENCE_INTERACT_RE = re.compile(
    r"(?i)\b("
    r"chime in|let us know|let me know|tell us|weigh in|sound off|"
    r"what do you think|i(?:'d| would) love to hear|"
    r"share your|drop (?:us )?a comment|join the conversation"
    r")\b"
)
_DISCOURSE_Q_RE = re.compile(
    r"(?i)\b(?:you know(?:\s+what)?|right|seriously|huh|come on|okay|ok|alright|yeah)\s*\?"
)
_LISTENER_ADDRESS_RE = re.compile(r"(?i)\b(?:you|your|you're|ya|anyone|anybody|listeners)\b")

_CLOSE_EVENT_MARKERS = (
    "handoff",
    "show close",
    "final half hour",
    "sign-off",
    "signoff",
)
_MIDSHIFT_HANDOFF_RE = re.compile(
    r"(?i)\b("
    r"hand(?:ing|s)? off|"
    r"hand(?:ing|s)? the (?:show|mic|reins)|"
    r"(?:kathy|pete|johnny j|johnny|bailey|mo|larry|lb|tony tone)\s+"
    r"(?:takes?|taking|is taking) over|"
    r"take(?:s|ing) (?:us |you )?(?:into|over to)\s+"
    r"(?:kathy|pete|johnny|bailey|mo|larry)|"
    r"wrap(?:ping)? (?:it |the show )?up|"
    r"that(?:'s| is) (?:gonna be|going to be) it for me|"
    r"close(?:ing)? out (?:the|my) show|"
    r"see you next (?:saturday|sunday)"
    r")\b"
)
_OTHER_HOST_NAME_RE = re.compile(
    r"(?i)\b(kathy|pete|johnny j|johnny|bailey|lowdown larry|larry|tony tone)\b"
)


def human_dj_must_follow_block() -> str:
    return HUMAN_DJ_MUST_FOLLOW


def human_dj_final_checklist() -> str:
    return HUMAN_DJ_FINAL_CHECKLIST


# Monday / Wednesday / Thursday / Friday only. One event, never the whole card.
_PAWPICKED_TODAY = {
    0: "Music Bingo with George at The Nest in Plaistow, New Hampshire, from 7 to 9 PM.",
    2: "Music Bingo with George at Casa Blanca Mexican Cantina in Andover, Massachusetts, from 7 to 9 PM.",
    3: "Karaoke with GForce Karaoke at Lynn's 102 Tavern in Hudson, New Hampshire, from 8 PM to midnight.",
    4: "Karaoke with GForce Karaoke at Lynn's 102 Tavern in Hudson, New Hampshire, from 8 PM to midnight.",
}


_SKIP_PAWPICKED_EVENTS = {
    "show open",
    "handoff",
    "show close",
    "final half hour",
    "lottery results",
}


def today_pawpicked_aside(when=None, event_type: str = "") -> str:
    """One Things To Do event for this weekday, or pawpicked: none. Not a lineup."""
    from datetime import date, datetime

    kind = str(event_type or "").strip().casefold()
    if kind in _SKIP_PAWPICKED_EVENTS or "lottery" in kind or kind == "news":
        return ""
    if when is None:
        when = datetime.now()
    if isinstance(when, datetime):
        weekday = when.weekday()
    elif isinstance(when, date):
        weekday = when.weekday()
    else:
        return "PAWPICKED TODAY:\npawpicked: none"
    line = _PAWPICKED_TODAY.get(int(weekday), "")
    if not line:
        return "PAWPICKED TODAY:\npawpicked: none"
    return (
        "PAWPICKED TODAY (optional Things To Do aside — this ONE event only):\n"
        f"- {line}\n"
        "- Mention it only if it fits this break. Do not add any other Pawpicked night. "
        "Point listeners to Things To Do on mosplaceradio.com."
    )


def _clauses(script: str) -> list[str]:
    text = str(script or "").strip()
    if not text:
        return []
    return [
        part.strip(" \t\"'")
        for part in re.split(r"(?<=[.!?;])\s+|\s+[—–-]\s+", text)
        if part.strip(" \t\"'")
    ]


def _join_clauses(clauses: list[str]) -> str:
    return " ".join(clause.rstrip() if clause.endswith((".", "!", "?")) else f"{clause}." for clause in clauses)


def _prompt_has_visit(prompt: str, sentence: str) -> bool:
    """Allow a first-person visit only when THIS prompt already contains that visit."""
    hay = str(prompt or "").casefold()
    if not hay.strip():
        return False
    needle = re.sub(r"\s+", " ", str(sentence or "")).strip().casefold()
    if len(needle) >= 24 and needle in hay:
        return True
    for pattern in _FAKE_VISIT_RES:
        match = pattern.search(sentence or "")
        if not match:
            continue
        tail = (sentence or "")[match.end() :].strip(" .,;:!")
        place = re.split(r"[,.]|\s+and\s+", tail, maxsplit=1)[0].strip()
        place = re.sub(r"^(?:the|a|an)\s+", "", place, flags=re.I)
        tokens = [tok for tok in re.findall(r"[A-Za-z][A-Za-z']{2,}", place) if tok.casefold() not in {"the", "and"}]
        if tokens and all(tok.casefold() in hay for tok in tokens[:3]):
            visit_markers = (
                "i was over at",
                "i was just talking to",
                "just requested",
                "called in",
                "i was driving",
                "i stopped at",
                "life memory",
                "personal memory",
            )
            if any(marker in hay for marker in visit_markers):
                return True
        return False
    return False


def sentence_is_ai_filler(sentence: str) -> bool:
    return any(pattern.search(sentence or "") for pattern in _AI_FILLER_RES)


def _prompt_supplies_named_visit(prompt: str, sentence: str, match: re.Match) -> bool:
    """Allow 'I was at the ...' only when this prompt supplies that named visit.

    Words like cafe, bar, and corner show up in the standing bans, so they
    never count as a supplied place.
    """
    hay = str(prompt or "").casefold()
    if not any(marker in hay for marker in _SUPPLIED_VISIT_MARKERS):
        return False
    tail = (sentence or "")[match.end() :]
    place = re.split(r"[,.]|\s+and\s+", tail, maxsplit=1)[0]
    tokens = [
        tok.casefold()
        for tok in re.findall(r"[A-Za-z][A-Za-z']{2,}", place)
        if tok.casefold() not in {"the", "and", "with", "for", "from"}
    ]
    named = [tok for tok in tokens if tok not in _GENERIC_SCENE_WORDS]
    if len(named) < 2:
        return False
    return all(tok in hay for tok in named[:3])


def sentence_is_invented_first_person_scene(sentence: str, prompt: str = "") -> bool:
    match = _INVENTED_SCENE_RE.search(sentence or "")
    if not match:
        return False
    return not _prompt_supplies_named_visit(prompt, sentence, match)


def sentence_is_fake_visit(sentence: str, prompt: str = "") -> bool:
    if sentence_is_invented_first_person_scene(sentence, prompt):
        return True
    if not any(pattern.search(sentence or "") for pattern in _FAKE_VISIT_RES):
        return False
    return not _prompt_has_visit(prompt, sentence)


def sentence_has_banned_place(sentence: str, prompt: str = "") -> bool:
    lowered = str(sentence or "").casefold()
    hay = str(prompt or "").casefold()
    for place in _BANNED_UNSOURCED_PLACES:
        if place in lowered and place not in hay:
            return True
    return False


def detect_ai_filler(script: str) -> str:
    for sentence in _clauses(script):
        if sentence_is_ai_filler(sentence):
            return "banned AI filler"
    return ""


def detect_fake_visit(script: str, prompt: str = "") -> str:
    for sentence in _clauses(script):
        if sentence_is_fake_visit(sentence, prompt):
            lowered = sentence.casefold()
            if sentence_is_invented_first_person_scene(sentence, prompt):
                return "invented first-person scene (I was at the)"
            if "i was over at" in lowered:
                return "fake visit (I was over at)"
            if "just requested" in lowered:
                return "fake listener request"
            if "call" in lowered:
                return "fake call-in"
            if "driving" in lowered:
                return "fake driving visit"
            if "stopped at" in lowered:
                return "fake stop-in visit"
            return "pretended event / fake visit"
    return ""


def detect_banned_place(script: str, prompt: str = "") -> str:
    for sentence in _clauses(script):
        if sentence_has_banned_place(sentence, prompt):
            return "unsourced place (Harbor Grill)"
    return ""


def detect_invented_human_dj_facts(script: str, prompt: str = "") -> str:
    return detect_banned_place(script, prompt) or detect_fake_visit(script, prompt)


def strip_ai_filler(script: str) -> str:
    kept = [sentence for sentence in _clauses(script) if not sentence_is_ai_filler(sentence)]
    if not kept:
        return ""
    return _join_clauses(kept)


def strip_fake_visits_and_banned_places(script: str, prompt: str = "") -> str:
    kept = [
        sentence
        for sentence in _clauses(script)
        if not sentence_is_fake_visit(sentence, prompt) and not sentence_has_banned_place(sentence, prompt)
    ]
    if not kept:
        return ""
    return _join_clauses(kept)


def rewrite_moes_place(script: str) -> str:
    """Station name is Mo's Place, never Moe's Place."""
    return _MOES_PLACE_RE.sub("Mo's Place", str(script or ""))


def _normalize_request_sentence(sentence: str) -> str:
    if not _REQUEST_INVITE_RE.search(sentence):
        return sentence
    sentence = re.sub(r"(?i)click Community", "click Request a Song", sentence)
    sentence = _LOOSE_REQUEST_CLICK_RE.sub("click Request a Song", sentence)
    sentence = _REQUEST_DEST_RE.sub(
        "click Request a Song at the top of mosplaceradio.com",
        sentence,
    )
    sentence = re.sub(
        r"(?i)\bclick Request a Song\b(?!\s+at\s+the\s+top\s+of\s+mosplaceradio\.com)",
        "click Request a Song at the top of mosplaceradio.com",
        sentence,
    )
    return sentence


def rewrite_request_cta(script: str) -> str:
    """Song-request and song-share invites go to Request a Song, not Community."""
    clauses = []
    changed = False
    for sentence in _clauses(script):
        updated = _normalize_request_sentence(sentence)
        if updated != sentence:
            changed = True
        clauses.append(updated)
    if not changed:
        return str(script or "")
    return _join_clauses(clauses)


def _community_lead(sentence: str, start: int) -> str:
    lead = sentence[:start].rstrip(" ,;:")
    return _COMMUNITY_LEAD_RE.sub("", lead).rstrip(" ,;:")


def rewrite_community_cta(script: str) -> str:
    """One Community invite per break, in the station's select-Community wording."""
    original = _clauses(script)
    clauses = []
    invited = False
    for sentence in original:
        if _COMMUNITY_THANKS_RE.match(sentence.strip()):
            continue
        if invited and _COMMUNITY_INTRO_RE.match(sentence.strip()):
            continue
        match = None if _REQUEST_INVITE_RE.search(sentence) else _COMMUNITY_PRESENT_RE.search(sentence)
        if not match:
            clauses.append(sentence)
            continue
        if invited:
            while clauses and _COMMUNITY_INTRO_RE.match(clauses[-1].strip()):
                clauses.pop()
            continue
        invited = True
        if _COMMUNITY_CANONICAL_RE.match(sentence.strip()):
            clauses.extend([sentence, _COMMUNITY_THANKS_LINE])
            continue
        lead = _community_lead(sentence, match.start())
        if len(lead.split()) >= 3:
            clauses.append(lead)
        clauses.extend([_COMMUNITY_CTA_LINE, _COMMUNITY_THANKS_LINE])
    if not invited or clauses == original:
        return str(script or "")
    return _join_clauses(clauses)


def rewrite_bakehouse_cta(script: str) -> str:
    """Bakehouse asides name the homepage link, not a vague check-out."""
    text = str(script or "")
    text = _CHECK_OUT_BAKEHOUSE_RE.sub(_BAKEHOUSE_CTA, text)
    text = _BAKEHOUSE_LINK_RE.sub(_BAKEHOUSE_CTA, text)
    text = _BAKEHOUSE_FOR_LINK_RE.sub(_BAKEHOUSE_CTA, text)
    return text


def _append_invite(script: str, sentence: str) -> str:
    text = str(script or "").rstrip()
    if not text:
        return text
    match = re.search(r"(?is)^(.*)(\bback to the music\.?)\s*$", text)
    if match and match.group(1).strip():
        head = match.group(1).rstrip()
        if not head.endswith((".", "!", "?")):
            head += "."
        return f"{head} {sentence} {match.group(2).strip()}"
    if not text.endswith((".", "!", "?")):
        text += "."
    return f"{text} {sentence}"


def _real_listener_question(sentence: str) -> bool:
    text = _DISCOURSE_Q_RE.sub(" ", str(sentence or ""))
    if "?" not in text:
        return False
    if _LISTENER_ADDRESS_RE.search(text):
        return True
    if re.search(r"(?i)\bhow about\b", text):
        return False
    return bool(re.search(r"(?i)\b(?:what|where|who|when|why|which)\b", text))


def _sentence_asks_audience(sentence: str) -> bool:
    if _REQUEST_INVITE_RE.search(sentence):
        return False
    if _AUDIENCE_INTERACT_RE.search(sentence):
        return True
    return _real_listener_question(sentence)


def _asks_question(sentence: str) -> bool:
    """Any question to the listener ('How's your day going?'), not a song-request ask."""
    if _REQUEST_INVITE_RE.search(sentence):
        return False
    return "?" in _DISCOURSE_Q_RE.sub(" ", str(sentence or ""))


def ensure_request_invite(script: str) -> str:
    """A song-request invite names Request a Song when that click is missing."""
    text = str(script or "")
    if not text.strip() or _REQUEST_PRESENT_RE.search(text):
        return text
    if not any(_REQUEST_INVITE_RE.search(sentence) for sentence in _clauses(text)):
        return text
    return _append_invite(text, _REQUEST_INVITE_LINE)


def ensure_community_invite(script: str) -> str:
    """A question to the listener gets the Community invite when that click is missing.

    A song request or song share never gets a Community click.
    """
    text = rewrite_request_cta(str(script or ""))
    if not text.strip() or _COMMUNITY_PRESENT_RE.search(text):
        return text
    if not any(_asks_question(sentence) for sentence in _clauses(text)):
        return text
    kept = [c for c in _clauses(text) if not _COMMUNITY_THANKS_RE.match(c.strip())]
    if kept and len(kept) != len(_clauses(text)):
        text = _join_clauses(kept)
    return _append_invite(text, _COMMUNITY_INVITE)


def _sentence_list(script: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", str(script or "").strip()) if part.strip()]


def _is_bakehouse_click(sentence: str) -> bool:
    return bool(_BAKEHOUSE_CLICK_RE.search(sentence))


def _is_bakehouse_mention(sentence: str) -> bool:
    return bool(_BAKEHOUSE_MENTION_RE.search(_BAKEHOUSE_CLICK_RE.sub(" ", sentence)))


def _is_vague_bakehouse_click(sentence: str) -> bool:
    return (
        bool(_BAKEHOUSE_VAGUE_CLICK_RE.search(sentence.strip()))
        and not _OTHER_SITE_SECTION_RE.search(sentence)
        and not _BAKEHOUSE_MENTION_RE.search(sentence)
    )


def ensure_bakehouse_invite(script: str) -> str:
    """One Barndoor Bakehouse click per break, right after the Bakehouse mention."""
    text = str(script or "")
    if not text.strip() or not _BAKEHOUSE_MENTION_RE.search(text):
        return text
    sentences = _sentence_list(text)
    mentions = [i for i, sentence in enumerate(sentences) if _is_bakehouse_mention(sentence)]
    invites = [
        i
        for i, sentence in enumerate(sentences)
        if _is_bakehouse_click(sentence)
        or (any(0 < i - m <= 2 for m in mentions) and _is_vague_bakehouse_click(sentence))
    ]
    if len(invites) == 1 and _is_bakehouse_click(sentences[invites[0]]):
        return text
    if not invites:
        if not mentions:
            return _append_invite(text, _BAKEHOUSE_INVITE)
        at = mentions[-1] + 1
        return " ".join(sentences[:at] + [_BAKEHOUSE_INVITE] + sentences[at:])
    keep = invites[0]
    out: list[str] = []
    for i, sentence in enumerate(sentences):
        if i == keep:
            out.append(sentence if _is_bakehouse_click(sentence) else _BAKEHOUSE_INVITE)
        elif i in invites and not _is_bakehouse_mention(sentence):
            continue
        else:
            out.append(sentence)
    return " ".join(out)


CTA_COMMUNITY = "community"
CTA_REQUEST = "request"
CTA_BAKEHOUSE = "bakehouse"


def _sentence_cta_kinds(sentence: str) -> set[str]:
    kinds: set[str] = set()
    if _REQUEST_PRESENT_RE.search(sentence) or _REQUEST_INVITE_RE.search(sentence):
        kinds.add(CTA_REQUEST)
    elif _COMMUNITY_PRESENT_RE.search(sentence):
        kinds.add(CTA_COMMUNITY)
    if _BAKEHOUSE_CLICK_RE.search(sentence):
        kinds.add(CTA_BAKEHOUSE)
    return kinds


def limit_to_one_cta(script: str, preferred: str = "") -> str:
    """Keep at most one call to action. Do not invent a request the break did not make.

    Community is used only when the DJ asks the listener a question, and then it wins.
    A Bakehouse mention keeps its click otherwise, so a second repair pass reaches the
    same result.
    """
    text = str(script or "")
    if not text.strip():
        return text
    sentences = _clauses(text)
    asks = any(_asks_question(s) for s in sentences)
    if not asks:
        trimmed = [
            s for s in sentences
            if _sentence_cta_kinds(s) != {CTA_COMMUNITY}
            and not _COMMUNITY_THANKS_RE.match(s.strip())
        ]
        if trimmed and len(trimmed) != len(sentences):
            sentences = trimmed
            text = _join_clauses(sentences)
    present: list[str] = []
    for sentence in sentences:
        for kind in sorted(_sentence_cta_kinds(sentence)):
            if kind not in present:
                present.append(kind)
    if not present:
        return text
    if len(present) == 1:
        return text
    if CTA_COMMUNITY in present and asks:
        keep = CTA_COMMUNITY
    elif CTA_BAKEHOUSE in present:
        keep = CTA_BAKEHOUSE
    elif preferred in present:
        keep = preferred
    else:
        keep = present[0]
    out: list[str] = []
    for sentence in sentences:
        kinds = _sentence_cta_kinds(sentence)
        stripped = sentence.strip()
        if kinds and keep not in kinds:
            continue
        if keep != CTA_COMMUNITY and (
            _COMMUNITY_THANKS_RE.match(stripped) or _COMMUNITY_INTRO_RE.match(stripped)
        ):
            continue
        out.append(sentence)
    if not out:
        return text
    return _join_clauses(out)


def pick_break_cta(*, bakehouse: bool = False, listener_question: bool = False) -> str:
    """Bakehouse on a farm-stand break, Community after a listener question, otherwise none.

    An ordinary break does not get a song-request closer. Request a Song is added
    only when the script already invites a request.
    """
    if bakehouse:
        return CTA_BAKEHOUSE
    if listener_question:
        return CTA_COMMUNITY
    return ""


_COMMUNITY_QUESTION_RULE = (
    f"If you ask the listener any question, end with exactly: {_COMMUNITY_INVITE} "
    "Use that Community line only after a question."
)


def cta_prompt_line(cta: str) -> str:
    if cta == CTA_BAKEHOUSE:
        return (
            "CALL TO ACTION THIS BREAK: the Barndoor Bakehouse click only. "
            "Do not also invite listeners to Community or Request a Song."
        )
    if cta == CTA_COMMUNITY:
        return (
            "CALL TO ACTION THIS BREAK: ask the listener the question, then say exactly: "
            f"{_COMMUNITY_INVITE} Do not also invite a song request."
        )
    return (
        "CALL TO ACTION THIS BREAK: invite a song request — click Request a Song at the top of "
        f"mosplaceradio.com. {_COMMUNITY_QUESTION_RULE} Never use both in one break."
    )


def tidy_double_punctuation(script: str) -> str:
    """'good day!.' -> 'good day!' (any '!.' or '?.')."""
    return _DOUBLE_END_PUNCT_RE.sub(r"\1", str(script or ""))


_ALLOW_LIVE_CLOCK = True


def allow_live_clock_rewrite(allowed: bool) -> None:
    """Station runs leave this on. A development run turns it off before repair."""
    global _ALLOW_LIVE_CLOCK
    _ALLOW_LIVE_CLOCK = bool(allowed)


def rewrite_spoken_times(script: str) -> str:
    """Every DJ, any hour: 7:00 PM / seven o'clock / 7 Oh Clock -> 7 PM / 7, 8:30PM -> 8:30 PM."""
    if not _ALLOW_LIVE_CLOCK:
        return str(script or "")
    import sys
    from pathlib import Path

    core = Path(r"D:\MPR\Engines\Core")
    if core.is_dir() and str(core) not in sys.path:
        sys.path.insert(0, str(core))
    try:
        from mpr_pronunciations import ampm_clock_text
    except ImportError:
        return str(script or "")
    return ampm_clock_text(script)


def _is_close_event(event_type: str = "", prompt: str = "") -> bool:
    et = str(event_type or "").strip().casefold()
    if any(marker in et for marker in _CLOSE_EVENT_MARKERS):
        return True
    return bool(
        re.search(
            r"(?im)^Event type:\s*(Handoff|Show Close|Final Half Hour)\b",
            str(prompt or ""),
        )
    )


def sentence_is_midshift_handoff(sentence: str, *, event_type: str = "", prompt: str = "") -> bool:
    if _is_close_event(event_type, prompt):
        return False
    text = str(sentence or "")
    if _MIDSHIFT_HANDOFF_RE.search(text):
        return True
    lowered = text.casefold()
    if _OTHER_HOST_NAME_RE.search(text) and any(
        phrase in lowered
        for phrase in ("coming up at", "takes over", "taking over", "handing", "next host")
    ):
        return True
    return False


def detect_midshift_handoff(script: str, *, event_type: str = "", prompt: str = "") -> str:
    for sentence in _clauses(script):
        if sentence_is_midshift_handoff(sentence, event_type=event_type, prompt=prompt):
            return "mid-shift handoff / close"
    return ""


def strip_midshift_handoff(script: str, *, event_type: str = "", prompt: str = "") -> str:
    if _is_close_event(event_type, prompt):
        return str(script or "")
    kept = [
        sentence
        for sentence in _clauses(script)
        if not sentence_is_midshift_handoff(sentence, event_type=event_type, prompt=prompt)
    ]
    if not kept:
        return ""
    return _join_clauses(kept)


def rewrite_playlist_flip(script: str) -> str:
    """Replace the recycled playlist-flip opener with a simple coming up."""
    text = str(script or "")
    if not text or not _PLAYLIST_FLIP_RE.search(text):
        return text
    text = _PLAYLIST_FLIP_RE.sub("Coming up", text)
    text = re.sub(r"(?i)\bcoming up\s+and\b", "Coming up,", text)
    text = re.sub(r"\s{2,}", " ", text)
    text = re.sub(r"\s+,", ",", text)
    text = re.sub(r",\s*,+", ",", text)
    return text.strip()


_HISTORY_OPEN_RE = re.compile(r"(?i)^hey friends,?\s+taking a look back\b")
_YEAR_LEAD_RE = re.compile(
    r"(?i)^(?:(?:and|then|back)\s+)?in\s+(?:(?:19|20)\d{2}|['\u2019]\d{2})\b"
)


def collapse_repeated_history(script: str) -> str:
    """Drop the stock history opener and a third or fourth 'In [year]' fact."""
    sentences = [
        part.strip()
        for part in re.split(r"(?<=[.!?…])\s+", str(script or "").strip())
        if part.strip()
    ]
    if len(sentences) < 2:
        return str(script or "")
    if _HISTORY_OPEN_RE.search(sentences[0]):
        sentences = sentences[1:]
    kept: list[str] = []
    year_lines = 0
    for sentence in sentences:
        if _YEAR_LEAD_RE.search(sentence):
            year_lines += 1
            if year_lines > 2:
                continue
        kept.append(sentence)
    if not kept:
        return str(script or "")
    return _join_clauses(kept)


_LIBRARY_TITLE_TAG = re.compile(r"\s*\(\s*TR\s*\)", re.IGNORECASE)


def strip_library_title_tag(script: str) -> str:
    """(TR) is library metadata on every song. Say the artist and title only."""
    text = _LIBRARY_TITLE_TAG.sub("", str(script or ""))
    text = re.sub(r"\s{2,}", " ", text)
    text = re.sub(r"\s+([,.!?;:])", r"\1", text)
    return text.strip()


def repair_human_dj_script(
    script: str,
    prompt: str = "",
    *,
    event_type: str = "",
    preferred_cta: str = "",
) -> str:
    """Strip banned AI filler, fake visits, unsourced places, and mid-shift handoffs."""
    text = str(script or "").strip().translate(_STRAIGHT_QUOTES)
    if not text:
        return text
    text = strip_library_title_tag(text)
    text = collapse_repeated_history(text)
    text = rewrite_moes_place(text)
    text = rewrite_playlist_flip(text)
    text = rewrite_request_cta(text)
    text = rewrite_community_cta(text)
    text = rewrite_bakehouse_cta(text)
    text = rewrite_spoken_times(text)
    text = strip_ai_filler(text)
    text = strip_fake_visits_and_banned_places(text, prompt)
    text = strip_midshift_handoff(text, event_type=event_type, prompt=prompt)
    text = ensure_request_invite(text)
    text = ensure_community_invite(text)
    text = ensure_bakehouse_invite(text)
    text = limit_to_one_cta(text, preferred_cta)
    return tidy_double_punctuation(text)

"""Verify awareness mentions stay one respectful sentence (Kathy's Daily Mix cart)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import livedj_events as events

# Kathy's aired Daily Mix cart: the cause three times, a dismissive aside, and Moe's Place.
KATHY_AWARENESS_BREAK = (
    "Hey friends, the playlist just got a little louder. October's Breast Cancer Awareness Month "
    "means we should all keep an eye on screenings—early detection saves lives. Let's support those "
    "fighting it, honor survivors, and remember those we've lost. From my kitchen to your speakers, "
    "let's make it a good day. Coming up, Survivor's High On You—smooth, soulful, and straight from "
    "the heart. It's Breast Cancer Awarness Month. I do not know what it means, but I like it. "
    "October is Breast Cancer Awareness Month, a time to support those fighting breast cancer, honor "
    "survivors, and remember those we've lost. Early detection can save lives, so encourage the people "
    "you love to stay up to date with their screenings. Let's spread awareness, offer support, and "
    "remind everyone facing this battle that they are not alone. Let's keep it easy. glad you're "
    "riding along on Moe's Place Radio while we keep the Daily Mix rolling. If you have got a request, "
    "click Request a Song at the top of Moe's Place Radio dot com."
)

RESPECTFUL_ONCE = (
    "Hey friends, the playlist just got a little louder. October is Breast Cancer Awareness Month, "
    "so remind the people you love to stay on top of screenings. Coming up, Survivor with High On You. "
    "Glad you're riding along on Mo's Place Radio."
)

PLAIN_CHECKIN = (
    "Good afternoon. The Daily Mix is rolling, and I like this song coming up. "
    "Glad you're here on Mo's Place Radio."
)


def _check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)


def main() -> None:
    coaching = events.event_coaching("Check-In")
    lower = coaching.lower()
    _check("Check-In says the cause once", "mention it once" in lower)
    _check("Check-In forbids not knowing", "do not know what it means" in lower)
    _check("Check-In forbids liking it", "never say you like it" in lower)
    _check("Check-In names Mo's Place", "moe's place" in lower)

    show_open = events.event_coaching("Show Open")
    _check("Show Open carries the awareness rule", "mention it once" in show_open.lower())
    music_story = events.event_coaching("Music Story")
    _check("Music Story coaching is unchanged", "mention it once" not in music_story.lower())

    kathy_row = {
        "Host": "kathy",
        "EventType": "Check-In",
        "Mission": "current_item",
        "Format": "Daily Mix",
        "Time": "14:30",
    }
    mission = events.mission_text_for_row(kathy_row)
    _check("Check-In mission carries the one-mention rule", "mention it once" in mission.lower())
    _check("Check-In mission keeps the original beat", "current song or daypart" in mission.lower())
    again = events.apply_awareness_rules_to_mission(kathy_row, mission)
    _check("awareness hint is not stacked", again.lower().count("mention it once") == 1)

    close_row = {
        "Host": "kathy",
        "EventType": "Show Close",
        "Mission": "Show Close",
        "Format": "Daily Mix",
        "NextHost": "johnny",
        "Time": "18:00",
    }
    close_mission = events.mission_text_for_row(close_row)
    _check("Show Close does not force the awareness hint", "mention it once" not in close_mission.lower())

    problems = events.awareness_break_problems(KATHY_AWARENESS_BREAK)
    _check("Kathy cart is rejected", events.script_mishandles_awareness(KATHY_AWARENESS_BREAK))
    for symptom in (
        "repeated_awareness",
        "misspelled_awareness",
        "confused_aside",
        "dismissive_aside",
        "wrong_station_name",
    ):
        _check(f"Kathy cart flags {symptom}", symptom in problems)

    _check("One respectful mention is allowed", events.awareness_break_problems(RESPECTFUL_ONCE) == [])
    _check("Plain check-in is allowed", events.awareness_break_problems(PLAIN_CHECKIN) == [])
    _check("Empty script is allowed", events.awareness_break_problems("") == [])

    print("verify_awareness_breaks: OK")


if __name__ == "__main__":
    main()

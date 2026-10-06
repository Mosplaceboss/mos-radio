"""Verify Check-In coaching keeps one focused beat (no laundry-list carts)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import livedj_events as events

# Kathy's last Check-In from generate_kathy.log (2026-10-06T04:38) — stacked beats.
KATHY_LAST_BREAK = (
    "Hey everybody, let's get this jukebox moving! The Kinks are still ahead with "
    "Sunny Afternoon. a classic that's been playing in my heart since I was a kid. "
    "Tommy Hawkins, happy birthday. wish you a day full of laughs and good music. "
    "Click Community to share your story. We've got a new Alanis Morissette track "
    "in the library. Ironic. just one more thing to love. And if you get a chance "
    "today, life is too short not to have a little fun!."
)

FOCUSED_SAMPLE = (
    "Good afternoon — The Kinks with Sunny Afternoon is coming up, "
    "an easy Tuesday groove to keep the Daily Mix rolling."
)


def _check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)


def main() -> None:
    coaching = events.event_coaching("Check-In")
    _check("Check-In coaching requires one clear thought", "one clear thought only" in coaching.lower())
    _check("Check-In coaching forbids laundry list", "laundry list" in coaching.lower())
    _check("Check-In coaching forbids stacked slogan closers", "stacked catchphrase closers" in coaching.lower())
    _check("Check-In coaching forbids invented rankings", "still ahead" in coaching.lower())

    weekend = events.event_coaching("Weekend Check-In")
    _check("Weekend Check-In keeps focused-break rules", "one clear thought only" in weekend.lower())

    kathy_row = {
        "Host": "kathy",
        "EventType": "Check-In",
        "Mission": "current_item",
        "Format": "Daily Mix",
        "Time": "14:30",
    }
    mission = events.mission_text_for_row(kathy_row)
    _check("Check-In mission forbids laundry list", "laundry list" in mission.lower())

    finalized = events.finalize_schedule_row(dict(kathy_row))
    _check("finalize keeps focused-break mission hint", "one clear thought only" in finalized["Mission"].lower())

    again = events.apply_focused_break_rules_to_mission(kathy_row, finalized["Mission"])
    _check("focused-break hint is not stacked", again.lower().count("one clear thought only") == 1)

    close_row = {
        "Host": "kathy",
        "EventType": "Show Close",
        "Mission": "Show Close",
        "Format": "Daily Mix",
        "NextHost": "johnny",
        "Time": "18:00",
    }
    close_mission = events.mission_text_for_row(close_row)
    _check("Show Close does not force focused-break hint", "laundry list" not in close_mission.lower())

    symptoms = events.laundry_list_symptoms(KATHY_LAST_BREAK)
    _check("Kathy last break is flagged as laundry list", events.script_sounds_like_laundry_list(KATHY_LAST_BREAK))
    _check("Kathy last break shows stacked unrelated beats", any(s.startswith("stacked_unrelated_beats") for s in symptoms))
    _check("Kathy last break shows stacked warm filler", any(s.startswith("stacked_warm_filler") for s in symptoms))
    _check("Kathy last break shows invented ranking language", "invented_ranking_language" in symptoms)

    _check("Focused sample is not a laundry list", not events.script_sounds_like_laundry_list(FOCUSED_SAMPLE))
    _check("Focused sample has no symptoms", events.laundry_list_symptoms(FOCUSED_SAMPLE) == [])

    print("verify_focused_breaks: OK")


if __name__ == "__main__":
    main()

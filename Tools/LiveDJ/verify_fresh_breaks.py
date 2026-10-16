"""Verify LiveDJ coaching blocks near-repeat carts / previous-break wording."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import livedj_events as events


def _check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)


def main() -> None:
    kathy_check = {
        "Host": "kathy",
        "EventType": "Check-In",
        "Mission": "current_item",
        "Format": "Daily Mix",
        "Time": "14:30",
    }
    kathy_open = {
        "Host": "kathy",
        "EventType": "Show Open",
        "Mission": "daily_mix_welcome",
        "Format": "Daily Mix",
        "Time": "13:00",
    }
    kathy_close = {
        "Host": "kathy",
        "EventType": "Show Close",
        "Mission": "Show Close",
        "Format": "Daily Mix",
        "NextHost": "johnny",
        "Time": "18:00",
    }

    coaching = events.event_coaching("Check-In")
    _check("Check-In coaching requires fresh break", "sound fresh" in coaching.lower())
    _check("Check-In coaching forbids near-repeat cart", "near-repeat" in coaching.lower())

    row_coaching = events.event_coaching_for_row(kathy_check)
    _check("Row coaching keeps fresh-break rule", "previous break" in row_coaching.lower())

    finalized = events.finalize_schedule_row(dict(kathy_check))
    _check("finalize appends fresh-break mission hint", "previous break" in finalized["Mission"].lower())

    open_mission = events.mission_text_for_row(kathy_open)
    _check("Show Open mission asks for fresh wording", "previous break" in open_mission.lower())

    close_mission = events.mission_text_for_row(kathy_close)
    _check("Show Close does not force fresh-break hint", "previous break" not in close_mission.lower())

    # Idempotent — applying twice must not stack duplicate hints.
    again = events.apply_fresh_break_rules_to_mission(kathy_check, finalized["Mission"])
    _check("fresh-break hint is not stacked", again.count("previous break") == 1)

    print("verify_fresh_breaks: OK")


if __name__ == "__main__":
    main()

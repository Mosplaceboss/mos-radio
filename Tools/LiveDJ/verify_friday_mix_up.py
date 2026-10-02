"""Verify Friday night Daily Mix is spoken as The Friday Mix Up for Kathy / Johnny."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import livedj_events as events


def _check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)


def main() -> None:
    kathy_night_open = {
        "day_of_week": "Friday",
        "Time": "20:00",
        "Host": "kathy",
        "EventType": "Show Open",
        "Mission": "daily_mix_welcome",
        "Format": "Daily Mix",
        "NextHost": "",
    }
    johnny_handoff = {
        "day_of_week": "Friday",
        "Time": "19:30",
        "Host": "johnny",
        "EventType": "Handoff",
        "Mission": "handoff",
        "Format": "Daily Mix",
        "NextHost": "kathy",
    }
    kathy_daytime = {
        "day_of_week": "Friday",
        "Time": "14:00",
        "Host": "kathy",
        "EventType": "Show Open",
        "Mission": "daily_mix_welcome",
        "Format": "Daily Mix",
        "NextHost": "",
    }
    thursday_night = {
        "day_of_week": "Thursday",
        "Time": "20:00",
        "Host": "kathy",
        "EventType": "Show Open",
        "Mission": "daily_mix_welcome",
        "Format": "Daily Mix",
        "NextHost": "",
    }

    night = events.finalize_schedule_row(kathy_night_open)
    _check("Kathy Friday night opens as Friday Mix Up", events.FRIDAY_MIX_UP_NAME in night["Mission"])
    _check("Kathy Friday night never says Daily Mix", "Daily Mix" not in night["Mission"])
    _check(
        "spoken format is Friday Mix Up at night",
        events.spoken_format_for_row(kathy_night_open) == events.FRIDAY_MIX_UP_NAME,
    )
    _check(
        "night coaching names Friday Mix Up",
        events.FRIDAY_MIX_UP_NAME in events.event_coaching_for_row(kathy_night_open),
    )

    handoff = events.finalize_schedule_row(johnny_handoff)
    _check("Johnny handoff names Kathy", "Kathy" in handoff["Mission"])
    _check("Johnny handoff names Friday Mix Up", events.FRIDAY_MIX_UP_NAME in handoff["Mission"])
    _check("Johnny handoff never says Daily Mix", "Daily Mix" not in handoff["Mission"])

    day = events.finalize_schedule_row(kathy_daytime)
    _check("daytime still says Daily Mix", "Daily Mix" in day["Mission"])
    _check("daytime does not say Friday Mix Up", events.FRIDAY_MIX_UP_NAME not in day["Mission"])
    _check(
        "spoken format stays Daily Mix in daytime",
        events.spoken_format_for_row(kathy_daytime) == "Daily Mix",
    )

    thursday = events.finalize_schedule_row(thursday_night)
    _check("Thursday night stays Daily Mix", "Daily Mix" in thursday["Mission"])
    _check("Thursday night is not Friday Mix Up", events.FRIDAY_MIX_UP_NAME not in thursday["Mission"])

    print("verify_friday_mix_up: OK")


if __name__ == "__main__":
    main()

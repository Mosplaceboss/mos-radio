"""Verify DJs do not pitch Request Song and Community in the same break."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import livedj_events as events

DUAL_CTA_SCRIPT = (
    "Hey everybody, let's get this jukebox moving! Click Request Song at "
    "mosplaceradio.com, and also click Community to share your story."
)

REQUEST_ONLY = (
    "Good afternoon — click Request Song at mosplaceradio.com if you want "
    "to hear something special later today."
)

COMMUNITY_ONLY = (
    "Good afternoon — click Community to share your story with the Mo's Place family."
)


def _check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)


def main() -> None:
    for event_type in (
        "Show Open",
        "Check-In",
        "Weekend Check-In",
        "Coming Up",
        "Listener Memory",
    ):
        coaching = events.event_coaching(event_type)
        _check(f"{event_type} forbids dual CTAs", "never mention both song requests and community" in coaching.lower())
        _check(f"{event_type} allows alternating", "alternating across breaks is fine" in coaching.lower())
        _check(f"{event_type} applies to every DJ", "every host/dj" in coaching.lower())

    kathy_row = {
        "Host": "kathy",
        "EventType": "Check-In",
        "Mission": "current_item",
        "Format": "Daily Mix",
        "Time": "14:30",
    }
    mo_row = {
        "Host": "mo",
        "EventType": "Check-In",
        "Mission": "personality",
        "Format": "Classic Rock",
        "Time": "10:00",
    }

    for row, label in ((kathy_row, "Kathy"), (mo_row, "Mo")):
        mission = events.mission_text_for_row(row)
        _check(f"{label} mission has Request Song or Community rule", "request song or community" in mission.lower())
        _check(f"{label} mission says not both", "not both" in mission.lower())
        finalized = events.finalize_schedule_row(dict(row))
        _check(f"{label} finalize keeps CTA alternate rule", "not both" in finalized["Mission"].lower())
        again = events.apply_listener_cta_rules_to_mission(row, finalized["Mission"])
        _check(
            f"{label} CTA hint is not stacked",
            again.lower().count("request song or community") == finalized["Mission"].lower().count("request song or community"),
        )

    close_row = {
        "Host": "kathy",
        "EventType": "Show Close",
        "Mission": "Show Close",
        "Format": "Daily Mix",
        "NextHost": "johnny",
        "Time": "18:00",
    }
    close_mission = events.mission_text_for_row(close_row)
    _check("Show Close does not force CTA alternate hint", "request song or community" not in close_mission.lower())

    _check("Dual CTA script is flagged", events.script_mentions_request_and_community(DUAL_CTA_SCRIPT))
    _check(
        "Dual CTA symptom present",
        "request_and_community_same_break" in events.dual_listener_cta_symptoms(DUAL_CTA_SCRIPT),
    )
    _check("Request-only script is allowed", not events.script_mentions_request_and_community(REQUEST_ONLY))
    _check("Community-only script is allowed", not events.script_mentions_request_and_community(COMMUNITY_ONLY))

    print("verify_listener_cta_alternate: OK")


if __name__ == "__main__":
    main()

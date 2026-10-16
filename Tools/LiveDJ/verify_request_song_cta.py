"""Verify song-request missions point to Request Song, not Community."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import livedj_events as events


def _check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)


def main() -> None:
    reminder = events.finalize_schedule_row(
        {
            "day_of_week": "Friday",
            "Time": "20:00",
            "Host": "kathy",
            "EventType": "Request Reminder",
            "Mission": "Remind listeners that requests are open.",
            "Format": "Daily Mix",
        }
    )
    _check("Request Reminder keeps event type", reminder["EventType"] == "Request Reminder")
    _check('Mission names Request Song', 'Request Song' in reminder["Mission"])
    _check("Mission names mosplaceradio.com", "mosplaceradio.com" in reminder["Mission"])
    _check(
        "Mission does not send requests to Community",
        "through Community" not in reminder["Mission"] and 'click "Community"' not in reminder["Mission"],
    )

    bad = events.apply_request_song_cta(
        "Remind listeners to request songs through Community at mosplaceradio.com.",
        "Check-In",
    )
    _check("Community request mission is rewritten", 'Request Song' in bad)
    _check(
        "Rewritten mission does not send requests to Community",
        "through Community" not in bad and 'click "Community"' not in bad,
    )

    coaching = events.event_coaching("Check-In")
    _check("Check-In coaching has Request Song CTA", "Request Song" in coaching)
    _check("Check-In coaching forbids Community for requests", "never send song requests to Community" in coaching)

    request_coaching = events.event_coaching("Request Reminder")
    _check("Request Reminder coaching exists", "Request Song" in request_coaching)

    plain = events.apply_request_song_cta(
        "Check in with listeners and reference the current daypart naturally.",
        "Check-In",
    )
    _check("Non-request missions stay unchanged", "Request Song" not in plain)

    print("verify_request_song_cta: OK")


if __name__ == "__main__":
    main()

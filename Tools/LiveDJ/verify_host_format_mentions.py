"""Verify Kathy/LB do not get Country / Yacht Rock mention permission off-format."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import livedj_events as events


def _check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)


def main() -> None:
    kathy_daily = {
        "Host": "kathy",
        "EventType": "Show Open",
        "Mission": "daily_mix_welcome",
        "Format": "Daily Mix",
    }
    lb_soft = {
        "Host": "lb",
        "EventType": "Check-In",
        "Mission": "personality",
        "Format": "Soft Rock",
    }
    kathy_country = {
        "Host": "kathy",
        "EventType": "Show Open",
        "Mission": "welcome",
        "Format": "Country",
    }
    lb_yacht = {
        "Host": "LB",
        "EventType": "Show Open",
        "Mission": "welcome",
        "Format": "Yacht Rock",
    }
    mo_daily = {
        "Host": "mo",
        "EventType": "Show Open",
        "Mission": "daily_mix_welcome",
        "Format": "Daily Mix",
    }

    _check("Kathy off Country is banned from Country", "Country" in events.active_format_mention_bans(kathy_daily))
    _check("LB off Yacht Rock is banned from Yacht Rock", "Yacht Rock" in events.active_format_mention_bans(lb_soft))
    _check("Kathy on Country is not banned", events.active_format_mention_bans(kathy_country) == [])
    _check("LB on Yacht Rock is not banned", events.active_format_mention_bans(lb_yacht) == [])
    _check("Mo has no host format bans", events.active_format_mention_bans(mo_daily) == [])

    kathy_mission = events.mission_text_for_row(kathy_daily)
    _check("Kathy mission bans country", "never mention Country" in kathy_mission)
    lb_mission = events.finalize_schedule_row(lb_soft)["Mission"]
    _check("LB mission bans yacht rock", "never mention Yacht Rock" in lb_mission)
    _check("Mo mission unchanged", "never mention" not in events.mission_text_for_row(mo_daily))

    coaching = events.event_coaching_for_row(kathy_daily)
    _check("Kathy coaching bans country", "never mention Country" in coaching)
    _check("Base coaching includes format discipline", "Only name the music format" in events.event_coaching("Show Open"))

    bad_kathy = "Welcome back — tonight we've got some country music for you."
    _check(
        "Kathy script with country is flagged",
        "Country" in events.banned_format_mentions_in_text(kathy_daily, bad_kathy),
    )
    bad_lb = "Kick back with some yacht rock vibes."
    _check(
        "LB script with yacht rock is flagged",
        "Yacht Rock" in events.banned_format_mentions_in_text(lb_soft, bad_lb),
    )
    _check(
        "Clean Kathy script is not flagged",
        events.banned_format_mentions_in_text(kathy_daily, "Welcome to the Daily Mix.") == [],
    )
    _check(
        "Substring host names do not trigger LB bans",
        events.active_format_mention_bans({"Host": "albert", "Format": "Daily Mix"}) == [],
    )

    print("verify_host_format_mentions: OK")


if __name__ == "__main__":
    main()

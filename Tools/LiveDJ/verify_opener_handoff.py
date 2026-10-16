"""Verify Show Open breaks never close or invent a next-host handoff."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import livedj_events as events


def _check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)


def main() -> None:
    casey_open = {
        "Host": "casey",
        "EventType": "Show Open",
        "Mission": "saturday_show_open",
        "Format": "Casey 70's",
        "NextHost": "kathy",
    }
    casey_close = {
        "Host": "casey",
        "EventType": "Show Close",
        "Mission": "Show Close",
        "Format": "Casey 70's",
        "NextHost": "kathy",
    }
    casey_close_blank = {
        "Host": "casey",
        "EventType": "Show Close",
        "Mission": "Show Close",
        "Format": "Casey 70's",
        "NextHost": "",
    }

    _check("Show Open does not allow host handoff", not events.allows_host_handoff(casey_open))
    _check("Show Close allows host handoff", events.allows_host_handoff(casey_close))
    _check("Show Open prompt next host is blank even if NextHost set", events.prompt_next_host(casey_open) == "")
    _check("Show Close prompt next host keeps Kathy", events.prompt_next_host(casey_close).lower() == "kathy")
    _check("Blank NextHost stays blank on close", events.prompt_next_host(casey_close_blank) == "")

    open_mission = events.mission_text_for_row(casey_open)
    _check("Show Open mission forbids closing/handoff", "do not close" in open_mission.lower())
    _check("Show Open mission says ignore Next host", "ignore any next host" in open_mission.lower())

    coaching = events.event_coaching_for_row(casey_open)
    _check("Show Open coaching forbids closer language", "never use closer or handoff language" in coaching.lower())
    _check("Show Open coaching ignores Next host", "ignore any next host field" in coaching.lower())

    close_hint = events.handoff_mission_hint(casey_close)
    _check("Show Close with Kathy names only Kathy", "kathy" in close_hint.lower())
    blank_hint = events.handoff_mission_hint(casey_close_blank)
    _check("Show Close without Next host forbids inventing", "without naming a replacement" in blank_hint.lower())

    bad_open = (
        "Hey everybody, Casey here wrapping up the show — handing it over to Kathy at 1."
    )
    findings = events.banned_closer_or_handoff_in_text(casey_open, bad_open)
    _check("Casey open closer+Kathy is flagged", "handoff_language" in findings)
    _check("Casey open invented Kathy is flagged", "invented_next_host:Kathy" in findings)

    clean_open = "Good morning — Casey here with Casey 70's. Stick around for some great tunes."
    _check(
        "Clean Casey open is not flagged",
        events.banned_closer_or_handoff_in_text(casey_open, clean_open) == [],
    )

    good_close = "Thanks for hanging with me — here's Kathy to take you through the next stretch."
    _check(
        "Valid Kathy handoff on close is allowed",
        events.banned_closer_or_handoff_in_text(casey_close, good_close) == [],
    )

    wrong_close = "Signing off — turn it over to Mo."
    wrong_findings = events.banned_closer_or_handoff_in_text(casey_close, wrong_close)
    _check("Wrong next host on close is flagged", "wrong_next_host:Mo" in wrong_findings)

    invented_close = "That's it for me — over to Kathy."
    invented = events.banned_closer_or_handoff_in_text(casey_close_blank, invented_close)
    _check("Invented Kathy on blank close is flagged", "invented_next_host:Kathy" in invented)

    finalized = events.finalize_schedule_row(dict(casey_open))
    _check("finalize_schedule_row keeps Show Open", finalized["EventType"] == "Show Open")
    _check("finalize_schedule_row mission includes open guard", "do not close" in finalized["Mission"].lower())

    print("verify_opener_handoff: OK")


if __name__ == "__main__":
    main()

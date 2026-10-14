"""Prove band announcements are gated to Reverend JJ — never Mo.

Usage:
    python Tools/LiveDJ/verify_bands_voice.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import Bands  # noqa: E402
import livedj_events  # noqa: E402


def _check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)


def main() -> None:
    _check("Band Announcements is a LiveDJ event type", "Band Announcements" in livedj_events.EVENT_TYPES)
    coaching = livedj_events.event_coaching("Band Announcements")
    _check("coaching names Reverend JJ", "Reverend JJ" in coaching)
    _check("coaching forbids Mo", "never mo" in coaching.lower())
    mission = livedj_events.default_mission_for_event_type("Band Announcements")
    _check("default mission names Reverend JJ", "Reverend JJ" in mission)
    _check(
        "mission text infers Band Announcements",
        livedj_events._infer_event_type_from_mission_text("share tonight's band announcements")
        == "Band Announcements",
    )

    sample = "[Reverend JJ]\nWednesday, October 14, 2026\n7:00 PM: Music Bingo with George at Casa Blanca.\n"
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "BandsTonight.txt"
        path.write_text(sample, encoding="utf-8")
        for host in ("Reverend JJ", "Rev JJ", "rev. jj", "JJ"):
            block = Bands.prompt_block_for_break(
                host=host,
                event_type="Band Announcements",
                bands_path=path,
            )
            _check(f"{host} gets bands source", "Music Bingo with George" in block)
        for host in ("Mo", "DJ Mo", "mo-main", "Kathy", "Casey"):
            block = Bands.prompt_block_for_break(
                host=host,
                event_type="Band Announcements",
                bands_path=path,
            )
            _check(f"{host} does not get bands source", block == "")

    print("verify_bands_voice: OK")


if __name__ == "__main__":
    main()

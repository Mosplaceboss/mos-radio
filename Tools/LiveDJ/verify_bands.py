"""Prove Weekly Events rows become tonight's bands file.

Wednesday, October 14, 2026 has a weekly Music Bingo row and a blank Date.
That night must write BandsTonight.txt. A night with no Yes row must not
leave a bands file behind, and a wav rundown must not be created.

Usage:
    python Tools/LiveDJ/verify_bands.py
"""

from __future__ import annotations

import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import Bands  # noqa: E402

FIXTURE = ROOT / "fixtures" / "Weekly_Events.csv"
WEDNESDAY = date(2026, 10, 14)
TUESDAY = date(2026, 10, 13)
THURSDAY = date(2026, 10, 15)
SATURDAY = date(2026, 10, 17)


def _check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)


def _write_csv(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8", newline="\n")


def main() -> None:
    _check("fixture calendar is present", FIXTURE.is_file())
    rows = Bands.load_calendar(FIXTURE)
    wednesday = Bands.events_for_night(rows, WEDNESDAY)
    _check("Wednesday keeps the weekly row with a blank Date", len(wednesday) == 1)
    _check("Wednesday event is Music Bingo with George", wednesday[0].event == "Music Bingo with George")
    _check("Wednesday date cell stayed blank", wednesday[0].event_date == "")

    tuesday = Bands.events_for_night(rows, TUESDAY)
    _check("Tuesday has no events", tuesday == [])

    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        output = folder / Bands.BANDS_FILENAME
        output.write_text("STALE BAND that must not air\n", encoding="utf-8")
        written = Bands.write_bands_file(FIXTURE, output, WEDNESDAY)
        text = output.read_text(encoding="utf-8")
        _check("Wednesday writes the bands file", written == output and output.is_file())
        _check("stale bands file is replaced", "STALE BAND" not in text)
        _check("file names the night", "Wednesday, October 14, 2026" in text)
        _check("file has Music Bingo with George", "Music Bingo with George" in text)
        _check("file has Casa Blanca", "Casa Blanca Mexican Cantina" in text)
        _check("file has Andover", "Andover, Massachusetts" in text)
        _check("file has 7:00 PM", "7:00 PM:" in text)
        _check("Monday Nest show is not in Wednesday", "The Nest" not in text)
        _check("Thursday karaoke is not in Wednesday", "Karaoke" not in text)
        _check("Thursday Mike Gacek is not in Wednesday", "Mike Gacek" not in text)
        _check("note rows are not aired", "Bea band" not in text and "Massachusettstching" not in text)
        wavs = list(folder.glob("*.wav"))
        _check("Wednesday does not invent a wav", wavs == [])

        output.write_text("Invented Band at Nowhere\n", encoding="utf-8")
        removed = Bands.write_bands_file(FIXTURE, output, TUESDAY)
        _check("Tuesday writes no bands file", removed is None)
        _check("Tuesday does not leave an invented bands file", not output.exists())
        leftovers = list(folder.glob("*.txt")) + list(folder.glob("*.wav"))
        _check("Tuesday leaves no bands or wav", leftovers == [])

        thursday_path = folder / Bands.BANDS_FILENAME
        Bands.write_bands_file(FIXTURE, thursday_path, THURSDAY)
        thursday = thursday_path.read_text(encoding="utf-8")
        _check("Thursday weekly karaoke is included", "Karaoke with GForce Karaoke" in thursday)
        _check("Thursday dated Mike Gacek is included", "Mike Gacek" in thursday)
        _check("Thursday keeps Garrisons", "Garrisons" in thursday)

        saturday_path = folder / Bands.BANDS_FILENAME
        Bands.write_bands_file(FIXTURE, saturday_path, SATURDAY)
        saturday = saturday_path.read_text(encoding="utf-8")
        _check("Saturday Todd Trusty is included", "Todd Trusty" in saturday)
        _check("Saturday Reverend JJ is included", "Reverend JJ & the Casual Sinners" in saturday)
        _check("Saturday does not invent a weekday weekly show", "Music Bingo" not in saturday)
        weekend_wav = folder / "FridayBands.wav"
        try:
            Bands.write_bands_file(FIXTURE, weekend_wav, SATURDAY)
        except ValueError:
            pass
        else:
            raise AssertionError("wav rundown path must be refused")
        _check("weekend wav rundown is not replaced", not weekend_wav.exists())

        filtered = folder / "filtered.csv"
        _write_csv(
            filtered,
            "Repeat,Day,Date,Event,Place,Town,Time,On\n"
            "Weekly,Wednesday,,Music Bingo with George,Casa Blanca,Andover,7:00 PM,No\n"
            "Weekly,Wednesday,,,Casa Blanca,Andover,8:00 PM,Yes\n"
            "Date,Monday,2026-10-14,Mike Gacek,Garrisons,Billerica,7:00 PM,Yes\n"
            "Date,,10/20/2026,G&G Music Bingo,Kelari,Pelham,7:00 PM,Yes\n",
        )
        off = Bands.write_bands_file(filtered, output, WEDNESDAY)
        off_text = output.read_text(encoding="utf-8")
        _check("On=No and a blank Event do not air", "Music Bingo with George" not in off_text)
        _check("blank Event does not invent a place line", "8:00 PM" not in off_text)
        _check("dated show still airs when Day names another weekday", "Mike Gacek" in off_text)
        _check("Wednesday still wrote a file for the dated show", off == output)

        october_20 = Bands.write_bands_file(filtered, output, date(2026, 10, 20))
        slash_text = output.read_text(encoding="utf-8")
        _check("slash date still selects the night", october_20 == output)
        _check("slash date event is kept", "G&G Music Bingo" in slash_text)

    print("verify_bands: OK")


if __name__ == "__main__":
    main()

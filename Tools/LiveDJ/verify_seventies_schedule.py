"""Vintage Seventies is created on Saturday and Sunday only.

Weekday refreshes must not fetch, must not read operator files, and must
not replace the cache. Saturday and Sunday still use the same output path
and the same operator-file-then-Wikimedia order.
"""

from __future__ import annotations

import sys
import tempfile
from datetime import date, datetime
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

_TMP = tempfile.TemporaryDirectory()
_platform_paths = ModuleType("platform_paths")
_platform_paths.LIVE_BASE = Path(_TMP.name)
sys.modules["platform_paths"] = _platform_paths

import SeventiesOnThisDay as seventies

# 2026-10-14 is a Wednesday, the day the dashboard showed a weekday build.
WEDNESDAY = date(2026, 10, 14)
WEEKDAYS = (
    date(2026, 10, 12),  # Monday
    date(2026, 10, 13),  # Tuesday
    date(2026, 10, 14),  # Wednesday
    date(2026, 10, 15),  # Thursday
    date(2026, 10, 16),  # Friday
)
SATURDAY = date(2026, 10, 17)
SUNDAY = date(2026, 10, 18)
OPERATOR_FACT = "1976: A Saturday Night Live episode premiered."


def _check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)


def _guard_io():
    calls = {"operator": 0, "fetch": 0, "write": 0}
    original = {
        "operator": seventies._load_facts_from_operator,
        "fetch": seventies._fetch_payload,
        "write": seventies._write_cache,
    }

    def operator(day):
        calls["operator"] += 1
        return [OPERATOR_FACT], r"D:\MPR\On this Day 1970's\October 17.txt"

    def fetch(day):
        calls["fetch"] += 1
        return {"events": [{"year": 1975, "text": "A popular song hit No. 1 on the chart."}]}

    def write(data):
        calls["write"] += 1
        original["write"](data)

    seventies._load_facts_from_operator = operator
    seventies._fetch_payload = fetch
    seventies._write_cache = write
    return calls, original


def _restore(original) -> None:
    seventies._load_facts_from_operator = original["operator"]
    seventies._fetch_payload = original["fetch"]
    seventies._write_cache = original["write"]


def main() -> None:
    _check("schedule label is Saturday and Sunday", seventies.SCHEDULE_LABEL == "Saturday and Sunday")
    _check("segment name is Vintage Seventies", seventies.SEGMENT_NAME == "Vintage Seventies")
    _check(
        "output path is still the seventies cache",
        seventies.OUTPUT_PATH.name == "SeventiesOnThisDay.json"
        and seventies.OUTPUT_PATH.parent.name == "Knowledge",
    )

    for day in WEEKDAYS:
        _check(f"{day.strftime('%A')} is not a build day", not seventies.seventies_segment_is_scheduled(day))
    _check("Saturday is a build day", seventies.seventies_segment_is_scheduled(SATURDAY))
    _check("Sunday is a build day", seventies.seventies_segment_is_scheduled(SUNDAY))
    _check(
        "Saturday 4:35 AM is a build day",
        seventies.seventies_segment_is_scheduled(datetime(2026, 10, 17, 4, 35)),
    )
    _check(
        "Wednesday 4:35 AM is not a build day",
        not seventies.seventies_segment_is_scheduled(datetime(2026, 10, 14, 4, 35)),
    )

    seventies.OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    sentinel = '{"date":"2026-10-17","facts":["1974: keep the weekend file"]}\n'
    seventies.OUTPUT_PATH.write_text(sentinel, encoding="utf-8")

    calls, original = _guard_io()
    try:
        for day in WEEKDAYS:
            result = seventies.refresh_seventies_on_this_day(when=day, force=True)
            _check(f"{day.strftime('%A')} refresh is skipped", result.get("skipped") is True)
            _check(f"{day.strftime('%A')} refresh has no facts", result.get("facts") == [])
            _check(
                f"{day.strftime('%A')} schedule text is Saturday and Sunday",
                result.get("schedule") == "Saturday and Sunday",
            )
            _check(f"{day.strftime('%A')} names Vintage Seventies", result.get("segment") == "Vintage Seventies")
            facts = seventies.load_seventies_facts(when=day)
            _check(f"{day.strftime('%A')} loader returns nothing", facts == [])

        _check("weekdays do not read operator files", calls["operator"] == 0)
        _check("weekdays do not fetch Wikimedia", calls["fetch"] == 0)
        _check("weekdays do not write the cache", calls["write"] == 0)
        _check(
            "weekday refresh leaves the weekend cache in place",
            seventies.OUTPUT_PATH.read_text(encoding="utf-8") == sentinel,
        )

        saturday = seventies.refresh_seventies_on_this_day(when=SATURDAY, force=True)
        _check("Saturday is not skipped", saturday.get("skipped") is not True)
        _check("Saturday keeps the operator fact", saturday.get("facts") == [OPERATOR_FACT])
        _check("Saturday source is still the operator file", str(saturday.get("source", "")).startswith("text_file:"))
        _check("Saturday operator file wins over Wikimedia", calls["fetch"] == 0)
        _check("Saturday still writes the cache", calls["write"] == 1)
        _check("Saturday output path is unchanged", seventies.OUTPUT_PATH.is_file())
        written = seventies.OUTPUT_PATH.read_text(encoding="utf-8")
        _check("Saturday cache contains the operator fact", OPERATOR_FACT in written)

        seventies._load_facts_from_operator = lambda day: ([], "")
        sunday = seventies.refresh_seventies_on_this_day(when=SUNDAY, force=True)
        _check("Sunday still uses the 1970-1979 feed", sunday.get("source") == "wikimedia_onthisday_1970s")
        _check("Sunday still selects a 1970s fact", sunday.get("facts") == ["1975: A popular song hit No. 1 on the chart."])
        _check("Sunday fetches once", calls["fetch"] == 1)
        _check("Sunday writes the cache", calls["write"] == 2)
        loaded = seventies.load_seventies_facts(when=SUNDAY)
        _check("Sunday loader returns the built facts", loaded == ["1975: A popular song hit No. 1 on the chart."])
    finally:
        _restore(original)

    _check(
        "Vintage Seventies is recognized by name",
        seventies.wants_seventies_on_this_day(event_type="Vintage Seventies"),
    )
    _check(
        "the Casey 70s break is still recognized",
        seventies.wants_seventies_on_this_day(event_type="On This Day in the 70s"),
    )
    _check(
        "a music-history break is not treated as Vintage Seventies",
        not seventies.wants_seventies_on_this_day(event_type="This Day in Music History"),
    )

    print("Vintage Seventies schedule checks passed.")


if __name__ == "__main__":
    main()

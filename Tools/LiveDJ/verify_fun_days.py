"""Verify same-day fun days rotate, one per LiveDJ break.

Four observances on one date must produce four different single-day prompts.
One fun day stays on every break. Disabled days are left out.
"""

from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import FunDays
import livedj_events

TODAY = date(2026, 10, 14)
NOW = datetime(2026, 10, 14, 4, 30)

BALD = "National Be Bald and Be Free Day"
DESSERT = "National Dessert Day"
NURSES = "National Emergency Nurses Day"
BULLYING = "National Stop Bullying Day"


def _check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)


def _day(title: str, **extra: object) -> dict:
    record: dict = {
        "title": title,
        "enabled": True,
        "who": "Each DJ",
        "note": extra.pop("note", ""),
        "date": "October 14",
        "when": "One-day",
    }
    record.update(extra)
    return record


def _titles(payload: str) -> list[str]:
    found: list[str] = []
    for line in payload.splitlines():
        if line.startswith("- title:"):
            found.append(line.split(":", 1)[1].strip())
    return found


def main() -> None:
    days = [
        _day(BALD, note="own the look"),
        _day(DESSERT, note="enjoy a little sweetness"),
        _day(NURSES, note="thank a nurse"),
        _day(BULLYING, note="stand up for someone"),
    ]
    breaks = [
        {"Time": "08:20", "Host": "Mo"},
        {"Time": "10:45", "Host": "Mo"},
        {"Time": "14:30", "Host": "Kathy"},
        {"Time": "18:00", "Host": "Johnny J"},
    ]

    listed = FunDays.fun_days_for_date(days, TODAY)
    _check("editor still lists all four", [day["title"] for day in listed] == [BALD, DESSERT, NURSES, BULLYING])

    payloads = [FunDays.prompt_payload_for_break(days, row, breaks, when=TODAY) for row in breaks]
    picked = [_titles(payload) for payload in payloads]
    _check("each break has one fun day", picked == [[BALD], [DESSERT], [NURSES], [BULLYING]])
    _check("four payloads differ", len(set(payloads)) == 4)
    for payload in payloads:
        _check("break prompt is not a rotation note", "Next up:" not in payload)
        _check("break prompt has a single title line", payload.count("- title:") == 1)

    rebuilt = {"Time": "14:30", "Host": "Kathy"}
    again = FunDays.prompt_payload_for_break(days, rebuilt, list(reversed(breaks)), when=TODAY)
    _check("same break keeps its fun day", again == payloads[2])
    _check("regenerating does not change the day", FunDays.prompt_payload_for_break(days, breaks[2], breaks, when=TODAY) == payloads[2])

    hooked = livedj_events.fun_day_context_for_row(breaks[0], days, breaks, when=TODAY)
    _check("LiveDJ hook matches the break payload", hooked == payloads[0])
    _check("empty fun-day list adds nothing", livedj_events.fun_day_context_for_row(breaks[0], [], breaks, when=TODAY) == "")

    preview = FunDays.preview_prompt_payload(days, breaks, when=TODAY, now=NOW)
    _check("preview names the next break", preview.startswith("This break: 8:20 AM, Mo\n"))
    _check("preview has one title", _titles(preview) == [BALD])
    _check("preview says whose turn is next", "Next up: National Dessert Day" in preview)
    _check("preview does not stack the later days", NURSES not in preview and BULLYING not in preview)

    only = [_day(DESSERT, note="enjoy a little sweetness")]
    only_payloads = [FunDays.prompt_payload_for_break(only, row, breaks, when=TODAY) for row in breaks]
    expected = (
        "Today's fun / national days:\n"
        "fun days:\n"
        "- title: National Dessert Day\n"
        "  read by: (any DJ)\n"
        "  notes: enjoy a little sweetness"
    )
    _check("one fun day is unchanged on every break", len(set(only_payloads)) == 1 and only_payloads[0] == expected)
    only_preview = FunDays.preview_prompt_payload(only, breaks, when=TODAY, now=NOW)
    _check("one fun day preview matches the break", only_preview == expected)

    disabled = [
        days[0],
        _day(DESSERT, enabled=False, note="enjoy a little sweetness"),
        days[2],
        days[3],
    ]
    disabled_payloads = [FunDays.prompt_payload_for_break(disabled, row, breaks, when=TODAY) for row in breaks]
    disabled_titles = [_titles(payload) for payload in disabled_payloads]
    _check("disabled day is skipped", disabled_titles == [[BALD], [NURSES], [BULLYING], [BALD]])
    _check("disabled title is absent", all(DESSERT not in payload for payload in disabled_payloads))
    _check("disabled day stays on the editor list", DESSERT in [day["title"] for day in FunDays.fun_days_for_date(disabled, TODAY)])

    aired = [days[0], _day(DESSERT, already_aired=True), days[2], days[3]]
    aired_blob = "\n".join(FunDays.prompt_payload_for_break(aired, row, breaks, when=TODAY) for row in breaks)
    _check("already aired day is skipped", DESSERT not in aired_blob and BALD in aired_blob)

    selected = [
        _day(BALD, who="Only selected DJs", selected_djs="Kathy"),
        _day(DESSERT),
    ]
    kathy_mo = [
        {"Time": "09:00", "Host": "Kathy"},
        {"Time": "11:00", "Host": "Mo"},
    ]
    kathy_payload = FunDays.prompt_payload_for_break(selected, kathy_mo[0], kathy_mo, when=TODAY)
    mo_payload = FunDays.prompt_payload_for_break(selected, kathy_mo[1], kathy_mo, when=TODAY)
    _check("selected DJ receives the named day", _titles(kathy_payload) == [BALD])
    _check("other DJ does not receive a selected-only day", _titles(mo_payload) == [DESSERT])

    each = [_day(BALD)]
    casey = FunDays.prompt_payload_for_break(each, {"Time": "12:00", "Host": "DJ Casey"}, breaks, when=TODAY)
    blues = FunDays.prompt_payload_for_break(each, {"Time": "12:05", "Host": "Mo Blues"}, breaks, when=TODAY)
    mo = FunDays.prompt_payload_for_break(each, {"Time": "12:10", "Host": "DJ Mo"}, breaks, when=TODAY)
    _check("Casey is left out of Each DJ", casey == "")
    _check("Mo Blues is left out of Each DJ", blues == "")
    _check("Mo still receives Each DJ", _titles(mo) == [BALD])
    named_casey = [_day(BALD, who="Only selected DJs", selected_djs="Casey")]
    casey_named = FunDays.prompt_payload_for_break(
        named_casey, {"Time": "12:00", "Host": "Casey"}, [{"Time": "12:00", "Host": "Casey"}], when=TODAY
    )
    _check("Casey can be named on purpose", _titles(casey_named) == [BALD])

    other_day = [_day(BALD), _day(DESSERT, date="October 15")]
    dated = FunDays.prompt_payload_for_break(other_day, breaks[0], breaks, when=TODAY)
    _check("a different date is not in today's prompt", _titles(dated) == [BALD])
    sunday = _day("National Sample Sunday", date="2nd Sunday of October", when="One-day", note="")
    _check("2nd Sunday of October 2026 is the 11th", FunDays.occurs_on(FunDays.normalize_day(sunday), date(2026, 10, 11)))
    _check("2nd Sunday is not October 14", not FunDays.occurs_on(FunDays.normalize_day(sunday), TODAY))

    plain = FunDays.normalize_day({"title": DESSERT, "note": "enjoy a little sweetness"})
    _check("saved day with no category stays Fun Day", plain["category"] == "Fun Day")
    awareness = {"title": "Breast Cancer Awareness Month", "enabled": True, "who": "Each DJ", "date": "October", "when": "Whole month", "note": "remind people about screenings"}
    loaded = FunDays.normalize_day(awareness)
    _check("Breast Cancer Awareness Month with no category loads as Serious Day", loaded["category"] == "Serious Day")
    overridden = FunDays.normalize_day({"title": "Breast Cancer Awareness Month", "category": "Fun Day"})
    _check("an explicit Fun Day choice is kept", overridden["category"] == "Fun Day")
    marked = FunDays.normalize_day({"title": DESSERT, "category": "Serious Day"})
    _check("an explicit Serious Day choice is kept", marked["category"] == "Serious Day")

    serious_break = [{"Time": "08:20", "Host": "Mo"}]
    serious_payload = FunDays.prompt_payload_for_break([awareness], serious_break[0], serious_break, when=TODAY)
    _check("serious prompt names the observance once", _titles(serious_payload) == ["Breast Cancer Awareness Month"])
    _check("serious prompt forbids jokes", "Do not joke." in serious_payload)
    _check("serious prompt forbids not knowing", "do not know what it means" in serious_payload.lower())
    _check("serious prompt forbids liking it", "Do not say you like it." in serious_payload)
    _check("serious prompt names the station", "Mo's Place Radio" in serious_payload)
    _check("serious line is the shared prompt line", FunDays.SERIOUS_PROMPT_LINE in serious_payload)

    fun_payload = only_payloads[0]
    _check("a fun day does not get the serious warning", "Do not joke." not in fun_payload and FunDays.SERIOUS_PROMPT_LINE not in fun_payload)

    mixed = [
        _day(BALD, note="own the look"),
        awareness,
        _day(DESSERT, note="enjoy a little sweetness"),
        _day(BULLYING, note="stand up for someone"),
    ]
    mixed_payloads = [FunDays.prompt_payload_for_break(mixed, row, breaks, when=TODAY) for row in breaks]
    mixed_titles = [_titles(payload) for payload in mixed_payloads]
    _check(
        "serious and fun days still rotate one per break",
        mixed_titles == [[BALD], ["Breast Cancer Awareness Month"], [DESSERT], [BULLYING]],
    )
    _check("only the serious break carries the warning", "Do not joke." in mixed_payloads[1])
    _check(
        "fun breaks in the same rotation stay light",
        all("Do not joke." not in payload for payload in (mixed_payloads[0], mixed_payloads[2], mixed_payloads[3])),
    )

    print("verify_fun_days: OK")


if __name__ == "__main__":
    main()

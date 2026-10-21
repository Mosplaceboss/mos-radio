"""Verify DJ breaks stay conversational and use supplied content.

Exercises the production-path helpers for a Wednesday morning DJ Mo Show Open
with a celebrity birthday note (daily.csv-style facts), plus custom/alert
preservation and rejection of verbatim fact dumps.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import break_continuity
import break_structure
import livedj_events as events


CARRIE_NOTE = (
    "Carrie Fisher was born October 21, 1956. Best known as Princess Leia in Star Wars."
)
CARRIE_LABEL = "Carrie Fisher"

GOOD_MO_OPEN = (
    "Good morning, everybody! DJ Mo here, settling in with you for a morning of Trop Rock. "
    "I was looking through today's celebrity birthdays and noticed Carrie Fisher was born "
    "on this day back in 1956. Most of us will always remember her as Princess Leia, but she "
    "had quite a career beyond Star Wars, too. Hard to believe how much time has passed! "
    "All right, let's get this morning rolling. You're hanging out with DJ Mo on Mo's Place Radio."
)

BAD_VERBATIM = (
    "Today is Carrie Fisher's birthday. Carrie Fisher was born October 21, 1956. "
    "Best known as Princess Leia in Star Wars."
)

BAD_WISH_ONLY = (
    "Happy birthday to Carrie Fisher. Carrie Fisher was born October 21, 1956. "
    "Best known as Princess Leia in Star Wars."
)

STATION_ALERT = (
    "This is a station alert. Mo's Place Radio will join a special network feed at the top of the hour."
)


def _check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)


def _codes(result: break_structure.StructureResult) -> set[str]:
    return {issue.code for issue in result.issues}


def test_subject_resolution() -> None:
    kind = break_structure.resolve_subject_kind(event_type="Show Open", birthday=True)
    _check("Show Open + birthday keeps show_open subject", kind == "show_open")

    kind = break_structure.resolve_subject_kind(event_type="Check-In", birthday=True)
    _check("Check-In + birthday uses birthday subject", kind == "birthday")

    kind = break_structure.resolve_subject_kind(
        event_type="Show Open",
        station_alert=True,
        birthday=True,
    )
    _check("Station alert wins over birthday", kind == "alert")

    kind = break_structure.resolve_subject_kind(
        event_type="Check-In",
        custom_script=True,
        birthday=True,
    )
    _check("Custom script wins over birthday", kind == "custom")


def test_coaching_allows_openings() -> None:
    shape = break_structure.break_shape_coaching(event_type="Show Open", subject="show_open")
    _check("Show Open coaching does not ban greetings", "do not open with a greeting" not in shape.lower())
    _check("Show Open coaching requires welcome", "welcome" in shape.lower())

    bday = break_structure.birthday_structure_coaching(CARRIE_LABEL, event_type="Show Open")
    _check("Birthday coaching does not ban greetings", "do not open with a greeting" not in bday.lower())
    _check("Birthday coaching says paraphrase", "paraphrase" in bday.lower())

    open_mission = events.DEFAULT_MISSIONS["Show Open"].lower()
    _check(
        "Show Open default mission covers daily content conversationally",
        "daily content" in open_mission or "conversational" in open_mission,
    )

    coaching = events.EVENT_COACHING["Show Open"].lower()
    _check("Show Open event coaching forbids verbatim notes", "verbatim" in coaching)


def test_validation_rejects_fact_dumps() -> None:
    good = break_structure.validate_break_structure(
        GOOD_MO_OPEN,
        subject="show_open",
        event_type="Show Open",
        label=CARRIE_LABEL,
        note=CARRIE_NOTE,
        host="mo",
    )
    _check(f"Good Mo open passes validation, got {_codes(good)}", good.ok)

    bad = break_structure.validate_break_structure(
        BAD_VERBATIM,
        subject="show_open",
        event_type="Show Open",
        label=CARRIE_LABEL,
        note=CARRIE_NOTE,
        host="mo",
    )
    _check("Verbatim dump is rejected", not bad.ok)
    codes = _codes(bad)
    _check(
        f"Verbatim dump flags abrupt/verbatim, got {codes}",
        bool(codes & {"abrupt_fact_start", "verbatim_note", "missing_open", "missing_exit"}),
    )

    wish = break_structure.validate_break_structure(
        BAD_WISH_ONLY,
        subject="birthday",
        event_type="Check-In",
        label=CARRIE_LABEL,
        note=CARRIE_NOTE,
        host="mo",
    )
    _check("Wish+note paste without exit is rejected", not wish.ok)

    alert = break_structure.validate_break_structure(
        STATION_ALERT,
        subject="alert",
        event_type="Check-In",
        station_alert=True,
    )
    _check("Station alert is not structure-validated", alert.ok and not alert.required)

    custom = break_structure.validate_break_structure(
        "Custom line exactly as approved in Producer.",
        subject="custom",
        event_type="Check-In",
        custom_script=True,
    )
    _check("Custom authored script is preserved", custom.ok and not custom.required)


def test_focus_preserves_conversation() -> None:
    focused = break_continuity.focus_spoken_break(
        GOOD_MO_OPEN,
        subject="show_open",
        label=CARRIE_LABEL,
        note=CARRIE_NOTE,
        event_type="Show Open",
        content_kind="birthday",
    )
    lowered = focused.casefold()
    _check("Focus keeps Good morning lead-in", "good morning" in lowered)
    _check("Focus keeps Carrie Fisher content", "carrie fisher" in lowered)
    _check(
        "Focus keeps natural exit",
        "music" in lowered or "mo's place" in lowered or "rolling" in lowered,
    )
    result = break_structure.validate_break_structure(
        focused,
        subject="show_open",
        event_type="Show Open",
        label=CARRIE_LABEL,
        note=CARRIE_NOTE,
        host="mo",
    )
    _check(f"Focused Mo open still validates, got {_codes(result)}", result.ok)

    dumped = break_continuity.focus_spoken_break(
        BAD_VERBATIM,
        subject="birthday",
        label=CARRIE_LABEL,
        note=CARRIE_NOTE,
        event_type="Show Open",
        content_kind="birthday",
    )
    dump_result = break_structure.validate_break_structure(
        dumped,
        subject="show_open",
        event_type="Show Open",
        label=CARRIE_LABEL,
        note=CARRIE_NOTE,
        host="mo",
    )
    _check(
        "Old verbatim dump path still fails structure gate after focus",
        not dump_result.ok,
    )


def test_regular_birthday_check_in() -> None:
    good_checkin = (
        "Hey — quick one before the next song. Looking at today's birthdays, "
        "Carrie Fisher was born on this day in 1956, forever Princess Leia to a lot of us. "
        "Happy birthday to Carrie Fisher. All right, back to the music."
    )
    focused = break_continuity.focus_spoken_break(
        good_checkin,
        subject="birthday",
        label=CARRIE_LABEL,
        note=CARRIE_NOTE,
        event_type="Check-In",
        content_kind="birthday",
    )
    result = break_structure.validate_break_structure(
        focused,
        subject="birthday",
        event_type="Check-In",
        label=CARRIE_LABEL,
        note=CARRIE_NOTE,
        host="mo",
    )
    _check(f"Regular birthday check-in passes, got {_codes(result)}: {focused}", result.ok)
    _check(
        "Check-in keeps lead-in",
        "quick one" in focused.casefold() or "looking" in focused.casefold() or "hey" in focused.casefold(),
    )
    _check("Check-in keeps exit", "back to the music" in focused.casefold())


def test_content_not_skipped_on_show_open() -> None:
    """Pending birthday on Show Open must remain content, not be cleared as 'music only'."""
    kind = break_structure.resolve_subject_kind(event_type="Show Open", birthday=True)
    coaching = break_structure.one_subject_coaching(
        kind,
        event_type="Show Open",
        label=CARRIE_LABEL,
        note=CARRIE_NOTE,
    )
    _check("Show Open subject stays show_open", kind == "show_open")
    _check("Show Open coaching still names the birthday", "carrie fisher" in coaching.casefold())
    _check("Show Open coaching says paraphrase", "paraphrase" in coaching.casefold())
    _check("Show Open coaching is not a skip block", "skip" not in coaching.casefold())


def main() -> None:
    test_subject_resolution()
    test_coaching_allows_openings()
    test_validation_rejects_fact_dumps()
    test_focus_preserves_conversation()
    test_regular_birthday_check_in()
    test_content_not_skipped_on_show_open()
    print("verify_break_structure: OK")
    print("  - Show Open + celebrity birthday keeps conversational open/content/exit")
    print("  - Supplied birthday content is coached into the open (not skipped)")
    print("  - Verbatim daily.csv-style dumps are rejected")
    print("  - Station alerts and custom scripts remain unaffected")
    print("  - Regular birthday check-ins stay conversational")


if __name__ == "__main__":
    main()

"""Break continuity: one focus, spaced reminders, no automatic closers.

Runs against this folder or the LiveDJ Scripts copy.
"""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import break_continuity as bc

WHEN = datetime(2026, 10, 15, 10, 0, 0)

AWARENESS = "Breast Cancer Awareness Month"
FRIENDS = "The One Where Ross Finds Out"


def _pool() -> list[dict]:
    return [
        bc.make_candidate("fun_day", AWARENESS, AWARENESS, must=True, solemn=True, shared=True),
        bc.make_candidate("friends", FRIENDS, FRIENDS, must=False, shared=False),
        bc.make_candidate("dogs", "moecarbay", "MoeCarBay", must=False),
        bc.make_candidate(
            "engagement",
            "what song cheers you up",
            "What song always cheers you up?",
            must=False,
        ),
        bc.make_candidate("rss", "saturday market lowell", "Saturday market in Lowell", must=False),
    ]


def _air(host: str, moment: datetime, plan: bc.BreakPlan, state: Path, script: str) -> None:
    bc.record_break(
        host,
        moment,
        script,
        plan.candidates,
        event_type="Check-In",
        planned_modes=plan.modes,
        state_file=state,
    )


class FocusTests(unittest.TestCase):
    def test_one_subject_when_several_are_available(self) -> None:
        plan = bc.plan_break("bailey", WHEN, "Check-In", _pool(), state_file=Path("missing-state.json"))
        heavy = plan.kept()
        self.assertEqual(len(heavy), 1)
        self.assertEqual(heavy[0]["family"], "fun_day")
        self.assertEqual(plan.mode_for("friends"), "skip")
        self.assertEqual(plan.mode_for("dogs"), "skip")
        self.assertEqual(plan.mode_for("engagement"), "skip")
        self.assertEqual(plan.mode_for("rss"), "skip")
        self.assertEqual(plan.preferred_cta, "")
        self.assertIn("Breast Cancer Awareness Month", plan.continuity_block)
        self.assertIn("this host", plan.continuity_block.lower())

    def test_music_only_break_is_allowed(self) -> None:
        plan = bc.plan_break("johnnyj", WHEN, "Check-In", [], state_file=Path("missing-state.json"))
        self.assertEqual(plan.kept(), [])
        self.assertEqual(plan.ending, "music")
        self.assertIn("Not a one-line announcement", plan.continuity_block)

    def test_specialty_break_does_not_take_the_stack(self) -> None:
        plan = bc.plan_break(
            "mo",
            WHEN,
            "Music Story",
            _pool(),
            specialty=True,
            state_file=Path("missing-state.json"),
        )
        self.assertEqual(plan.kept(), [])
        self.assertEqual(plan.preferred_cta, "")

    def test_handoff_does_not_start_a_new_story(self) -> None:
        plan = bc.plan_break("kathy", WHEN, "Handoff", _pool(), state_file=Path("missing-state.json"))
        self.assertEqual(plan.kept(), [])
        self.assertEqual(plan.ending, "signoff")

    def test_personality_feature_survives_when_it_is_the_focus(self) -> None:
        friends_only = [bc.make_candidate("friends", FRIENDS, FRIENDS)]
        bailey = bc.plan_break("bailey", WHEN, "Check-In", friends_only, state_file=Path("missing-state.json"))
        pete = bc.plan_break(
            "pete",
            WHEN,
            "Check-In",
            [bc.make_candidate("personal", "chipper the dog", "Chipper the dog")],
            state_file=Path("missing-state.json"),
        )
        self.assertEqual(bailey.kept()[0]["family"], "friends")
        self.assertEqual(bailey.ending, "community")
        self.assertEqual(pete.kept()[0]["label"], "Chipper the dog")
        self.assertNotIn("Bailey", pete.continuity_block)


class SequenceTests(unittest.TestCase):
    def test_three_bailey_breaks_do_not_repeat(self) -> None:
        """The reported Bailey stretch: same Friends episode, awareness twice, same closer."""
        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder) / "break_continuity.json"
            pool = _pool()
            first = bc.plan_break("bailey", WHEN, "Check-In", pool, state_file=state)
            self.assertEqual(first.kept()[0]["label"], AWARENESS)
            self.assertEqual(first.mode_for("fun_day"), "full")
            self.assertNotIn("friends", {item["family"] for item in first.kept()})
            _air(
                "bailey",
                WHEN,
                first,
                state,
                f"October is {AWARENESS}. It is a time to support the people we love. "
                "Coming up, Brewer and Shipley.",
            )

            second_at = WHEN + timedelta(minutes=40)
            second = bc.plan_break("bailey", second_at, "Check-In", pool, state_file=state)
            self.assertEqual(second.mode_for("fun_day"), "skip")
            self.assertEqual(second.kept()[0]["family"], "friends")
            self.assertNotEqual(second.preferred_cta, first.preferred_cta)
            _air(
                "bailey",
                second_at,
                second,
                state,
                f"Last night was {FRIENDS}. Anyone else know that one? "
                "Let us know what you think by clicking Community at mosplaceradio.com. "
                "We would love to hear from you!",
            )

            third_at = WHEN + timedelta(minutes=80)
            third = bc.plan_break("bailey", third_at, "Check-In", pool, state_file=state)
            self.assertEqual(third.mode_for("fun_day"), "skip")
            self.assertEqual(third.mode_for("friends"), "skip")
            self.assertEqual(len(third.kept()), 1)
            self.assertNotEqual(third.kept()[0]["family"], "friends")
            self.assertEqual(third.preferred_cta, "")
            closers = [first.preferred_cta, second.preferred_cta, third.preferred_cta]
            self.assertLess(closers.count("community"), 3)
            self.assertLess(closers.count("request"), 1)

    def test_other_host_does_not_reexplain_a_station_message(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder) / "break_continuity.json"
            item = bc.make_candidate("fun_day", AWARENESS, AWARENESS, must=True, solemn=True, shared=True)
            bailey = bc.plan_break("bailey", WHEN, "Check-In", [item], state_file=state)
            _air("bailey", WHEN, bailey, state, f"A warm word about {AWARENESS}, then the music.")
            mo_soon = bc.plan_break("mo", WHEN + timedelta(minutes=30), "Check-In", [item], state_file=state)
            self.assertEqual(mo_soon.mode_for("fun_day"), "skip")
            mo_later = bc.plan_break("mo", WHEN + timedelta(hours=4), "Check-In", [item], state_file=state)
            self.assertEqual(mo_later.mode_for("fun_day"), "reminder")
            self.assertIn("short reminder", mo_later.continuity_block.lower())

    def test_awareness_is_not_banned_for_the_day(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder) / "break_continuity.json"
            item = bc.make_candidate("announcement", "road closure", "Main Street closure", must=True, shared=True)
            morning = bc.plan_break("bailey", WHEN, "Check-In", [item], state_file=state)
            self.assertEqual(morning.mode_for("announcement"), "full")
            _air("bailey", WHEN, morning, state, "Heads up on the Main Street closure before you head out.")
            midday = bc.plan_break("bailey", WHEN + timedelta(hours=4), "Check-In", [item], state_file=state)
            self.assertEqual(midday.mode_for("announcement"), "reminder")


class SpokenRepairTests(unittest.TestCase):
    def test_awareness_is_not_explained_twice(self) -> None:
        script = (
            f"October is {AWARENESS}, a time to support survivors and talk about screening. "
            "Even a gray morning feels a little kinder when we remember people going through it. "
            f"{AWARENESS} matters because supporting survivors and talking about screening "
            "can make a real difference. "
            "Coming up, Brewer and Shipley."
        )
        fixed = bc.tighten_spoken_break(script, labels=[AWARENESS], allow_cta="")
        self.assertEqual(fixed.lower().count("breast cancer"), 1)
        self.assertIn("Coming up, Brewer and Shipley.", fixed)

    def test_restated_explanation_without_the_title_is_dropped(self) -> None:
        script = (
            f"It's {AWARENESS}, a time to support survivors and wear pink for the people we love. "
            "It is a time to support survivors and wear pink for the people we love."
        )
        fixed = bc.tighten_spoken_break(script, labels=[AWARENESS], allow_cta="")
        self.assertEqual(len(bc._sentences(fixed)), 1)

    def test_automatic_closers_are_removed_when_the_break_did_not_ask(self) -> None:
        script = (
            "The rain has that November feel, so the music can do the warming up. "
            "Coming up, Brewer and Shipley. "
            "If you have a request, click Request a Song at the top of mosplaceradio.com. "
            "We would love to hear from you!"
        )
        fixed = bc.tighten_spoken_break(
            script,
            labels=[],
            allow_cta="",
            recent_openers=["youre_still_here"],
        )
        self.assertNotIn("Request a Song", fixed)
        self.assertNotIn("love to hear", fixed.lower())
        self.assertIn("Brewer and Shipley", fixed)

    def test_conversational_follow_through_is_not_cut_to_a_liner(self) -> None:
        script = (
            "One of the things I love about Jimmy Buffett is how a song can change the mood of a drive. "
            "You could be sitting in traffic and the whole hour feels easier. "
            "That is the trick of a good record. "
            "Volcano is in the mix a little later."
        )
        fixed = bc.tighten_spoken_break(script, labels=[], allow_cta="")
        self.assertIn("traffic", fixed)
        self.assertIn("good record", fixed)
        self.assertIn("Volcano", fixed)
        self.assertGreaterEqual(len(fixed.split()), 35)

    def test_repeated_opener_is_not_kept(self) -> None:
        script = "You're still here. The mix is in a good mood this hour."
        fixed = bc.tighten_spoken_break(script, recent_openers=["youre_still_here"])
        self.assertNotIn("still here", fixed.lower())
        self.assertIn("good mood", fixed)

    def test_a_real_question_keeps_one_community_invite(self) -> None:
        script = (
            "What song always cheers you up? "
            "Let us know what you think by clicking Community at mosplaceradio.com. "
            "We would love to hear from you!"
        )
        fixed = bc.tighten_spoken_break(script, allow_cta="community")
        self.assertIn("clicking Community", fixed)
        self.assertIn("love to hear from you", fixed.lower())

    def test_question_break_does_not_also_ask_for_a_request(self) -> None:
        script = (
            "What song always cheers you up? "
            "Let us know what you think by clicking Community at mosplaceradio.com. "
            "We would love to hear from you! "
            "If you've got a request, click Request a Song at the top of mosplaceradio.com."
        )
        fixed = bc.tighten_spoken_break(script, allow_cta="community")
        self.assertIn("clicking Community", fixed)
        self.assertNotIn("Request a Song", fixed)

    def test_no_canned_bridge_and_no_orphaned_follow_on(self) -> None:
        script = (
            "Hey everyone, Bailey here on Mo's Place Radio. "
            "MoeCarBay's tail is still wagging, and the studio feels ready for the morning. "
            "We are rolling with a daily mix and a little real talk. "
            "If you've got a request, drop it in. "
            "We'll get to it. "
            "Life is better with the music turned up."
        )
        fixed = bc.tighten_spoken_break(script, labels=[], allow_cta="")
        self.assertNotIn("That lines up with this", fixed)
        self.assertNotIn("get to it", fixed)
        self.assertIn("MoeCarBay", fixed)
        self.assertIn("music turned up", fixed)

    def test_unrelated_sentences_are_not_dropped_or_bridged(self) -> None:
        script = (
            "The weather is turning cold this weekend with some snow up north. "
            "Bring a jacket if you are heading out. "
            "The Red Sox signed a new pitcher yesterday afternoon in Boston. "
            "Local bakeries around Lowell are selling pumpkin bread this week."
        )
        fixed = bc.tighten_spoken_break(script, labels=[], allow_cta="")
        self.assertNotIn("That lines up with this", fixed)
        self.assertIn("Red Sox", fixed)
        self.assertIn("pumpkin bread", fixed)


if __name__ == "__main__":
    unittest.main()

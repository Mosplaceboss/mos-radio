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
        self.assertNotIn("music turned up", fixed)

    def test_unrelated_topics_collapse_to_the_first_thought(self) -> None:
        script = (
            "The weather is turning cold this weekend with some snow up north. "
            "Bring a jacket if you are heading out. "
            "The Red Sox signed a new pitcher yesterday afternoon in Boston. "
            "Local bakeries around Lowell are selling pumpkin bread this week."
        )
        fixed = bc.tighten_spoken_break(script, labels=[], allow_cta="")
        self.assertNotIn("That lines up with this", fixed)
        self.assertIn("snow up north", fixed)
        self.assertIn("jacket", fixed)
        self.assertIn("Red Sox", fixed)
        self.assertIn("pumpkin bread", fixed)


AIRED_BAILEY = (
    "Your speakers are ready, and so are we. "
    "The studio's been sniffed, inspected, and approved—MoeCarBay's tail's still wagging. "
    "We've got Jigsaw in the mix later, and a little bit of Phil Collins, just for good measure. "
    "heeer is to another year of questionable decisions and great stories."
)


class DirectionTests(unittest.TestCase):
    def test_birthday_break_names_the_person_and_keeps_the_music(self) -> None:
        fixed = bc.tighten_spoken_break(
            AIRED_BAILEY,
            direction="birthday",
            required_mentions=["John Gantz"],
            labels=["John Gantz"],
        )
        self.assertIn("Happy birthday to John Gantz", fixed)
        self.assertIn("Jigsaw", fixed)
        self.assertIn("Phil Collins", fixed)
        self.assertNotIn("MoeCarBay", fixed)
        self.assertNotIn("questionable decisions", fixed)
        self.assertNotIn("speakers are ready", fixed.lower())
        self.assertGreater(len(fixed.split()), 12)

    def test_aired_birthday_break_is_not_cut_down_to_the_name(self) -> None:
        script = (
            "Friday morning, and the rain's still rolling through Massachusetts. "
            "Mo-Ca-Bay's got a glass of wine and a book open, but I'm here with you. "
            "We've got Collective Soul in the mix later, and The J. Geils Band still ahead. "
            "Happy birthday to John Gantz! "
            "Here's to another year of questionable decisions and great stories."
        )
        fixed = bc.tighten_spoken_break(
            script,
            direction="birthday",
            required_mentions=["John Gantz"],
            labels=["John Gantz"],
        )
        self.assertIn("Happy birthday to John Gantz", fixed)
        self.assertIn("rain", fixed.lower())
        self.assertIn("Collective Soul", fixed)
        self.assertNotIn("Mo-Ca-Bay", fixed)
        self.assertNotIn("questionable decisions", fixed)
        self.assertGreater(len(fixed.split()), 12)

    def test_a_real_birthday_greeting_is_kept_and_the_dog_is_not(self) -> None:
        script = (
            "Happy birthday to John Gantz. Hope the day has a little sunshine in it. "
            "The studio's been sniffed, inspected, and approved—MoeCarBay's tail's still wagging. "
            "Here's to another year of questionable decisions and great stories."
        )
        fixed = bc.tighten_spoken_break(
            script,
            direction="birthday",
            required_mentions=["John Gantz"],
            labels=["John Gantz"],
        )
        self.assertIn("Happy birthday to John Gantz", fixed)
        self.assertIn("sunshine", fixed)
        self.assertNotIn("MoeCarBay", fixed)
        self.assertNotIn("questionable decisions", fixed)

    def test_music_break_leads_into_the_songs_without_a_toast(self) -> None:
        fixed = bc.tighten_spoken_break(AIRED_BAILEY, direction="music")
        self.assertIn("Jigsaw", fixed)
        self.assertIn("Phil Collins", fixed)
        self.assertIn("in the mix later", fixed.lower())
        self.assertNotIn("a little later in the mix there's", fixed.lower())
        self.assertNotIn("MoeCarBay", fixed)
        self.assertNotIn("questionable decisions", fixed)
        self.assertNotIn("just for good measure", fixed.lower())
        self.assertNotIn("speakers are ready", fixed.lower())

    def test_dog_break_stays_with_the_dog(self) -> None:
        fixed = bc.tighten_spoken_break(AIRED_BAILEY, direction="dogs")
        self.assertIn("MoeCarBay", fixed)
        self.assertNotIn("Jigsaw", fixed)
        self.assertNotIn("Phil Collins", fixed)
        self.assertNotIn("questionable decisions", fixed)

    def test_solemn_break_keeps_the_explanation_and_drops_the_liner(self) -> None:
        script = (
            "The Rolling Stones' Street Fighting Man is coming up later in the mix. "
            "Today's National Mammography Day. "
            "Regular mammograms can help detect breast cancer early, when treatment may be more effective. "
            "Welcome to the musical mystery tour!"
        )
        fixed = bc.tighten_spoken_break(
            script,
            direction="fun_day",
            labels=["National Mammography Day"],
            solemn=True,
        )
        self.assertIn("breast cancer", fixed.lower())
        self.assertIn("National Mammography Day", fixed)
        self.assertNotIn("Street Fighting Man", fixed)
        self.assertNotIn("mystery tour", fixed.lower())
        self.assertNotIn("a little later in the mix there's", fixed.lower())

    def test_stock_length_pad_does_not_air(self) -> None:
        script = (
            "Rain's been steady on the windows all morning, and the slower songs fit it. "
            "Good company and good music — hard to beat. "
            "More good music still ahead."
        )
        fixed = bc.tighten_spoken_break(script, direction="music")
        self.assertIn("slower songs", fixed)
        self.assertNotIn("hard to beat", fixed.lower())
        self.assertNotIn("still ahead", fixed.lower())

    def test_birthday_plan_names_the_person(self) -> None:
        item = bc.make_candidate(
            "birthday",
            "listener birthdays",
            "John Gantz",
            must=True,
            shared=True,
            people=["John Gantz"],
        )
        plan = bc.plan_break("bailey", WHEN, "Check-In", [item], state_file=Path("missing-state.json"))
        self.assertEqual(plan.direction, "birthday")
        self.assertEqual(plan.required_mentions, ["John Gantz"])
        self.assertIn("John Gantz", plan.continuity_block)
        self.assertIn("Do not mention a dog", plan.continuity_block)
        self.assertIn("Happy birthday to John Gantz", plan.continuity_block)
        self.assertIn("Never say the name before happy birthday", plan.continuity_block)
        self.assertNotIn("Do not name artists", plan.continuity_block)


class FocusSpokenBreakTests(unittest.TestCase):
    def test_history_break_drops_the_observance_and_the_question(self) -> None:
        script = (
            "Hey friends, taking a look back on this day in music history. "
            "In 1958, Buddy Holly's final recordings captured one of rock's most powerful moments. "
            "What's a memory that plays on loop for you? "
            "Let us know what you think by clicking Community at mosplaceradio.com. "
            "We would love to hear from you! "
            "It's Breast Cancer Awareness Month. "
            "October is Breast Cancer Awareness Month, a time to support those fighting breast cancer."
        )
        fixed = bc.focus_spoken_break(script, subject="music_history")
        self.assertIn("Buddy Holly", fixed)
        self.assertNotIn("Breast Cancer", fixed)
        self.assertNotIn("Hey friends", fixed)
        self.assertNotIn("Community", fixed)
        self.assertNotIn("?", fixed)

    def test_observance_stays_on_the_observance(self) -> None:
        script = (
            "Hey friends, taking a look back on this day in music history. "
            "In 1958, Buddy Holly's final recordings captured one of rock's most powerful moments. "
            "What's a memory that plays on loop for you? "
            "It's Breast Cancer Awareness Month. "
            "October is Breast Cancer Awareness Month, a time to support those fighting breast cancer."
        )
        fixed = bc.focus_spoken_break(
            script,
            subject="fun_day",
            label="Breast Cancer Awareness Month",
            note="October is Breast Cancer Awareness Month, a time to support those fighting breast cancer.",
        )
        self.assertIn("Breast Cancer Awareness Month", fixed)
        self.assertNotIn("Buddy Holly", fixed)
        self.assertNotIn("Hey friends", fixed)
        self.assertNotIn("?", fixed)

    def test_music_break_drops_stock_pads_and_the_request_closer(self) -> None:
        script = (
            "We've been spinning the good stuff from the seventies. "
            "Hope you're enjoying your weekend, and the music still feels easy. "
            "Back to the music. "
            "Glad you're still hanging out with me. "
            "Plenty of good songs still rolling through. "
            "Stick around. "
            "If you've got a request, click Request a Song at the top of mosplaceradio.com."
        )
        fixed = bc.focus_spoken_break(script, subject="music")
        self.assertIn("seventies", fixed.lower())
        self.assertIn("Back to the music", fixed)
        self.assertNotIn("hanging out", fixed.lower())
        self.assertNotIn("Hope you're enjoying", fixed)
        self.assertNotIn("Request a Song", fixed)
        self.assertNotIn("Stick around", fixed)

    def test_missing_subject_uses_the_supplied_note_only(self) -> None:
        fixed = bc.focus_spoken_break(
            "Hey friends, the Keys are calling and I grabbed a coffee.",
            subject="fun_day",
            label="National Chocolate Cupcake Day",
            note="National Chocolate Cupcake Day is a day for chocolate cupcakes.",
        )
        self.assertIn("Chocolate Cupcake", fixed)
        self.assertNotIn("Keys", fixed)
        self.assertNotIn("coffee", fixed.lower())

    def test_recent_opening_is_not_reused(self) -> None:
        script = (
            "The slower songs fit this rainy hour. "
            "I'll stay with that for a minute."
        )
        fixed = bc.focus_spoken_break(
            script,
            subject="music",
            recent_opening_fingerprints=["the slower songs fit this rainy"],
        )
        self.assertNotIn("rainy hour", fixed.lower())
        self.assertIn("stay with that", fixed)

    def test_handoff_keeps_the_handoff(self) -> None:
        script = (
            "I'm Bailey, handing off to Kathy. "
            "Hope you had a great weekend, especially with all the rain we've been having. "
            "I've been thinking about Mo-Ca-Bay, he's still the best at sniffing out the good stuff. "
            "If your life came with a warning label, what would it say? "
            "Head over to mosplace.radio.com. "
            "Have a great day everyone, remember to woosah and stay away from the filthy chooches. "
            "Love you, bye. "
            "Let us know what you think by clicking Community at mosplaceradio.com."
        )
        fixed = bc.focus_spoken_break(script, subject="handoff")
        self.assertIn("handing off to Kathy", fixed)
        self.assertIn("woosah", fixed)
        self.assertIn("Love you, bye", fixed)
        self.assertNotIn("Mo-Ca-Bay", fixed)
        self.assertNotIn("weekend", fixed.lower())
        self.assertNotIn("warning label", fixed.lower())
        self.assertNotIn("mosplace", fixed.lower())

    def test_peter_birthday_is_only_the_birthday(self) -> None:
        script = (
            "Hey everyone, Kathy heeer on Moe's Place Radio. "
            "This afternoon, the Daily Mix is all about variety—because variety sounds good. "
            "Hope you had a great weekend, Peter. "
            "From all of us, happy birthday, Peter! "
            "We've got a fresh mix rolling in—great tunes, great vibes. "
            "Keep your ears tuned, and let the music bring you right in. "
            "If you have got a request, click Request a Song at the top of Moe's Place Radio dot com."
        )
        fixed = bc.focus_spoken_break(script, subject="birthday", label="Peter")
        self.assertEqual(fixed, "Happy birthday to Peter. Hope the day treats you well.")
        self.assertLess(fixed.casefold().find("happy birthday"), fixed.casefold().find("peter"))
        self.assertNotIn("weekend, peter", fixed.casefold())
        self.assertNotIn("peter, happy birthday", fixed.casefold())
        self.assertNotIn("heeer", fixed.lower())
        self.assertNotIn("Hey everyone", fixed)
        self.assertNotIn("weekend", fixed.lower())
        self.assertNotIn("variety", fixed.lower())
        self.assertNotIn("fresh mix", fixed.lower())
        self.assertNotIn("Request a Song", fixed)
        self.assertNotIn("dot com", fixed.lower())
        self.assertNotIn("from all of us", fixed.lower())

    def test_birthday_never_says_the_name_before_the_wish(self) -> None:
        script = "Peter, happy birthday! Hope you had a great weekend, Peter."
        fixed = bc.focus_spoken_break(script, subject="birthday", label="Peter")
        lowered = fixed.casefold()
        self.assertTrue(lowered.startswith("happy birthday"))
        self.assertLess(lowered.find("happy birthday"), lowered.find("peter"))
        self.assertNotIn("weekend, peter", lowered)
        self.assertNotIn("peter, happy birthday", lowered)
        self.assertNotIn("from all of us", lowered)
        for sentence in fixed.replace("!", ".").replace("?", ".").split("."):
            name_at = sentence.casefold().find("peter")
            wish_at = sentence.casefold().find("happy birthday")
            if name_at >= 0 and wish_at >= 0:
                self.assertLess(wish_at, name_at)

    def test_birthday_does_not_keep_the_weekend_story(self) -> None:
        script = (
            "Hope you had a great weekend. Out in the Keys the air still feels easy. "
            "Happy birthday to John Gantz. Hope the day treats you well. "
            "If you've got a request, click Request a Song at the top of mosplaceradio.com."
        )
        fixed = bc.focus_spoken_break(
            script,
            subject="birthday",
            label="John Gantz",
            note="Happy birthday to John Gantz.",
        )
        self.assertIn("John Gantz", fixed)
        self.assertNotIn("Keys", fixed)
        self.assertNotIn("Request a Song", fixed)
        self.assertNotIn("great weekend", fixed.lower())


if __name__ == "__main__":
    unittest.main()

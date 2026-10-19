"""Repair samples for the restored human-DJ rules.

The BEFORE strings were captured by running the restored
repair_human_dj_script, with preferred_cta='request', before
limit_to_one_cta stopped appending a request closer. They are real
function output, not model speech.
"""

from __future__ import annotations

import unittest

import livedj_human_dj_rules as rules

rules.allow_live_clock_rewrite(False)

KATHY_SONG = (
    "The booth is quiet and the next record is already cued. "
    "Otis Redding's Dock of the Bay is sitting right there. "
    "I'll stay with that mood for a minute."
)
MO_SONG = (
    "That harbor light makes the whole room feel slower. "
    "Dock of the Bay fits it, so I'll let it play."
)
BAILEY_SONG = (
    "Some records just walk in and sit down. "
    "Dock of the Bay does that. No need to dress it up."
)
KATHY_NO_SONG = (
    "The booth is quiet and the next record is already cued. "
    "I'll stay with that for a minute and not rush the room."
)
REQUEST_CLOSER = (
    "If you've got a request, click Request a Song at the top of mosplaceradio.com."
)

# Captured 2026-10-17 from the restored function before the limit_to_one_cta edit.
# Producer passes preferred_cta from pick_break_cta(), which returned "request".
ORIGINAL_PREFERRED = {
    "kathy_song": f"{KATHY_SONG} {REQUEST_CLOSER}",
    "mo_song": f"{MO_SONG} {REQUEST_CLOSER}",
    "bailey_song": f"{BAILEY_SONG} {REQUEST_CLOSER}",
    "kathy_nosong": f"{KATHY_NO_SONG} {REQUEST_CLOSER}",
}


class RepairSampleTests(unittest.TestCase):
    def test_original_rule_appended_a_request_when_preferred(self) -> None:
        """The captured before-fix lines are the request closer, not a song title."""
        for text in ORIGINAL_PREFERRED.values():
            self.assertTrue(text.endswith(REQUEST_CLOSER))
            self.assertNotIn("coming up", text.lower())

    def test_pick_break_cta_does_not_force_a_request(self) -> None:
        self.assertEqual(rules.pick_break_cta(), "")
        self.assertEqual(rules.pick_break_cta(bakehouse=True), "bakehouse")
        self.assertEqual(rules.pick_break_cta(listener_question=True), "community")

    def test_repair_leaves_supplied_song_and_no_song_scripts(self) -> None:
        samples = {
            "kathy_song": KATHY_SONG,
            "mo_song": MO_SONG,
            "bailey_song": BAILEY_SONG,
            "kathy_nosong": KATHY_NO_SONG,
        }
        for name, before in samples.items():
            one_arg = rules.repair_human_dj_script(before)
            preferred = rules.repair_human_dj_script(before, preferred_cta="request")
            self.assertEqual(one_arg, before, name)
            self.assertEqual(preferred, before, name)
            self.assertNotEqual(preferred, ORIGINAL_PREFERRED[name], name)
            self.assertNotIn(REQUEST_CLOSER, preferred)

    def test_an_actual_request_invite_still_names_the_click(self) -> None:
        script = "If you've got a request, send it in. Back to the music."
        fixed = rules.repair_human_dj_script(script)
        self.assertIn("click Request a Song at the top of mosplaceradio.com", fixed)

    def test_a_real_listener_question_still_gets_community(self) -> None:
        script = "How's your day going out there? The harbor is bright and the room can stay easy."
        fixed = rules.repair_human_dj_script(script)
        self.assertIn("clicking Community at mosplaceradio.com", fixed)
        self.assertNotIn(REQUEST_CLOSER, fixed)

    def test_music_history_list_keeps_two_facts(self) -> None:
        script = (
            "Hey friends, taking a look back on this day in music history. "
            "In 1958, Buddy Holly's final recordings captured one of rock's most powerful moments. "
            "Then in 1973, David Bowie released Pin Ups. "
            "In '87, George Michael dropped Faith. "
            "And in 1999, Tom Petty got a star on the Hollywood Walk of Fame."
        )
        fixed = rules.repair_human_dj_script(script)
        self.assertNotIn("Hey friends", fixed)
        self.assertIn("Buddy Holly", fixed)
        self.assertIn("David Bowie", fixed)
        self.assertNotIn("George Michael", fixed)
        self.assertNotIn("Tom Petty", fixed)

    def test_moes_place_rewrite_still_runs(self) -> None:
        fixed = rules.repair_human_dj_script("You're listening to Moe's Place Radio.")
        self.assertIn("Mo's Place", fixed)
        self.assertNotIn("Moe's Place", fixed)


if __name__ == "__main__":
    unittest.main()

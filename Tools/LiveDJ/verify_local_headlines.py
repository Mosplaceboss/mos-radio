"""Offline checks for LocalHeadlines today-only RSS filtering and host gating."""

from __future__ import annotations

import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

import LocalHeadlines as lh

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Top Stories</title>
    <item>
      <title>Patriots injury report ahead of Sunday matchup</title>
      <description>Several New England starters are listed as questionable.</description>
      <pubDate>Fri, 09 Oct 2026 15:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Man accused in mother's death returns to Massachusetts</title>
      <description>A grim crime story that must not air as a DJ aside.</description>
      <pubDate>Fri, 09 Oct 2026 14:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Boston festival weekend draws crowds to the Common</title>
      <description>Local celebration details for the weekend.</description>
      <pubDate>Fri, 09 Oct 2026 13:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Old national story from yesterday</title>
      <description>Should be ignored because the date is not today.</description>
      <pubDate>Thu, 08 Oct 2026 13:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""


class LocalHeadlinesTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.cache_path = Path(self._tmpdir.name) / "LocalHeadlinesToday.json"
        self._base_patch = mock.patch.object(lh, "BASE", Path(self._tmpdir.name))
        self._out_patch = mock.patch.object(lh, "OUTPUT_PATH", self.cache_path)
        self._base_patch.start()
        self._out_patch.start()
        self.addCleanup(self._base_patch.stop)
        self.addCleanup(self._out_patch.stop)

    def test_parse_keeps_today_local_and_skips_grim(self) -> None:
        items = lh.parse_rss_items(SAMPLE_RSS, today=date(2026, 10, 9))
        titles = [item["title"] for item in items]
        self.assertTrue(any("Patriots" in title for title in titles))
        self.assertTrue(any("Boston festival" in title for title in titles))
        self.assertFalse(any("death" in title.lower() for title in titles))
        self.assertFalse(any("yesterday" in title.lower() for title in titles))

    def test_host_gating(self) -> None:
        self.assertTrue(
            lh.wants_local_headlines(host="Kathy", event_type="Check-In", mission="Check in")
        )
        self.assertTrue(
            lh.wants_local_headlines(host="Bailey", event_type="Show Open", mission="")
        )
        self.assertTrue(
            lh.wants_local_headlines(host="Johnny J", event_type="Weekend Check-In", mission="")
        )
        self.assertFalse(
            lh.wants_local_headlines(host="Mo", event_type="Check-In", mission="Check in")
        )
        self.assertFalse(
            lh.wants_local_headlines(host="Kathy", event_type="Handoff", mission="Hand off")
        )

    def test_prompt_block_is_optional_and_not_a_newscast(self) -> None:
        block = lh.format_prompt_block(
            ["Boston festival weekend draws crowds to the Common"],
            when=date(2026, 10, 9),
            host="Kathy",
        )
        self.assertIn("OPTIONAL", block)
        self.assertIn("At most ONE short casual mention", block)
        self.assertIn("Do not name the news outlet", block)
        self.assertIn("Do not ramble", block)

        empty = lh.format_prompt_block([], when=date(2026, 10, 9), host="Bailey")
        self.assertIn("skip any news mention", empty)

    def test_refresh_uses_inline_xml_and_station_date(self) -> None:
        when = datetime(2026, 10, 9, 12, 0, tzinfo=ZoneInfo("America/New_York"))
        data = lh.refresh_local_headlines(when=when, force=True, xml_text=SAMPLE_RSS)
        self.assertEqual(data["date"], "2026-10-09")
        self.assertGreaterEqual(len(data["headlines"]), 1)
        self.assertTrue(self.cache_path.is_file())

        block = lh.prompt_block_for_break(
            host="Johnny J",
            event_type="Check-In",
            mission="Reconnect with listeners",
            when=when,
        )
        self.assertIn("TODAY'S LOCAL NEWS ASIDE SOURCE", block)
        self.assertIn("Patriots", block)

        skipped = lh.prompt_block_for_break(
            host="Casey",
            event_type="Check-In",
            mission="Reconnect with listeners",
            when=when,
        )
        self.assertEqual(skipped, "")


if __name__ == "__main__":
    unittest.main()

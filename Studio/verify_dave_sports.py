"""Offline checks for Dave's sports copy.

Idle Patriots, Red Sox, Celtics, Bruins, and Lowell Spinners stay silent.
A team with a game or news is mentioned. An MLB playoff item is spoken.
A down Spinners, MLB, or general Fox feed does not crash.
The general Fox feed adds other major headlines and does not repeat MLB items.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.error import URLError

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from app.core.news_content_model import (  # noqa: E402
    default_script_rules,
    generate_dev_script_preview,
    normalize_bundle,
    normalize_script_rules,
)
from app.core.sports_report import (  # noqa: E402
    DEFAULT_SPORTS_GAME_RULES,
    build_dave_sports_script,
    format_sports_story,
)

TODAY = date(2026, 10, 14)

IDLE_NOTES = [
    {"team": "Patriots", "text": "The Patriots are not playing."},
    {"team": "Red Sox", "text": "The Red Sox have no game today."},
    {"team": "Celtics", "text": "There is nothing to report on the Celtics."},
    {"team": "Bruins", "text": "The Bruins are idle."},
    {"team": "Lowell Spinners", "text": "The Lowell Spinners are not playing and there is nothing to report."},
]

_NS = (
    'xmlns:dc="http://purl.org/dc/elements/1.1/" '
    'xmlns:ps="http://www.prestosports.com/rss/schedule"'
)

SPINNER_TODAY = f"""<?xml version="1.0" encoding="ISO-8859-1"?>
<rss version="2.0" {_NS}>
  <channel>
    <title>2026 Schedule</title>
    <item>
      <title>Nashua Silver Knights vs. Lowell Spinners</title>
      <description>Baseball on Oct 14, 2026 at 7:00 PM: Nashua Silver Knights vs. Lowell Spinners</description>
      <pubDate>Wed, 14 Oct 2026 23:00:00 GMT</pubDate>
      <dc:date>2026-10-14T23:00:00Z</dc:date>
      <ps:opponent>Nashua Silver Knights</ps:opponent>
    </item>
  </channel>
</rss>
"""

SPINNER_NEXT = f"""<?xml version="1.0"?>
<rss version="2.0" {_NS}>
  <channel>
    <item>
      <title>Lowell Spinners vs. Worcester Bravehearts</title>
      <description>Baseball on Oct 16, 2026 at 6:35 PM: Lowell Spinners vs. Worcester Bravehearts</description>
      <dc:date>2026-10-16T22:35:00Z</dc:date>
      <ps:opponent>at Worcester Bravehearts</ps:opponent>
    </item>
  </channel>
</rss>
"""

SPINNER_PAST = f"""<?xml version="1.0"?>
<rss version="2.0" {_NS}>
  <channel>
    <item>
      <title>Lowell Spinners 5, New Britain Bees 11 Final</title>
      <description>Baseball on May 27, 2026 at 6:35 PM: Lowell Spinners vs. New Britain Bees, Final, 5-11</description>
      <dc:date>2026-05-27T22:35:00Z</dc:date>
      <ps:score>L, 11-5</ps:score>
      <ps:opponent>at New Britain Bees</ps:opponent>
    </item>
  </channel>
</rss>
"""

SPINNER_FINAL_TODAY = f"""<?xml version="1.0"?>
<rss version="2.0" {_NS}>
  <channel>
    <item>
      <title>Lowell Spinners 4, Nashua Silver Knights 2 Final</title>
      <description>Baseball on Oct 14, 2026 at 7:00 PM: Lowell Spinners vs. Nashua Silver Knights, Final, 4-2</description>
      <dc:date>2026-10-14T23:00:00Z</dc:date>
      <ps:opponent>at Nashua Silver Knights</ps:opponent>
      <ps:score>W, 4-2</ps:score>
    </item>
  </channel>
</rss>
"""

FOX_PLAYOFFS = """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Older ALCS note from last week</title>
      <description>A stale playoff recap.</description>
      <pubDate>Wed, 07 Oct 2026 12:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Dodgers wrap a regular-season series in Los Angeles</title>
      <description>A midweek wrap from Los Angeles.</description>
      <pubDate>Wed, 14 Oct 2026 18:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Rays even the ALCS and keep their World Series hopes alive</title>
      <description>Tampa Bay beat Cleveland 3-1 to tie the championship series.</description>
      <pubDate>Wed, 14 Oct 2026 05:34:00 GMT</pubDate>
    </item>
    <item>
      <title>Red Sox name a new manager</title>
      <description>Boston made the announcement on Wednesday.</description>
      <pubDate>Wed, 14 Oct 2026 15:00:00 GMT</pubDate>
    </item>
    <item>
      <title>The Patriots are not playing</title>
      <pubDate>Wed, 14 Oct 2026 16:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""

IDLE_PHRASES = (
    "not playing",
    "no game",
    "nothing to report",
    "are idle",
    "have no game",
)


def _spoken(lines: list[str]) -> str:
    return " ".join(lines).lower()


def _assert_no_idle(lines: list[str]) -> None:
    blob = _spoken(lines)
    for phrase in IDLE_PHRASES:
        assert phrase not in blob, (phrase, lines)


def main() -> None:
    idle = build_dave_sports_script(today=TODAY, team_notes=IDLE_NOTES, spinners_xml=SPINNER_PAST, fox_xml="")
    assert idle == [], idle
    _assert_no_idle(idle)
    for team in ("Patriots", "Red Sox", "Celtics", "Bruins", "Spinners"):
        assert team.lower() not in _spoken(idle)

    playing = build_dave_sports_script(
        today=TODAY,
        team_notes=[
            {"team": "Patriots", "text": "The Patriots are not playing. The Patriots host the Buffalo Bills today."},
            {"team": "Celtics", "text": "The Celtics beat the Knicks 112-98."},
            {"team": "Bruins", "text": "The Bruins are idle."},
            {"team": "Red Sox", "text": "The Red Sox have no game today."},
        ],
        spinners_xml=SPINNER_TODAY,
        fox_xml=FOX_PLAYOFFS,
    )
    blob = _spoken(playing)
    assert "patriots" in blob and "bills" in blob, playing
    assert "celtics" in blob and "knicks" in blob, playing
    assert "bruins" not in blob, playing
    assert "have no game" not in blob and "not playing" not in blob, playing
    assert "nashua silver knights" in blob, playing
    assert "spinners play the nashua silver knights today" in blob, playing
    assert "rays even the alcs" in blob, playing
    assert "world series" in blob, playing
    assert "red sox" in blob and "manager" in blob, playing
    assert "dodgers" not in blob, playing
    rays_at = next(index for index, line in enumerate(playing) if "Rays even" in line)
    older_at = next(index for index, line in enumerate(playing) if "Older ALCS" in line)
    assert rays_at < older_at, playing
    _assert_no_idle(playing)

    nxt = build_dave_sports_script(today=TODAY, spinners_xml=SPINNER_NEXT, fox_xml="")
    assert len(nxt) == 1, nxt
    assert "next game" in nxt[0].lower() and "Worcester Bravehearts" in nxt[0], nxt
    assert "October 16" in nxt[0], nxt
    _assert_no_idle(nxt)

    final_today = build_dave_sports_script(today=TODAY, spinners_xml=SPINNER_FINAL_TODAY, fox_xml="")
    assert any("4" in line and "2" in line and "final" in line.lower() for line in final_today), final_today
    assert "9-0" not in " ".join(final_today)
    _assert_no_idle(final_today)

    past = build_dave_sports_script(today=TODAY, spinners_xml=SPINNER_PAST, fox_xml="")
    assert past == [], past

    makeup = """<?xml version="1.0"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:ps="http://www.prestosports.com/rss/schedule">
  <channel>
    <item>
      <title>Lowell Spinners 2, Norwich Sea Unicorns 7 Final</title>
      <description>Baseball on Oct 14, 2026 at 4:00 PM: Lowell Spinners vs. Norwich Sea Unicorns, Postponed from 10/10, Final, 2-7</description>
      <dc:date>2026-10-14T20:00:00Z</dc:date>
      <ps:opponent>at Norwich Sea Unicorns</ps:opponent>
      <ps:score>L, 7-2</ps:score>
    </item>
  </channel>
</rss>
"""
    makeup_lines = build_dave_sports_script(today=TODAY, spinners_xml=makeup, fox_xml="")
    assert any("final" in line.lower() and "2" in line for line in makeup_lines), makeup_lines
    assert "postponed" not in " ".join(makeup_lines).lower()
    _assert_no_idle(makeup_lines)

    def _down(_url: str, _timeout: float) -> str:
        raise URLError("feed down")

    down = build_dave_sports_script(today=TODAY, fetch=True, fetcher=_down)
    assert down == [], down
    survived = build_dave_sports_script(
        today=TODAY,
        fetch=True,
        fetcher=_down,
        spinners_xml=URLError("spinners down"),
        fox_xml=OSError("fox down"),
        other_xml=[URLError("other down"), "<rss>"],
        team_notes=[{"team": "Celtics", "text": "The Celtics beat the Knicks 112-98."}],
    )
    assert any("Celtics" in line for line in survived), survived
    _assert_no_idle(survived)

    broken = build_dave_sports_script(
        today=TODAY, spinners_xml="<rss>", fox_xml="not xml", fox_general_xml="also not xml"
    )
    assert broken == [], broken

    general_xml = """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Rays even the ALCS and keep their World Series hopes alive</title>
      <description>The same playoff story as the MLB feed.</description>
      <pubDate>Wed, 14 Oct 2026 06:00:00 GMT</pubDate>
    </item>
    <item>
      <title>49ers' Dre Greenlaw suspended 1 game after headbutting Seahawks' Ernest Jones IV</title>
      <description>San Francisco's linebacker will sit out one game.</description>
      <pubDate>Wed, 14 Oct 2026 12:00:00 GMT</pubDate>
    </item>
    <item>
      <title>The Patriots are not playing</title>
      <pubDate>Wed, 14 Oct 2026 13:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Underdog Promo Code FOXSPORTS: Play $5, Get $100 on Rays or Guardians</title>
      <description>Odds and a sign-up bonus.</description>
      <pubDate>Wed, 14 Oct 2026 14:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Cowboys' defense draws questions after another leaky afternoon</title>
      <pubDate>Wed, 14 Oct 2026 11:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""
    combined = build_dave_sports_script(
        today=TODAY,
        fox_xml=FOX_PLAYOFFS,
        fox_general_xml=general_xml,
    )
    combined_blob = _spoken(combined)
    assert combined_blob.count("rays even the alcs") == 1, combined
    assert "49ers" in combined_blob and "greenlaw" in combined_blob, combined
    assert "cowboys" in combined_blob, combined
    assert "promo code" not in combined_blob and "underdog" not in combined_blob, combined
    assert "not playing" not in combined_blob, combined
    _assert_no_idle(combined)

    def _mlb_only(url: str, _timeout: float) -> str:
        if "tags=fs" in url:
            return FOX_PLAYOFFS
        raise URLError("general fox down")

    mlb_only = build_dave_sports_script(today=TODAY, fetch=True, fetcher=_mlb_only)
    assert any("Rays even the ALCS" in line for line in mlb_only), mlb_only
    _assert_no_idle(mlb_only)

    college_xml = """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Bob Chesney, UCLA Bruins top the AP Big Ten list</title>
      <pubDate>Wed, 14 Oct 2026 18:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Favorite 'Dogs: Back Broncos; Badgers Over Bruins</title>
      <pubDate>Wed, 14 Oct 2026 17:00:00 GMT</pubDate>
    </item>
    <item>
      <title>The Bruins beat the Rangers 4-2</title>
      <pubDate>Wed, 14 Oct 2026 16:00:00 GMT</pubDate>
    </item>
    <item>
      <title>The Bruins are idle</title>
      <pubDate>Wed, 14 Oct 2026 15:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""
    college = build_dave_sports_script(today=TODAY, fox_xml="", fox_general_xml=college_xml)
    college_blob = _spoken(college)
    assert "rangers" in college_blob and "4-2" in college_blob, college
    assert "ucla" in college_blob, college
    assert "favorite" not in college_blob, college
    assert "are idle" not in college_blob, college
    _assert_no_idle(college)

    rules = default_script_rules()
    sports_rules = rules["sports_game_rules"].lower()
    assert sports_rules == DEFAULT_SPORTS_GAME_RULES.lower()
    assert "playoff" in sports_rules and "stay silent" in sports_rules and "spinners" in sports_rules
    assert "general fox" in sports_rules
    assert "dave reads sports" in rules["news_first_personality_rules"].lower()

    legacy = normalize_script_rules(
        {
            "sports_game_rules": (
                "If a team does not play today, do not say there is no game or that they are off. "
                "Say something similar to: their next game is… using the supplied schedule."
            ),
            "news_first_personality_rules": "Lead anchor opens every newscast.",
        }
    )
    assert legacy["sports_game_rules"] == DEFAULT_SPORTS_GAME_RULES
    assert "stay silent" in legacy["news_first_personality_rules"].lower()
    again = normalize_script_rules(legacy)
    assert again["sports_game_rules"] == legacy["sports_game_rules"]
    assert again["news_first_personality_rules"] == legacy["news_first_personality_rules"]

    custom = normalize_script_rules({"sports_game_rules": "Keep sports brief."})
    assert "keep sports brief" in custom["sports_game_rules"].lower()
    assert "mlb playoff" in custom["sports_game_rules"].lower()
    assert "stay silent" in custom["sports_game_rules"].lower()
    assert "general fox" in custom["sports_game_rules"].lower()
    assert normalize_script_rules(custom)["sports_game_rules"] == custom["sports_game_rules"]

    assert format_sports_story(IDLE_NOTES and [note["text"] for note in IDLE_NOTES]) == ""

    bundle = normalize_bundle({})
    with TemporaryDirectory() as temp:
        out = Path(temp)
        with patch("app.core.news_content_model.news_dev_output_dir", return_value=out):
            idle_path = Path(generate_dev_script_preview(bundle, sports_lines=[note["text"] for note in IDLE_NOTES]))
            live_path = Path(generate_dev_script_preview(bundle, sports_lines=playing))
        idle_text = idle_path.read_text(encoding="utf-8").lower()
        live_text = live_path.read_text(encoding="utf-8")
        assert "sample headline" in idle_text
    for phrase in IDLE_PHRASES:
        assert phrase not in idle_text, phrase
    assert "patriots" not in idle_text and "spinners" not in idle_text
    assert "Rays even the ALCS" in live_text
    assert "Nashua Silver Knights" in live_text
    assert "not playing" not in live_text.lower()

    print("OK: Dave sports silence, Spinners, MLB playoffs, and general Fox headlines verified")


if __name__ == "__main__":
    main()

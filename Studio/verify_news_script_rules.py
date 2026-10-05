"""Verify news New England wording, Community close, and sports obituary rules."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.news_content_model import (  # noqa: E402
    DEFAULT_LOTTERY_CLOSING,
    DEFAULT_NEWS_CLOSING,
    DEFAULT_SPORTS_GAME_RULES,
    apply_news_pronunciation_rules,
    default_script_rules,
    normalize_script_rules,
)


def main() -> None:
    # New England replacement
    spoken = apply_news_pronunciation_rules(
        "Good morning from the Merrimack Valley and across Merrimack Valley."
    )
    assert "Merrimack Valley" not in spoken, spoken
    assert spoken.count("New England") == 2, spoken

    rules = default_script_rules()
    assert "selecting Community at mosplaceradio.com" in rules["closing"]
    assert "Now back to the music" in rules["closing"]
    assert rules["lottery_closing"] == DEFAULT_LOTTERY_CLOSING
    assert "lottery dreams" in rules["lottery_close_rules"].lower()
    assert "back to the music" in rules["lottery_close_rules"].lower()  # as "do not say..."
    assert "do not say now back to the music" in rules["lottery_close_rules"].lower()
    assert "obituar" in rules["sports_game_rules"].lower() or "death" in rules["sports_game_rules"].lower()
    assert "New England" in rules["news_first_personality_rules"]
    assert "lottery" in rules["news_first_personality_rules"].lower()

    # Legacy short closing upgrades
    upgraded = normalize_script_rules(
        {"closing": "For Mo's Place Radio, I'm {personality}.", "sports_game_rules": ""}
    )
    assert upgraded["closing"] == DEFAULT_NEWS_CLOSING
    assert upgraded["sports_game_rules"] == DEFAULT_SPORTS_GAME_RULES

    # Older Community click phrasing upgrades to today's-stories + selecting
    older = normalize_script_rules(
        {
            "closing": (
                "We'd love to hear from you — if there's anything on your mind, "
                "click Community at mosplaceradio.com. For Mo's Place Radio, I'm {personality}."
            )
        }
    )
    assert "today's stories" in older["closing"]
    assert "selecting Community" in older["closing"]
    assert "Now back to the music" in older["closing"]

    # Sports without obituaries upgrades
    sports = normalize_script_rules(
        {
            "sports_game_rules": (
                "If there is no news regarding a sports team, do not mention that team and "
                "do not say there is no news. Skip them quietly. "
                "If a team does not play today, do not say there is no game or that they are off. "
                "Say something similar to: their next game is… using the supplied schedule. "
                "Only mention a next game when the date or opponent is provided — never invent one."
            )
        }
    )
    assert "Penguin" in sports["sports_game_rules"] or "obituar" in sports["sports_game_rules"].lower()
    assert "death" in sports["sports_game_rules"].lower() or "memorial" in sports["sports_game_rules"].lower()

    # Lottery close upgrades from empty / back-to-the-music habits
    lottery = normalize_script_rules({"lottery_closing": "Now back to the music.", "lottery_close_rules": ""})
    assert lottery["lottery_closing"] == DEFAULT_LOTTERY_CLOSING
    assert "lottery dreams" in lottery["lottery_close_rules"].lower()
    assert "do not say now back to the music" in lottery["lottery_close_rules"].lower()

    print("OK: news New England, Community close, sports obituaries, and lottery close verified")


if __name__ == "__main__":
    main()

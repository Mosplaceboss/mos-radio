"""Verify Dave sports rules include MLB playoff coverage."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.news_content_model import (  # noqa: E402
    DEFAULT_SPORTS_GAME_RULES,
    default_script_rules,
    normalize_script_rules,
)


def main() -> None:
    rules = default_script_rules()
    sports = rules["sports_game_rules"].lower()
    assert "mlb" in sports and "playoff" in sports, rules["sports_game_rules"]
    assert "local team is not playing" in sports, rules["sports_game_rules"]
    assert "dave covers sports" in rules["news_first_personality_rules"].lower()
    assert "playoff" in DEFAULT_SPORTS_GAME_RULES.lower()

    # Empty sports rules upgrade to full default (includes playoffs).
    upgraded = normalize_script_rules({"sports_game_rules": ""})
    assert upgraded["sports_game_rules"] == DEFAULT_SPORTS_GAME_RULES

    # Legacy next-game-only rules upgrade to full default.
    legacy = normalize_script_rules(
        {
            "sports_game_rules": (
                "If a team does not play today, do not say there is no game or that they are off. "
                "Say something similar to: their next game is… using the supplied schedule. "
                "Only mention a next game when the date or opponent is provided — never invent one."
            )
        }
    )
    assert "mlb playoff" in legacy["sports_game_rules"].lower()

    # Custom rules without playoffs get the playoff prefix appended.
    custom = normalize_script_rules(
        {"sports_game_rules": "Keep sports brief and stick to supplied team notes only."}
    )
    assert custom["sports_game_rules"].lower().startswith("during the mlb postseason")
    assert "keep sports brief" in custom["sports_game_rules"].lower()

    # Personality rules without playoff mention get Dave sports guidance.
    personality = normalize_script_rules(
        {"news_first_personality_rules": "Lead anchor opens every newscast."}
    )
    assert "MLB" in personality["news_first_personality_rules"]
    assert "playoff" in personality["news_first_personality_rules"].lower()

    print("OK: Dave sports MLB playoff rules verified")


if __name__ == "__main__":
    main()

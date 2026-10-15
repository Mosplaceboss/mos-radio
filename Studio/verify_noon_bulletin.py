"""The 12:15 bulletin keeps Mo, Johnny, Dave, Michael G, Mo and names 12:15."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Studio"))
sys.path.insert(0, str(ROOT / "Automation" / "News"))

from build_bulletin import build_bulletin_text  # noqa: E402
from app.core.entertainment_report import (  # noqa: E402
    DAVE_SPORTS_CLOSE,
    JOHNNY_MORNING_BRIDGE,
    MICHAEL_HANDOFF,
    MO_MORNING_OPEN,
    EntertainmentStory,
)


def main() -> None:
    story = EntertainmentStory(
        title="Ocean Light trailer",
        summary="Opens June 12. A lighthouse keeper finds a map at sea.",
        url="https://example.com/ocean",
        source_id="variety",
        source_name="Variety",
        kind="film_news",
        slot="variety_film_news",
        published=datetime(2026, 10, 14, 14, 0, tzinfo=timezone.utc),
    )
    script = build_bulletin_text(
        air="12:15",
        fetch=False,
        news_copy="The council meets tonight at town hall.",
        sports_lines=[
            "The Patriots are not playing.",
            "The Red Sox have no game today.",
            "The Celtics beat the Knicks.",
            "The Bruins are idle.",
            "The Lowell Spinners are not playing.",
        ],
        stories=[story],
    )
    assert MO_MORNING_OPEN in script
    assert JOHNNY_MORNING_BRIDGE in script
    assert "The council meets tonight at town hall." in script
    assert script.index("[DJ Mo]") < script.index("[Johnny J]") < script.index("[Dave]")
    assert script.index("[Dave]") < script.index("[Michael G]") < script.rindex("[DJ Mo]")
    assert DAVE_SPORTS_CLOSE in script
    assert "Thanks, Dave. Michael G here with the entertainment report." in script
    assert MICHAEL_HANDOFF in script
    assert "Thanks, Michael G. Weekdays at 12:15 on Mo's Place Radio." in script
    assert "7:15" not in script
    assert "not playing" not in script.lower()
    assert "Celtics" in script
    assert "In movie news" in script
    assert "Ocean Light" in script

    def boom(*_args, **_kwargs):
        raise RuntimeError("feed exploded")

    import build_bulletin

    with patch.object(build_bulletin, "build_dave_sports_script", boom), patch.object(
        build_bulletin, "collect_entertainment_report", boom
    ):
        failed = build_bulletin_text(
            air="12:15",
            fetch=True,
            news_copy="Headlines still air.",
            sports_lines=None,
            stories=None,
        )
    assert "Headlines still air." in failed
    assert DAVE_SPORTS_CLOSE in failed
    assert MICHAEL_HANDOFF in failed
    assert "12:15" in failed
    print("OK: 12:15 bulletin keeps Mo, Johnny, Dave, Michael G, Mo and the 12:15 clock")


if __name__ == "__main__":
    main()

"""Morning bulletin is Mo, Johnny, Dave, Michael G, Mo — and skips yesterday's copy."""

from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Studio"))
sys.path.insert(0, str(ROOT / "Automation" / "News"))

from build_bulletin import (  # noqa: E402
    build_bulletin_text,
    load_news_copy,
    news_copy_is_fresh,
    write_bulletin,
)
from app.core.entertainment_report import (  # noqa: E402
    DAVE_SPORTS_CLOSE,
    JOHNNY_MORNING_BRIDGE,
    MICHAEL_HANDOFF,
    MO_MORNING_OPEN,
    EntertainmentStory,
    split_morning_news_copy,
)

STATION_TZ = ZoneInfo("America/New_York")


def main() -> None:
    story = EntertainmentStory(
        title="Ocean Light trailer",
        summary="Opens June 12. A lighthouse keeper finds a map at sea.",
        url="https://example.com/ocean",
        source_id="variety",
        source_name="Variety",
        kind="film_news",
        slot="variety_film_news",
        published=datetime(2026, 10, 15, 14, 0, tzinfo=timezone.utc),
    )
    script = build_bulletin_text(
        air="7:15",
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
    assert script.index(MO_MORNING_OPEN) < script.index("council meets")
    assert script.index("council meets") < script.index(DAVE_SPORTS_CLOSE)
    assert DAVE_SPORTS_CLOSE in script
    assert "Thanks, Dave. Michael G here with the entertainment report." in script
    assert MICHAEL_HANDOFF in script
    assert "Thanks, Michael G. Weekdays at 7:15 and 12:15 on Mo's Place Radio." in script
    assert "not playing" not in script.lower()
    assert "Celtics" in script
    assert "In movie news" in script
    assert "Ocean Light" in script

    mo_body, johnny_body = split_morning_news_copy(
        "[DJ Mo]\nGood morning from the newsroom.\n[Johnny J]\nTown hall is packed tonight."
    )
    assert mo_body == "Good morning from the newsroom."
    assert johnny_body == "Town hall is packed tonight."

    now = datetime(2026, 10, 15, 6, 30, tzinfo=STATION_TZ)
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        fresh = folder / "news_copy.txt"
        fresh.write_text("Fresh local headlines for today.", encoding="utf-8")
        assert news_copy_is_fresh(fresh, now=now)
        assert "Fresh local headlines" in load_news_copy(fresh, now=now)

        stale = folder / "stale_copy.txt"
        stale.write_text("Yesterday's leftover headlines.", encoding="utf-8")
        stale_mtime = (now - timedelta(days=1)).timestamp()
        import os

        os.utime(stale, (stale_mtime, stale_mtime))
        assert not news_copy_is_fresh(stale, now=now)
        assert load_news_copy(stale, now=now) == ""

        out = folder / "bulletin.txt"
        path = write_bulletin(
            air="7:15",
            fetch=False,
            news_file=stale,
            output=out,
            sports_lines=["The Celtics beat the Knicks."],
            stories=[story],
            now=now,
        )
        text = path.read_text(encoding="utf-8")
        assert "Yesterday's leftover headlines." not in text
        assert MO_MORNING_OPEN in text
        assert JOHNNY_MORNING_BRIDGE in text
        assert DAVE_SPORTS_CLOSE in text
        assert MICHAEL_HANDOFF in text

    def boom(*_args, **_kwargs):
        raise RuntimeError("feed exploded")

    import build_bulletin

    with patch.object(build_bulletin, "build_dave_sports_script", boom), patch.object(
        build_bulletin, "collect_entertainment_report", boom
    ):
        failed = build_bulletin_text(
            air="7:15",
            fetch=True,
            news_copy="Headlines still air.",
            sports_lines=None,
            stories=None,
        )
    assert "Headlines still air." in failed
    assert MO_MORNING_OPEN in failed
    assert "[Johnny J]" in failed
    assert DAVE_SPORTS_CLOSE in failed
    assert MICHAEL_HANDOFF in failed
    print("OK: morning bulletin is Mo, Johnny, Dave, Michael G, Mo and skips stale copy")


if __name__ == "__main__":
    main()

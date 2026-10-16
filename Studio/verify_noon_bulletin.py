"""The 12:15 bulletin is Mo, Johnny, Bailey, Michael G, Mo and names 12:15."""

from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Studio"))

from app.core.news_bulletin import build_bulletin_text  # noqa: E402
from app.core.entertainment_report import (  # noqa: E402
    BAILEY_ENTERTAINMENT_CLOSE,
    JOHNNY_MIDDAY_BRIDGE,
    MICHAEL_HANDOFF,
    MO_MIDDAY_OPEN,
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
        published=datetime.now(timezone.utc),
    )
    script = build_bulletin_text(
        air="12:15",
        fetch=False,
        news_copy="The council meets tonight at town hall.",
        sports_lines=[
            "The Patriots are not playing.",
            "The Celtics beat the Knicks.",
        ],
        stories=[story],
    )
    assert MO_MIDDAY_OPEN in script
    assert JOHNNY_MIDDAY_BRIDGE in script
    assert "The council meets tonight at town hall." in script
    assert script.index("[DJ Mo]") < script.index("[Johnny J]") < script.index("[Bailey]")
    assert script.index("[Bailey]") < script.index("[Michael G]") < script.rindex("[DJ Mo]")
    assert "[Dave]" not in script
    assert "Celtics" not in script
    assert BAILEY_ENTERTAINMENT_CLOSE in script
    assert "Thanks, Bailey. Michael G here with the entertainment report." in script
    assert "Thanks, Dave." not in script
    assert MICHAEL_HANDOFF in script
    assert "Thanks, Michael G. Weekdays at 12:15 on Mo's Place Radio." in script
    assert "7:15" not in script
    assert "In movie news" in script
    assert "Ocean Light" in script

    def boom(*_args, **_kwargs):
        raise RuntimeError("feed exploded")

    import app.core.news_bulletin as news_bulletin

    with patch.object(news_bulletin, "build_dave_sports_script", boom), patch.object(
        news_bulletin, "collect_entertainment_report", boom
    ):
        failed = build_bulletin_text(
            air="12:15",
            fetch=True,
            news_copy="Headlines still air.",
            sports_lines=None,
            stories=None,
            news_dir=Path(tempfile.gettempdir()),
        )
    assert "Headlines still air." in failed
    assert "[Bailey]" in failed
    assert "[Dave]" not in failed
    assert MICHAEL_HANDOFF in failed
    assert "12:15" in failed
    print("OK: 12:15 bulletin is Mo, Johnny, Bailey, Michael G, Mo and the 12:15 clock")


if __name__ == "__main__":
    main()

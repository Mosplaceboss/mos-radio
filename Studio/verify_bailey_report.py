"""Bailey midday: Hidden Boston + Good News Wag animals, then Love you, bye."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Studio"))

from app.core.bailey_report import (  # noqa: E402
    BAILEY_GOOD_NEWS_WAG,
    BAILEY_HIDDEN_BOSTON_OPEN,
    BAILEY_LAST_LINE,
    BaileyStory,
    bailey_feed_urls,
    bailey_midday_script,
    collect_bailey_report,
    parse_animal_feed_xml,
    parse_hidden_boston_xml,
    pick_hidden_boston,
)
from app.core.entertainment_report import (  # noqa: E402
    ENTERTAINMENT_STORY_COUNT,
    build_midday_flow,
)


def _check(label: str, ok: bool) -> None:
    if not ok:
        raise AssertionError(label)


HIDDEN_XML = """<?xml version="1.0"?>
<rss version="2.0"><channel>
<item><title>Brown Jug Chelsea</title><description>Pizza and wings in Chelsea.</description></item>
<item><title>MexiCali Burrito</title><description>Vegetable specials in Kendall Square.</description></item>
<item><title>Harbor Clam Shack</title><description>Fried clams by the water.</description></item>
<item><title>North End Nook</title><description>Tiny pasta spot.</description></item>
</channel></rss>
"""

ANIMAL_XML = """<?xml version="1.0"?>
<rss version="2.0"><channel>
<item>
  <title>Rescue pup finds forever home</title>
  <description>A shelter dog named Maple was adopted after waiting six months.</description>
  <category>Animals</category>
</item>
<item>
  <title>Kelly Clarkson sings a new album</title>
  <description>Entertainment news that must be skipped.</description>
  <category>Celebrities</category>
</item>
</channel></rss>
"""


def main() -> None:
    places = parse_hidden_boston_xml(HIDDEN_XML)
    _check("parses Hidden Boston favorites", len(places) == 4)
    picked = pick_hidden_boston(places, pool=3, speak=2, rng=__import__("random").Random(7))
    _check("rotates Hidden Boston picks", len(picked) == 2)

    animals = parse_animal_feed_xml(ANIMAL_XML, source_id="good_news_network_animals")
    _check("keeps animal story", len(animals) == 1 and "Maple" in animals[0].summary)
    _check("skips celebrity GNN item", all("Clarkson" not in a.title for a in animals))

    script = bailey_midday_script(hidden_boston=picked, animals=animals)
    _check("opens Hidden Boston", BAILEY_HIDDEN_BOSTON_OPEN in script)
    _check("includes Good News Wag lead-in", BAILEY_GOOD_NEWS_WAG in script)
    _check("ends Love you bye", script.rstrip().endswith("Love you, bye!"))
    _check("Hidden Boston before Wag", script.index(BAILEY_HIDDEN_BOSTON_OPEN) < script.index(BAILEY_GOOD_NEWS_WAG))
    _check("Wag before close", script.index(BAILEY_GOOD_NEWS_WAG) < script.index(BAILEY_LAST_LINE))

    empty = bailey_midday_script(hidden_boston=[], animals=[])
    _check("empty feeds still close", empty == BAILEY_LAST_LINE)

    report = collect_bailey_report(
        {
            "https://www.hiddenboston.com/favorites.xml": HIDDEN_XML,
            "https://www.goodnewsnetwork.org/tag/dogs/feed/": ANIMAL_XML,
            "https://www.goodnewsnetwork.org/category/news/animals/feed/": "<rss/>",
            "https://dogwithblog.in/feed/": "<rss/>",
        },
        fetch=False,
        rng=__import__("random").Random(3),
    )
    _check("collect builds script", "Hidden Boston" in report["script"])
    _check("collect has food", bool(report["hidden_boston"]))
    _check("collect has animals", bool(report["animals"]))

    food = [
        BaileyStory("Brown Jug Chelsea", "Pizza and wings.", "hidden_boston", "hidden_boston"),
    ]
    wag = [
        BaileyStory("Rescue pup finds forever home", "Maple was adopted.", "gnn", "animal"),
    ]
    flow = build_midday_flow(
        [],
        sports_body="The Celtics beat the Knicks.",
        bailey_script=bailey_midday_script(hidden_boston=food, animals=wag),
    )
    _check("midday still four Michael slots", ENTERTAINMENT_STORY_COUNT == 4)
    _check("Bailey page in midday script", "Hidden Boston" in flow["script"])
    _check("Good News Wag in midday script", "Good News Wag" in flow["script"])
    _check("Michael still hands to Bailey", "Bailey, over to you." in flow["michael_g_script"])
    _check("Mo Love you hun after Bailey", flow["mo_thanks"].startswith("Love you, hun."))
    _check(
        "order Mo Johnny Dave Michael Bailey Mo",
        flow["script"].index("[DJ Mo]")
        < flow["script"].index("[Johnny J]")
        < flow["script"].index("[Dave]")
        < flow["script"].index("[Michael G]")
        < flow["script"].index("[Bailey]")
        < flow["script"].rindex("[DJ Mo]"),
    )
    _check("feed url list includes Hidden Boston", any("hiddenboston.com" in u for u in bailey_feed_urls()))
    _check("feed url list includes GNN animals", any("animals/feed" in u for u in bailey_feed_urls()))

    print("OK: Bailey midday Hidden Boston + Good News Wag restored")


if __name__ == "__main__":
    main()

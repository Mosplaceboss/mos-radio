"""Offline checks for Michael G's morning entertainment report."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from app.core.entertainment_report import (  # noqa: E402
    DAVE_SPORTS_CLOSE,
    ENTERTAINMENT_SOURCES,
    MICHAEL_G_VOICEBOX_ID,
    MICHAEL_G_VOICEBOX_PROFILE,
    MO_THANKS,
    EntertainmentStory,
    build_morning_flow,
    collect_entertainment_stories,
    is_morning_safe,
    michael_g_script,
    select_entertainment_stories,
    spoken_story,
    sports_close_hands_to_michael,
)
from app.core.news_content_model import (  # noqa: E402
    build_dev_script_lines,
    default_script_rules,
    normalize_bundle,
    normalize_personalities,
    normalize_script_rules,
)

DEADLINE_URL = "https://deadline.com/feed/atom/"
TMZ_URL = "https://www.tmz.com/rss.xml"
VARIETY_URL = "https://variety.com/v/film/feed/"


def _check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)


def _story(
    title: str,
    *,
    summary: str = "",
    kind: str = "general",
    source_id: str = "deadline",
    published: datetime | None = None,
) -> EntertainmentStory:
    return EntertainmentStory(
        title=title,
        summary=summary,
        url="",
        source_id=source_id,
        source_name=source_id,
        kind=kind,
        published=published,
    )


def _dt(hour: int, day: int = 13) -> datetime:
    return datetime(2026, 10, day, hour, 0, tzinfo=timezone.utc)


def test_filters() -> None:
    _check("movie news stays", is_morning_safe("New comedy sets a summer release date"))
    _check("review stays", is_morning_safe("Review: midnight comedy is a charmer"))
    _check("celebrity death notice stays", is_morning_safe("Beloved actor dies at 88"))
    _check("killed-it slang stays", is_morning_safe("Singer killed it at the box office"))
    _check("Middlesex title stays", is_morning_safe("Middlesex author optioned for a film"))
    _check("sex tape dropped", not is_morning_safe("Celebrity sex tape leaks online"))
    _check("nude photos dropped", not is_morning_safe("Nude photos of a star hit the web"))
    _check("murder dropped", not is_morning_safe("Actor arrested for murder after party"))
    _check("shooting dropped", not is_morning_safe("Star shot and killed outside a club"))
    _check("short title dropped", not is_morning_safe("Nope"))


def test_selection_and_feeds() -> None:
    fresh = [
        _story("Award show adds a surprise host", published=_dt(12), source_id="tmz"),
        _story("Streaming series renews for another year", published=_dt(11)),
        _story("Festival announces its opening film", published=_dt(10), source_id="tmz"),
        _story("Singer confirms a fall tour", published=_dt(9)),
        _story("Older concert clip resurfaces", published=_dt(8, day=1)),
    ]
    picked = select_entertainment_stories(fresh)
    _check("exactly four when more are safe", len(picked) == 4)
    _check("stale item left out", all(story.title != "Older concert clip resurfaces" for story in picked))
    _check("freshest story leads", picked[0].title.startswith("Award show"))

    with_film = fresh[:4] + [
        _story(
            "Review: the new heist movie sticks the landing",
            summary="Critics call the June release a crowd pleaser.",
            kind="film",
            source_id="variety_film",
            published=_dt(8, day=11),
        )
    ]
    filmed = select_entertainment_stories(with_film)
    _check("still four with a film slot", len(filmed) == 4)
    _check("variety film kept", any(story.kind == "film" for story in filmed))
    _check(
        "oldest general item yields the film slot",
        all(story.title != "Singer confirms a fall tour" for story in filmed),
    )

    short_list = select_entertainment_stories(fresh[:2])
    _check("fewer than four stays short", len(short_list) == 2)

    graphic = _story("Star shot and killed outside a club", published=_dt(15))
    sexual = _story("Celebrity sex tape leaks online", published=_dt(14))
    safe = _story("Family movie tops the weekend chart", published=_dt(13))
    cleaned = select_entertainment_stories([graphic, sexual, safe])
    _check("unsafe stories never selected", cleaned == [safe])

    deadline = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Studio sets a summer release date</title>
    <summary>The film is scheduled for June.</summary>
    <published>2026-10-13T12:00:00Z</published>
    <link href="https://deadline.com/example"/>
  </entry>
  <entry>
    <title>Actor arrested for assault after premiere</title>
    <published>2026-10-13T12:30:00Z</published>
  </entry>
</feed>
"""
    variety = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item>
    <title>Review: midnight comedy is a charmer</title>
    <description>Variety likes the new movie.</description>
    <pubDate>Sun, 12 Oct 2026 15:00:00 GMT</pubDate>
    <link>https://variety.com/film/review</link>
  </item>
</channel></rss>
"""
    tmz = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item>
    <title>Box office: family comedy opens at number one</title>
    <description>The film opened Friday and leads the weekend chart.</description>
    <pubDate>Mon, 13 Oct 2026 11:00:00 GMT</pubDate>
  </item>
  <item>
    <title>Celebrity sex tape leaks online</title>
    <pubDate>Mon, 13 Oct 2026 12:00:00 GMT</pubDate>
  </item>
</channel></rss>
"""
    stories = collect_entertainment_stories(
        {
            DEADLINE_URL: deadline,
            TMZ_URL: tmz,
            VARIETY_URL: RuntimeError("feed down"),
        }
    )
    titles = [story.title for story in stories]
    _check("down variety feed is skipped", "Review: midnight comedy is a charmer" not in titles)
    _check("deadline story kept", "Studio sets a summer release date" in titles)
    _check("tmz story kept", any(title.startswith("Box office") for title in titles))
    _check("assault story dropped", all("assault" not in title.lower() for title in titles))
    _check("sex tape dropped from feed", all("sex tape" not in title.lower() for title in titles))

    variety_only = collect_entertainment_stories(
        {
            DEADLINE_URL: "<not xml",
            TMZ_URL: "",
            VARIETY_URL: variety,
        }
    )
    _check("bad feeds still leave the film review", len(variety_only) == 1)
    spoken = spoken_story(variety_only[0])
    _check("outlet name not spoken", "Variety" not in spoken and "Deadline" not in spoken)
    _check("review title spoken", "midnight comedy" in spoken)


def test_handoff_flow() -> None:
    _check("empty sports close hands to Michael G", sports_close_hands_to_michael("") == DAVE_SPORTS_CLOSE)
    mo_handoff = sports_close_hands_to_michael("Back to you, DJ Mo.")
    _check("Mo handoff replaced", mo_handoff == DAVE_SPORTS_CLOSE)
    _check("replaced close does not return to Mo", "back to you" not in mo_handoff.lower())
    music = sports_close_hands_to_michael("Now back to the music. For Mo's Place Radio, I'm Dave.")
    _check("music close becomes Michael G", "Michael G" in music and "back to the music" not in music.lower())
    kept = sports_close_hands_to_michael("Patriots play Sunday.")
    _check("sports fact kept", kept.startswith("Patriots play Sunday."))
    _check("sports fact hands onward", "Michael G has the entertainment report." in kept)
    already = "That's sports. Michael G is next."
    _check("existing Michael G close kept", sports_close_hands_to_michael(already) == already)

    stories = [
        _story("Award show adds a surprise host", summary="Producers confirmed the booking this morning.", published=_dt(12)),
        _story("Streaming series renews for another year", published=_dt(11)),
        _story("Festival announces its opening film", published=_dt(10)),
        _story("Singer confirms a fall tour", summary="According to Deadline, the tour starts in November.", published=_dt(9)),
    ]
    flow = build_morning_flow(stories, sports_close="Back to you, Mo.")
    _check("order is news, sports, entertainment, thanks", flow["order"] == [
        "news",
        "dave_sports",
        "michael_g_entertainment",
        "mo_thanks",
    ])
    _check("four stories in the package", flow["story_count"] == 4)
    script = flow["script"]
    dave_at = script.index("[Dave]")
    michael_at = script.index("[Michael G]")
    mo_at = script.index("[DJ Mo]")
    _check("speakers run Dave then Michael G then Mo", dave_at < michael_at < mo_at)
    _check("dave does not hand straight to Mo", "Back to you, Mo." not in script.split("[Michael G]")[0])
    _check("michael script thanks Dave", flow["michael_g_script"].startswith("Thanks, Dave."))
    _check("michael hands to DJ Mo", flow["michael_g_script"].strip().endswith("DJ Mo, back to you."))
    _check("mo thanks Michael G", flow["mo_thanks"] == MO_THANKS)
    _check("spoken script has no outlet names", all(name not in flow["michael_g_script"] for name in ("Deadline", "TMZ", "Variety")))
    _check("prompt forbids inventing", "do not invent" in flow["michael_g_prompt"].lower())
    _check("prompt reads exactly four", "exactly these four" in flow["michael_g_prompt"].lower())
    _check("supplied tour fact kept", "November" in flow["michael_g_script"])

    short = build_morning_flow(stories[:2])
    _check("short report does not pad", short["story_count"] == 2)
    _check("short prompt says not to pad", "do not invent stories to reach four" in short["michael_g_prompt"].lower())
    _check("short script has two beats", michael_g_script(stories[:2]).count("\n") == 3)

    empty = build_morning_flow([])
    _check("empty report invents nothing", "Thanks, Dave." in empty["michael_g_script"])
    _check("empty report still hands off", "DJ Mo, back to you." in empty["michael_g_script"])
    _check("empty prompt forbids gossip", "do not invent" in empty["michael_g_prompt"].lower())
    _check("mo still thanks Michael G", empty["mo_thanks"] == "Thanks, Michael G.")


def test_news_rules_upgrade() -> None:
    legacy = {
        "story_order": ["Breaking News", "Local"],
        "maximum_stories": 8,
        "personality_handoffs": True,
        "opening": "This is Mo's Place Radio news.",
        "closing": "For Mo's Place Radio, I'm {personality}.",
        "pronunciation_rules": [],
        "pause_sound_between_stories": "news_bed.mp3",
        "news_first_personality_rules": "Lead anchor opens every newscast.",
        "sports_close": "Back to you, DJ Mo.",
        "stale_hours_warning": 12,
    }
    upgraded = normalize_script_rules(legacy)
    _check("opening preserved", upgraded["opening"] == legacy["opening"])
    _check("news closing preserved", upgraded["closing"] == legacy["closing"])
    _check("story cap preserved", upgraded["maximum_stories"] == 8)
    _check("personality rules mention Michael G", "michael g" in upgraded["news_first_personality_rules"].lower())
    _check("sports close no longer returns to Mo", upgraded["sports_close"] == DAVE_SPORTS_CLOSE)
    _check("four story count", upgraded["entertainment_story_count"] == 4)
    _check("thanks line", upgraded["mo_entertainment_thanks"] == MO_THANKS)
    _check("feeds present", upgraded["entertainment_feeds"] == [source["url"] for source in ENTERTAINMENT_SOURCES])
    again = normalize_script_rules(upgraded)
    _check("rules upgrade is stable", again["entertainment_report_rules"] == upgraded["entertainment_report_rules"])
    _check("personality clause is not duplicated", again["news_first_personality_rules"].lower().count("hands to michael g") == 1)

    defaults = default_script_rules()
    _check("default close hands to Michael G", "Michael G" in defaults["sports_close"])
    _check("default close is not a Mo return", "back to you" not in defaults["sports_close"].lower())

    people = normalize_personalities(
        {
            "personalities": [
                {
                    "id": "dj_mo",
                    "name": "DJ Mo",
                    "role": "anchor",
                    "voice_id": "vb-mo-primary",
                    "enabled": True,
                    "notes": "",
                },
                {
                    "id": "mos_place_dave",
                    "name": "Mo's Place Dave",
                    "role": "anchor",
                    "voice_id": "vb-news-desk",
                    "enabled": True,
                    "notes": "sports",
                },
            ]
        }
    )["personalities"]
    ids = [person["id"] for person in people]
    _check("Michael G inserted after Dave", ids.index("michael_g") == ids.index("mos_place_dave") + 1)
    dave = next(person for person in people if person["id"] == "mos_place_dave")
    michael = next(person for person in people if person["id"] == "michael_g")
    _check("Dave voice unchanged", dave["voice_id"] == "vb-news-desk" and dave["notes"] == "sports")
    _check("Michael G voice record linked", michael["voice_id"] == "vb-michael-g")
    _check("Voicebox profile stored on Michael G", MICHAEL_G_VOICEBOX_PROFILE in michael["notes"])
    _check("profile id stored", MICHAEL_G_VOICEBOX_ID in michael["notes"])

    disabled = normalize_personalities(
        {
            "personalities": [
                {
                    "id": "michael_g",
                    "name": "Michael G",
                    "role": "entertainment",
                    "voice_id": "vb-michael-g",
                    "enabled": False,
                    "notes": MICHAEL_G_VOICEBOX_PROFILE,
                }
            ]
        }
    )["personalities"]
    _check("disabled Michael G stays off", disabled[0]["enabled"] is False)
    _check("no duplicate Michael G", sum(1 for person in disabled if person["name"] == "Michael G") == 1)

    preview = build_dev_script_lines(normalize_bundle({}))
    text = "\n".join(preview)
    _check("preview keeps the news opening", "This is Mo's Place Radio news." in text)
    _check("preview order", text.index("[Dave]") < text.index("[Michael G]") < text.index("[DJ Mo]"))
    _check("preview thanks Michael G", "Thanks, Michael G." in text)
    _check("preview does not invent a headline", "Do not invent stories in this preview." in text)
    _check("preview still signs off", "For Mo's Place Radio, I'm DJ Mo." in text)


def test_config_files() -> None:
    config = ROOT / "config"
    voices = json.loads((config / "voice_library.json").read_text(encoding="utf-8"))
    michael_voice = next(voice for voice in voices["voices"] if voice["display_name"] == "Michael G")
    _check("voicebox id matches the profile", michael_voice["voicebox_id"] == MICHAEL_G_VOICEBOX_ID)
    _check("voice id is the studio record", michael_voice["id"] == "vb-michael-g")
    personalities = json.loads((config / "personalities.json").read_text(encoding="utf-8"))
    michael = next(person for person in personalities["personalities"] if person["display_name"] == "Michael G")
    _check("personality voicebox id", michael["voicebox_voice_id"] == MICHAEL_G_VOICEBOX_ID)
    _check("personality stores the UNC profile", MICHAEL_G_VOICEBOX_PROFILE in michael["bio"])
    mo = next(person for person in personalities["personalities"] if person["id"] == "mo-main")
    _check("Mo thanks Michael G in the personality note", "thank Michael G" in mo["personality_description"])
    news_desk = next(voice for voice in voices["voices"] if voice["id"] == "vb-news-desk")
    _check("news desk hands to Michael G", "hands to Michael G" in news_desk["personality_prompt"])
    mo_voice = next(voice for voice in voices["voices"] if voice["id"] == "vb-mo-primary")
    _check("Mo voice thanks Michael G", "thank Michael G" in mo_voice["personality_prompt"])


def main() -> None:
    test_filters()
    test_selection_and_feeds()
    test_handoff_flow()
    test_news_rules_upgrade()
    test_config_files()
    print("OK: Michael G entertainment report verified")


if __name__ == "__main__":
    main()

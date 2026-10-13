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
    SLOT_DEADLINE,
    SLOT_FILM_NEWS,
    SLOT_REVIEW,
    SLOT_TMZ,
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
VARIETY_NEWS_URL = "https://variety.com/v/film/feed/"
VARIETY_REVIEWS_URL = "https://variety.com/v/film/reviews/feed/"


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
    _check("birthday stays out", not is_morning_safe("Singer turns 40 today"))


def test_selection_and_feeds() -> None:
    graphic = _story("Star shot and killed outside a club", published=_dt(15), source_id="tmz", kind="celebrity")
    sexual = _story("Celebrity sex tape leaks online", published=_dt(14), source_id="tmz", kind="celebrity")
    birthday = _story("Singer turns 40 today", published=_dt(16), source_id="tmz", kind="celebrity")
    box_office = _story(
        "Weekend ticket sales climb again",
        published=_dt(13),
        source_id="tmz",
        kind="celebrity",
    )
    sighting = _story(
        "Singer spotted leaving a downtown diner",
        summary="Fans saw the singer just after midnight.",
        published=_dt(9),
        source_id="tmz",
        kind="celebrity",
    )
    gossip = _story(
        "Famous couple split after the premiere party",
        summary="Friends say the breakup followed a long week of rumors.",
        published=_dt(8),
        source_id="tmz",
        kind="celebrity",
    )
    deadline = _story(
        "Studio renews the drama for two more seasons",
        summary="The series returns in November with the same cast.",
        published=_dt(12),
        source_id="deadline",
        kind="entertainment_news",
    )
    film_review_on_news_feed = _story(
        "Review: midnight comedy is a charmer",
        summary="Critics call the June release a crowd pleaser. The second paragraph keeps going.",
        published=_dt(18),
        source_id="variety_film",
        kind="film_news",
    )
    trailer = _story(
        "Ocean Light trailer",
        summary=(
            "Opens June 12. A lighthouse keeper finds a map at sea. "
            "The third act reveals the map was a painting."
        ),
        published=_dt(7),
        source_id="variety_film",
        kind="film_news",
    )
    memo = _story(
        "Festival posts its volunteer memo",
        summary="Staff should arrive early for badges.",
        published=_dt(17),
        source_id="variety_film",
        kind="film_news",
    )
    review = _story(
        "Ocean Light",
        summary=(
            "The film is a warm adventure. The lead performance carries every scene. "
            "The ending is discussed at length with spoilers and should not be read aloud."
        ),
        published=_dt(6),
        source_id="variety_reviews",
        kind="film_review",
    )
    picked = select_entertainment_stories(
        [graphic, sexual, birthday, box_office, sighting, gossip, deadline, film_review_on_news_feed, trailer, memo, review]
    )
    _check("four slots when every feed has a story", len(picked) == 4)
    _check("slot order is celebrity, news, film news, review", [story.slot for story in picked] == [
        SLOT_TMZ,
        SLOT_DEADLINE,
        SLOT_FILM_NEWS,
        SLOT_REVIEW,
    ])
    _check("slot 1 is the TMZ sighting, not the fresher ticket item", picked[0].source_id == "tmz")
    _check("slot 1 title is the sighting", picked[0].title.startswith("Singer spotted"))
    _check("slot 2 is Deadline", picked[1].source_id == "deadline" and picked[1].title.startswith("Studio renews"))
    _check("slot 3 is the film-news feed", picked[2].source_id == "variety_film" and picked[2].slot == SLOT_FILM_NEWS)
    _check("slot 3 is the trailer, not a review or a memo", picked[2].title == "Ocean Light trailer")
    _check("slot 4 is the reviews feed", picked[3].source_id == "variety_reviews" and picked[3].slot == SLOT_REVIEW)
    _check("news-feed review did not become slot 4", all(story.title.startswith("Review:") is False for story in picked))

    trailer_line = spoken_story(picked[2])
    _check("film news says the title", "Ocean Light trailer" in trailer_line)
    _check("film news says when it arrives", "June 12" in trailer_line)
    _check("film news says what it is", "lighthouse keeper" in trailer_line)
    _check("film news does not read the later sentence", "painting" not in trailer_line)

    review_line = spoken_story(picked[3])
    _check("review says the title", review_line.startswith("Ocean Light"))
    _check("review keeps the first sentence", "warm adventure" in review_line)
    _check("review keeps a second sentence", "lead performance" in review_line)
    _check("review does not read the rest", "spoilers" not in review_line)
    _check("outlet names stay off the read", all(name not in trailer_line + review_line for name in ("Deadline", "TMZ", "Variety")))

    without_deadline = select_entertainment_stories(
        [sighting, gossip, trailer, review, graphic, sexual]
    )
    _check("deadline gap uses a second TMZ item", [story.slot for story in without_deadline] == [
        SLOT_TMZ,
        SLOT_DEADLINE,
        SLOT_FILM_NEWS,
        SLOT_REVIEW,
    ])
    _check("fallback slot stays a TMZ story", without_deadline[1].source_id == "tmz")
    _check("fallback is not the same celebrity item", without_deadline[1].title != without_deadline[0].title)

    reviews_down = select_entertainment_stories([sighting, deadline, trailer, film_review_on_news_feed])
    _check("missing reviews feed skips slot 4", [story.slot for story in reviews_down] == [
        SLOT_TMZ,
        SLOT_DEADLINE,
        SLOT_FILM_NEWS,
    ])
    _check("film news is not rewritten as a review", all(story.slot != SLOT_REVIEW for story in reviews_down))

    film_down = select_entertainment_stories([sighting, deadline, review])
    _check("missing film-news feed skips slot 3", [story.slot for story in film_down] == [
        SLOT_TMZ,
        SLOT_DEADLINE,
        SLOT_REVIEW,
    ])

    deadline_xml = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Studio sets a summer release date</title>
    <summary>The series returns in November.</summary>
    <published>2026-10-13T12:00:00Z</published>
    <link href="https://deadline.com/example"/>
  </entry>
  <entry>
    <title>Actor arrested for assault after premiere</title>
    <published>2026-10-13T12:30:00Z</published>
  </entry>
</feed>
"""
    film_news_xml = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item>
    <title>Review: midnight comedy is a charmer</title>
    <description>Critics liked the new movie.</description>
    <pubDate>Mon, 13 Oct 2026 18:00:00 GMT</pubDate>
  </item>
  <item>
    <title>Ocean Light trailer</title>
    <description>Opens June 12. A lighthouse keeper finds a map at sea. The third act reveals the map was a painting.</description>
    <pubDate>Sun, 12 Oct 2026 15:00:00 GMT</pubDate>
    <link>https://variety.com/v/film/ocean-light</link>
  </item>
</channel></rss>
"""
    reviews_xml = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item>
    <title>Ocean Light</title>
    <description>The film is a warm adventure. The lead performance carries every scene. The ending is discussed at length with spoilers and should not be read aloud.</description>
    <pubDate>Sat, 11 Oct 2026 15:00:00 GMT</pubDate>
    <link>https://variety.com/v/film/reviews/ocean-light</link>
  </item>
</channel></rss>
"""
    tmz_xml = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item>
    <title>Weekend ticket sales climb again</title>
    <description>The family comedy led the chart.</description>
    <pubDate>Mon, 13 Oct 2026 13:00:00 GMT</pubDate>
  </item>
  <item>
    <title>Singer spotted leaving a downtown diner</title>
    <description>Fans saw the singer just after midnight.</description>
    <pubDate>Mon, 13 Oct 2026 09:00:00 GMT</pubDate>
  </item>
  <item>
    <title>Famous couple split after the premiere party</title>
    <description>Friends say the breakup followed a long week of rumors.</description>
    <pubDate>Mon, 13 Oct 2026 08:00:00 GMT</pubDate>
  </item>
  <item>
    <title>Celebrity sex tape leaks online</title>
    <pubDate>Mon, 13 Oct 2026 14:00:00 GMT</pubDate>
  </item>
  <item>
    <title>Singer turns 40 today</title>
    <pubDate>Mon, 13 Oct 2026 15:00:00 GMT</pubDate>
  </item>
</channel></rss>
"""
    from_feeds = collect_entertainment_stories(
        {
            TMZ_URL: tmz_xml,
            DEADLINE_URL: deadline_xml,
            VARIETY_NEWS_URL: film_news_xml,
            VARIETY_REVIEWS_URL: reviews_xml,
        }
    )
    _check("fixtures keep the four-slot order", [story.slot for story in from_feeds] == [
        SLOT_TMZ,
        SLOT_DEADLINE,
        SLOT_FILM_NEWS,
        SLOT_REVIEW,
    ])
    _check("fixture slot 3 is film news", from_feeds[2].source_id == "variety_film")
    _check("fixture slot 4 is the reviews feed", from_feeds[3].source_id == "variety_reviews")
    _check("fixture slot 3 title is the trailer", from_feeds[2].title == "Ocean Light trailer")
    _check("fixture slot 4 title is the review", from_feeds[3].title == "Ocean Light")
    _check("assault story dropped", all("assault" not in story.title.lower() for story in from_feeds))
    _check("sex tape dropped from feed", all("sex tape" not in story.title.lower() for story in from_feeds))
    _check("birthday dropped from feed", all("turns 40" not in story.title.lower() for story in from_feeds))

    reviews_feed_down = collect_entertainment_stories(
        {
            TMZ_URL: tmz_xml,
            DEADLINE_URL: deadline_xml,
            VARIETY_NEWS_URL: film_news_xml,
            VARIETY_REVIEWS_URL: RuntimeError("feed down"),
        }
    )
    _check("down reviews feed skips slot 4", SLOT_REVIEW not in [story.slot for story in reviews_feed_down])
    _check("down reviews feed still reads the trailer", any(story.slot == SLOT_FILM_NEWS for story in reviews_feed_down))
    _check(
        "film news is not used as the review",
        all(story.source_id != "variety_reviews" for story in reviews_feed_down),
    )

    deadline_down = collect_entertainment_stories(
        {
            TMZ_URL: tmz_xml,
            DEADLINE_URL: RuntimeError("feed down"),
            VARIETY_NEWS_URL: film_news_xml,
            VARIETY_REVIEWS_URL: reviews_xml,
        }
    )
    _check("deadline down keeps the other slots", [story.slot for story in deadline_down] == [
        SLOT_TMZ,
        SLOT_DEADLINE,
        SLOT_FILM_NEWS,
        SLOT_REVIEW,
    ])
    _check("deadline down uses a second TMZ item", deadline_down[1].source_id == "tmz")
    _check("deadline down does not invent a Deadline story", "summer release" not in deadline_down[1].title.lower())
    _check("second TMZ item is not the first celebrity story", deadline_down[1].title != deadline_down[0].title)


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
        _story(
            "Singer spotted leaving a downtown diner",
            summary="Fans saw the singer just after midnight.",
            source_id="tmz",
            kind="celebrity",
            published=_dt(9),
        ),
        _story(
            "Studio renews the drama for two more seasons",
            summary="The series returns in November.",
            source_id="deadline",
            kind="entertainment_news",
            published=_dt(11),
        ),
        _story(
            "Ocean Light trailer",
            summary="Opens June 12. A lighthouse keeper finds a map at sea.",
            source_id="variety_film",
            kind="film_news",
            published=_dt(10),
        ),
        _story(
            "Ocean Light",
            summary="The film is a warm adventure. The lead performance carries every scene.",
            source_id="variety_reviews",
            kind="film_review",
            published=_dt(8),
        ),
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
    _check("rules name the reviews slot", "variety reviews" in upgraded["entertainment_report_rules"].lower())
    _check("rules refuse an invented review", "do not invent a review" in upgraded["entertainment_report_rules"].lower())
    legacy_rules = normalize_script_rules(
        {
            "entertainment_report_rules": (
                "Michael G reads the entertainment report after Dave's sports. "
                "Use only the supplied stories. Read four when four usable stories are supplied; "
                "if fewer are supplied, read only those and do not invent gossip, quotes, or extra stories. "
                "Deadline and TMZ items are general entertainment. Variety film items are new movies and reviews. "
                "Skip graphic crime, sexual content, and anything that does not fit a morning music-radio show. "
                "Do not name the outlets on the air. "
                "Thank Dave, then read the stories in short conversational beats, then hand the show to DJ Mo. "
                "DJ Mo's next line thanks Michael G by name."
            )
        }
    )
    _check("old movie-and-review wording upgrades", "variety reviews" in legacy_rules["entertainment_report_rules"].lower())
    _check(
        "old wording no longer treats film news as the review",
        "new movies and reviews" not in legacy_rules["entertainment_report_rules"].lower(),
    )
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

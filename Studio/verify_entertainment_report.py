"""Offline checks for Michael G's morning entertainment report."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from app.core.entertainment_report import (  # noqa: E402
    DAVE_SPORTS_CLOSE,
    DEFAULT_ENTERTAINMENT_REPORT_RULES,
    ENTERTAINMENT_SOURCES,
    MICHAEL_BEAT,
    MICHAEL_G_BIO,
    MICHAEL_G_VOICEBOX_ID,
    MICHAEL_G_VOICEBOX_PROFILE,
    MICHAEL_STRAIGHT_OPEN,
    MO_THANKS,
    EntertainmentStory,
    build_morning_flow,
    collect_entertainment_stories,
    is_morning_safe,
    michael_g_script,
    SLOT_DEADLINE,
    SLOT_EXTRA,
    SLOT_FILM_NEWS,
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
RETIRED_REVIEWS_URL = "https://variety.com/v/film/reviews/feed/"

MOVIE_SUMMARY = (
    "Opens June 12. A lighthouse keeper finds a map at sea. "
    "Familiar themes of courage show up along the way. "
    "A later paragraph about the score should stay off the air."
)
MOVIE_LINE = (
    "In movie news, Ocean Light fans, get ready! "
    "It hits theaters June 12. "
    "A lighthouse keeper finds a map at sea. "
    "Familiar themes of courage show up along the way. "
    "Get ready for this one."
)

_REVIEW_WORD_RE = re.compile(r"(?i)\breviews?\b")
_CRITICS_RE = re.compile(r"(?i)critics?\s+say|critics?\s+said|critic\s+says")
_RATING_RE = re.compile(
    r"(?i)star rating|\b\d(?:\.\d)?\s*(?:out of|/)\s*5\b|"
    r"\b(?:\d+(?:\.\d+)?|one|two|three|four|five)\s+stars?\b|★"
)


def _check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)


def _assert_no_review_language(text: str) -> None:
    _check("spoken line does not say review", _REVIEW_WORD_RE.search(text) is None)
    _check("spoken line does not say critics say", _CRITICS_RE.search(text) is None)
    _check("spoken line has no star rating", _RATING_RE.search(text) is None)


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
    _check("safety filter allows a review headline", is_morning_safe("Review: midnight comedy is a charmer"))
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
    urls = [source["url"] for source in ENTERTAINMENT_SOURCES]
    _check("three feeds", urls == [TMZ_URL, DEADLINE_URL, VARIETY_NEWS_URL])
    _check("reviews feed is not a source", RETIRED_REVIEWS_URL not in urls)
    _check("no reviews path in the source list", all("variety.com/v/film/reviews" not in url for url in urls))
    module_source = (ROOT / "app/core/entertainment_report.py").read_text(encoding="utf-8")
    _check("movie slot is not a hard-coded Star Wars script", "star wars" not in module_source.lower())
    _check("module does not fetch the reviews feed", RETIRED_REVIEWS_URL not in module_source)

    graphic = _story("Star shot and killed outside a club", published=_dt(15), source_id="tmz", kind="celebrity")
    sexual = _story("Celebrity sex tape leaks online", published=_dt(14), source_id="tmz", kind="celebrity")
    birthday = _story("Singer turns 40 today", published=_dt(16), source_id="tmz", kind="celebrity")
    box_office = _story(
        "Weekend ticket sales climb again",
        summary="The family comedy led the chart.",
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
        summary="Critics say the June release is a crowd pleaser. The second paragraph keeps going.",
        published=_dt(18),
        source_id="variety_film",
        kind="film_news",
    )
    trailer = _story(
        "Ocean Light trailer",
        summary=MOVIE_SUMMARY,
        published=_dt(7),
        source_id="variety_film",
        kind="film_news",
    )
    spec_deal = _story(
        "Black Bear Acquires Love Triangle Comedy Spec From Writing Duo Cassidy Alla and Read Masino (EXCLUSIVE)",
        summary=(
            "Black Bear has acquired the rights to a comedy spec script, Variety can reveal exclusively. "
            'According to an official logline, the untitled film "tells the story of a family mix-up."'
        ),
        published=_dt(21),
        source_id="variety_film",
        kind="film_news",
    )
    writers_lab = _story(
        "The Black List Names 2026 Writers Lab Participants",
        summary="EXCLUSIVE: The Black List has named the six writers chosen for its writers lab.",
        published=_dt(19),
        source_id="deadline",
        kind="entertainment_news",
    )
    cast_list = _story(
        "Callan Farris, Lexi Minetree and Josh Macqueen Round Out Cast Of Sony Comedy 'Narcs'",
        summary=(
            "EXCLUSIVE: Sony Pictures has rounded out the cast for its comedy, with "
            "Callan Farris (Grimcutty) and Lexi Minetree (Elle)."
        ),
        published=_dt(18),
        source_id="deadline",
        kind="entertainment_news",
    )
    memo = _story(
        "Festival posts its volunteer memo",
        summary="Staff should arrive early for badges.",
        published=_dt(17),
        source_id="variety_film",
        kind="film_news",
    )
    retired_review = _story(
        "Ocean Light",
        summary=(
            "The film is a warm adventure. Critics say the lead performance carries every scene. "
            "It earns 4 out of 5 stars."
        ),
        published=_dt(6),
        source_id="variety_reviews",
        kind="film_review",
    )
    picked = select_entertainment_stories(
        [
            graphic,
            sexual,
            birthday,
            box_office,
            sighting,
            gossip,
            deadline,
            film_review_on_news_feed,
            trailer,
            spec_deal,
            writers_lab,
            cast_list,
            memo,
            retired_review,
        ]
    )
    _check("four slots when every feed has a story", len(picked) == 4)
    _check(
        "slot order is celebrity, news, movie news, one more entertainment item",
        [story.slot for story in picked] == [SLOT_TMZ, SLOT_DEADLINE, SLOT_FILM_NEWS, SLOT_EXTRA],
    )
    _check("slot 1 is the TMZ sighting, not the fresher ticket item", picked[0].source_id == "tmz")
    _check("slot 1 title is the sighting", picked[0].title.startswith("Singer spotted"))
    _check("slot 2 is Deadline", picked[1].source_id == "deadline" and picked[1].title.startswith("Studio renews"))
    _check("slot 3 is the film-news feed", picked[2].source_id == "variety_film" and picked[2].slot == SLOT_FILM_NEWS)
    _check("slot 3 is the trailer, not a review headline or a memo", picked[2].title == "Ocean Light trailer")
    _check("slot 4 is another TMZ or Deadline item", picked[3].source_id in {"tmz", "deadline"} and picked[3].slot == SLOT_EXTRA)
    _check("slot 4 is the freshest leftover entertainment item", picked[3].title == "Weekend ticket sales climb again")
    _check("a review headline did not air", all(not story.title.startswith("Review:") for story in picked))
    _check("retired review story did not air", all(story.source_id != "variety_reviews" for story in picked))
    _check("volunteer memo did not take a slot", all("volunteer" not in story.title.lower() for story in picked))
    _check("spec-script sale did not air", all("comedy spec" not in story.title.lower() for story in picked))
    _check("writers lab did not air", all("writers lab" not in story.title.lower() for story in picked))
    _check("cast laundry list did not air", all("round out cast" not in story.title.lower() for story in picked))
    spec_line = spoken_story(spec_deal)
    _check("spec deal is not spoken", spec_line == "")
    _check("spec headline is not the movie name", "fans, get ready" not in spec_line.lower())
    _check("spec headline is not read aloud", "Black Bear Acquires" not in spec_line)
    cast_line = spoken_story(cast_list)
    _check("cast list is not spoken", cast_line == "")
    _check("cast list does not say exclusive", "exclusive" not in cast_line.lower())
    _check("cast list does not read parenthetical credits", "Grimcutty" not in cast_line)
    _check("cast list does not paste the headline", "Round Out Cast" not in cast_line)
    lab_line = spoken_story(writers_lab)
    _check("writers lab is not spoken", lab_line == "")

    dolly = spoken_story(
        _story(
            "Dolly Parton's Former Solvang Cottage Sells for $2 Million",
            summary=(
                "The Solvang cottage that once belonged to Dolly Parton is officially off the market, "
                "TMZ has learned."
            ),
            source_id="tmz",
            kind="celebrity",
        )
    )
    _check(
        "cottage sale is one plain sentence",
        dolly == "The Solvang cottage that once belonged to Dolly Parton is officially off the market.",
    )
    _check("cottage sale does not read the raw headline", "Former Solvang Cottage Sells" not in dolly)
    _check("cottage sale does not name the outlet", "TMZ" not in dolly)
    dolly_bad_blurb = spoken_story(
        _story(
            "Dolly Parton's Former Solvang Cottage Sells for $2 Million",
            summary=(
                "The Solvang cottage that once belonged to Dolly Parton is officially off the market. "
                "The late legend's former retreat sold this month for $1,945,150, "
                "weeks after the singer's late August death."
            ),
            source_id="tmz",
            kind="celebrity",
        )
    )
    _check(
        "a sale blurb cannot add a death the headline never reported",
        dolly_bad_blurb == "The Solvang cottage that once belonged to Dolly Parton is officially off the market.",
    )
    _check("sale blurb does not say the late", "late" not in dolly_bad_blurb.lower())
    _check("sale blurb does not say death", "death" not in dolly_bad_blurb.lower())

    sighting_line = spoken_story(sighting)
    _check(
        "sighting is the blurb, not the headline plus the lede",
        sighting_line == "Fans saw the singer just after midnight.",
    )
    _check("sighting does not repeat the headline", "Singer spotted" not in sighting_line)
    deadline_line = spoken_story(deadline)
    _check(
        "deadline item is one sentence, not the headline plus the lede",
        deadline_line == "The series returns in November with the same cast.",
    )
    _check("deadline item does not say exclusive", "exclusive" not in deadline_line.lower())
    _check("deadline item does not say according to", "according to" not in deadline_line.lower())

    trailer_line = spoken_story(picked[2])
    _check("movie slot matches the fixture sentence", trailer_line == MOVIE_LINE)
    _check("movie slot starts with In movie news", trailer_line.startswith("In movie news,"))
    _check("movie slot names the movie", "Ocean Light fans, get ready!" in trailer_line)
    _check("movie slot uses the supplied date", "June 12" in trailer_line)
    _check("movie slot uses the supplied story", "lighthouse keeper" in trailer_line)
    _check("movie slot keeps a second blurb sentence", "themes of courage" in trailer_line)
    _check("movie slot leaves the later paragraph off the air", "score" not in trailer_line.lower())
    _check("movie slot does not invent this Friday", "friday" not in trailer_line.lower())
    _assert_no_review_language(trailer_line)
    _check("outlet names stay off the movie read", all(name not in trailer_line for name in ("Deadline", "TMZ", "Variety")))

    no_date = spoken_story(
        _story(
            "Harbor Road trailer",
            summary="A ferry captain follows a letter home. The crew stays together.",
            source_id="variety_film",
            kind="film_news",
        )
    )
    _check(
        "movie slot without a date does not invent a theater day",
        no_date
        == (
            "In movie news, Harbor Road fans, get ready! "
            "A ferry captain follows a letter home. "
            "The crew stays together. "
            "Get ready for this one."
        ),
    )
    _check("undated movie does not say Friday", "friday" not in no_date.lower())
    _check("undated movie does not say hits theaters", "hits theaters" not in no_date.lower())

    dated = spoken_story(
        _story(
            "North Wind trailer",
            summary=(
                "Opens this Friday. Critics say the show is a triumph. "
                "A drummer leaves home. It earns 4 out of 5 stars. "
                "The band stays on the road."
            ),
            source_id="variety_film",
            kind="film_news",
        )
    )
    _check(
        "movie slot says this Friday only because the item says it",
        dated
        == (
            "In movie news, North Wind fans, get ready! "
            "It hits theaters this Friday. "
            "A drummer leaves home. "
            "The band stays on the road. "
            "Get ready for this one."
        ),
    )
    _assert_no_review_language(dated)

    preview_line = spoken_story(
        _story(
            "Lantern preview",
            summary="The preview shows a lighthouse. Critics say it shines.",
            source_id="variety_film",
            kind="film_news",
        )
    )
    _check("preview is not treated as a review", "preview" in preview_line.lower())
    _assert_no_review_language(preview_line)
    _check("critics sentence stays off the preview read", "shines" not in preview_line.lower())
    _check("preview without a film title does not say fans get ready", "fans, get ready" not in preview_line.lower())

    named_movie = _story(
        "Parker Posey to Star in 'Sleepover'",
        summary=(
            "Parker Posey will star in the upcoming horror movie. "
            "The film hits theaters on Oct. 8, 2027."
        ),
        published=_dt(4),
        source_id="variety_film",
        kind="film_news",
    )
    named_only = select_entertainment_stories([sighting, deadline, spec_deal, named_movie])
    _check(
        "a titled movie beats a newer spec deal",
        [story.slot for story in named_only] == [SLOT_TMZ, SLOT_DEADLINE, SLOT_FILM_NEWS],
    )
    _check("movie slot uses the titled film, not the spec", named_only[2].title.startswith("Parker Posey"))
    named_line = spoken_story(named_only[2])
    _check(
        "titled movie uses the film title",
        named_line.startswith("In movie news, Sleepover fans, get ready!"),
    )
    _check("titled movie keeps the supplied theater date", "Oct. 8, 2027" in named_line)
    _check("titled movie does not invent Friday", "friday" not in named_line.lower())
    _check("titled movie does not read the acquisition headline", "Black Bear" not in named_line)
    _assert_no_review_language(named_line)

    screening = spoken_story(
        _story(
            "Director attends a fest for 'Once Upon a Time in Hollywood'",
            summary="The screening takes place on Friday, Oct. 23. He will talk about the movie.",
            source_id="variety_film",
            kind="film_news",
        )
    )
    _check("a screening date is not turned into a theater day", "hits theaters" not in screening.lower())
    _check("screening still names the movie", "Once Upon a Time in Hollywood fans, get ready!" in screening)

    deals_only = select_entertainment_stories([sighting, deadline, spec_deal, writers_lab, cast_list])
    _check(
        "deals and labs skip the movie slot",
        [story.slot for story in deals_only] == [SLOT_TMZ, SLOT_DEADLINE],
    )

    without_deadline = select_entertainment_stories(
        [sighting, gossip, box_office, trailer, retired_review, graphic, sexual]
    )
    _check(
        "deadline gap uses a second TMZ item and still fills slot 4",
        [story.slot for story in without_deadline] == [SLOT_TMZ, SLOT_DEADLINE, SLOT_FILM_NEWS, SLOT_EXTRA],
    )
    _check("fallback slot stays a TMZ story", without_deadline[1].source_id == "tmz")
    _check("fallback is not the same celebrity item", without_deadline[1].title != without_deadline[0].title)
    _check("slot 4 after a deadline gap is still TMZ or Deadline", without_deadline[3].source_id in {"tmz", "deadline"})
    _check("a retired review does not fill the deadline gap", "warm adventure" not in spoken_story(without_deadline[3]))

    no_extra = select_entertainment_stories([sighting, deadline, trailer, retired_review, film_review_on_news_feed])
    _check(
        "a review does not fill slot 4",
        [story.slot for story in no_extra] == [SLOT_TMZ, SLOT_DEADLINE, SLOT_FILM_NEWS],
    )

    second_deadline = _story(
        "Network orders a holiday special",
        summary="The special airs in December.",
        published=_dt(6),
        source_id="deadline",
        kind="entertainment_news",
    )
    deadline_extra = select_entertainment_stories([sighting, deadline, second_deadline, trailer])
    _check(
        "second Deadline item can take slot 4",
        [story.slot for story in deadline_extra] == [SLOT_TMZ, SLOT_DEADLINE, SLOT_FILM_NEWS, SLOT_EXTRA],
    )
    _check("slot 4 can be Deadline", deadline_extra[3].source_id == "deadline")
    _check("slot 4 is not the Deadline item already used", deadline_extra[3].title != deadline_extra[1].title)

    film_down = select_entertainment_stories([sighting, deadline, retired_review])
    _check(
        "missing film-news feed skips the movie slot",
        [story.slot for story in film_down] == [SLOT_TMZ, SLOT_DEADLINE],
    )
    _check("a review does not become the movie slot", all(story.slot != SLOT_FILM_NEWS for story in film_down))

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
    <description>Critics say the new movie is a crowd pleaser.</description>
    <pubDate>Mon, 13 Oct 2026 18:00:00 GMT</pubDate>
  </item>
  <item>
    <title>Ocean Light trailer</title>
    <description>Opens June 12. A lighthouse keeper finds a map at sea. Familiar themes of courage show up along the way. A later paragraph about the score should stay off the air.</description>
    <pubDate>Sun, 12 Oct 2026 15:00:00 GMT</pubDate>
    <link>https://variety.com/v/film/ocean-light</link>
  </item>
</channel></rss>
"""
    reviews_xml = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item>
    <title>Ocean Light</title>
    <description>The film is a warm adventure. Critics say the lead performance carries every scene. It earns 4 out of 5 stars.</description>
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
            RETIRED_REVIEWS_URL: reviews_xml,
        }
    )
    _check(
        "fixtures keep the four-slot order",
        [story.slot for story in from_feeds] == [SLOT_TMZ, SLOT_DEADLINE, SLOT_FILM_NEWS, SLOT_EXTRA],
    )
    _check("fixture slot 3 is film news", from_feeds[2].source_id == "variety_film")
    _check("fixture slot 3 title is the trailer", from_feeds[2].title == "Ocean Light trailer")
    _check("fixture movie sentence", spoken_story(from_feeds[2]) == MOVIE_LINE)
    _check("fixture slot 4 is TMZ or Deadline", from_feeds[3].source_id in {"tmz", "deadline"})
    _check("fixture slot 4 is not the retired review", from_feeds[3].title != "Ocean Light")
    _check("reviews xml is ignored", all(story.source_id != "variety_reviews" for story in from_feeds))
    _check("warm-adventure review stays off the air", all("warm adventure" not in story.summary.lower() for story in from_feeds))
    _check("assault story dropped", all("assault" not in story.title.lower() for story in from_feeds))
    _check("sex tape dropped from feed", all("sex tape" not in story.title.lower() for story in from_feeds))
    _check("birthday dropped from feed", all("turns 40" not in story.title.lower() for story in from_feeds))
    _assert_no_review_language("\n".join(spoken_story(story) for story in from_feeds))

    deadline_down = collect_entertainment_stories(
        {
            TMZ_URL: tmz_xml,
            DEADLINE_URL: RuntimeError("feed down"),
            VARIETY_NEWS_URL: film_news_xml,
            RETIRED_REVIEWS_URL: reviews_xml,
        }
    )
    _check(
        "deadline down keeps four slots from TMZ and film news",
        [story.slot for story in deadline_down] == [SLOT_TMZ, SLOT_DEADLINE, SLOT_FILM_NEWS, SLOT_EXTRA],
    )
    _check("deadline down uses a second TMZ item", deadline_down[1].source_id == "tmz")
    _check("deadline down does not invent a Deadline story", "summer release" not in deadline_down[1].title.lower())
    _check("second TMZ item is not the first celebrity story", deadline_down[1].title != deadline_down[0].title)
    _check("deadline down does not air the reviews feed", all(story.source_id != "variety_reviews" for story in deadline_down))


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
            summary=MOVIE_SUMMARY,
            source_id="variety_film",
            kind="film_news",
            published=_dt(10),
        ),
        _story(
            "Weekend ticket sales climb again",
            summary="The family comedy led the chart.",
            source_id="tmz",
            kind="celebrity",
            published=_dt(13),
        ),
        _story(
            "Ocean Light",
            summary="The film is a warm adventure. Critics say it earns 4 out of 5 stars.",
            source_id="variety_reviews",
            kind="film_review",
            published=_dt(8),
        ),
    ]
    flow = build_morning_flow(stories, sports_close="Back to you, Mo.")
    _check(
        "order is news, sports, entertainment, thanks",
        flow["order"] == ["news", "dave_sports", "michael_g_entertainment", "mo_thanks"],
    )
    _check("four stories in the package", flow["story_count"] == 4)
    script = flow["script"]
    dave_at = script.index("[Dave]")
    michael_at = script.index("[Michael G]")
    mo_at = script.index("[DJ Mo]")
    _check("speakers run Dave then Michael G then Mo", dave_at < michael_at < mo_at)
    _check("dave does not hand straight to Mo", "Back to you, Mo." not in script.split("[Michael G]")[0])
    _check("dave close is the entertainment handoff", DAVE_SPORTS_CLOSE in script)
    _check("michael script thanks Dave", flow["michael_g_script"].startswith("Thanks, Dave."))
    normal_lines = flow["michael_g_script"].splitlines()
    _check("normal-day open is straight plus one beat", normal_lines[0] == MICHAEL_STRAIGHT_OPEN)
    _check("normal-day open adds one conversational beat", normal_lines[1] == MICHAEL_BEAT)
    _check(
        "fallback beat sounds like coffee and classic rock",
        "coffee" in MICHAEL_BEAT.lower() and "classic rock" in MICHAEL_BEAT.lower(),
    )
    _check(
        "fallback beat is not the dog chair gag",
        "good chair" not in MICHAEL_BEAT.lower() and "dog" not in MICHAEL_BEAT.lower(),
    )
    _check("normal-day beat is one sentence", MICHAEL_BEAT.endswith(".") and MICHAEL_BEAT.count(".") == 1)
    _check("normal-day script uses that beat once", flow["michael_g_script"].count(MICHAEL_BEAT) == 1)
    _check("normal-day script does not read the biography", "Roger Williams" not in flow["michael_g_script"])
    _check("normal-day script does not say Mike Gleason", "Mike Gleason" not in flow["michael_g_script"])
    _check(
        "normal-day script does not read the bio coffee line",
        "sub genres" not in flow["michael_g_script"].lower()
        and "golden age" not in flow["michael_g_script"].lower(),
    )
    _check("normal-day script has no popcorn joke", "popcorn" not in flow["michael_g_script"].lower())
    _check(
        "normal-day prompt asks for one conversational beat",
        "coffee or classic rock" in flow["michael_g_prompt"].lower()
        and "not a disconnected gag" in flow["michael_g_prompt"].lower()
        and "not the same sentence every day" in flow["michael_g_prompt"].lower(),
    )
    _check(
        "normal-day prompt does not force today's open straight",
        "a supplied story is a death, obituary, or mourning item" not in flow["michael_g_prompt"].lower(),
    )
    _check("michael hands to DJ Mo", flow["michael_g_script"].strip().endswith("DJ Mo, back to you."))
    _check("mo thanks Michael G", flow["mo_thanks"] == MO_THANKS)
    _check("script thanks Michael G", script.strip().endswith("Thanks, Michael G."))
    _check("spoken script has no outlet names", all(name not in flow["michael_g_script"] for name in ("Deadline", "TMZ", "Variety")))
    _check("prompt forbids inventing", "do not invent" in flow["michael_g_prompt"].lower())
    _check("prompt reads exactly four", "exactly these four" in flow["michael_g_prompt"].lower())
    _check(
        "prompt introduces the entertainment report",
        "michael g here with the entertainment report" in flow["michael_g_prompt"].lower(),
    )
    _check("prompt is not sarcastic about death", "not sarcastic about death" in flow["michael_g_prompt"].lower())
    _check("supplied tour fact kept", "November" in flow["michael_g_script"])
    _check("movie fixture is in the spoken script", MOVIE_LINE in flow["michael_g_script"])
    _check("retired review stays out of the spoken script", "warm adventure" not in flow["michael_g_script"])
    _assert_no_review_language(flow["michael_g_script"])

    short = build_morning_flow(stories[:2])
    _check("short report does not pad", short["story_count"] == 2)
    _check("short prompt says not to pad", "do not invent stories to reach four" in short["michael_g_prompt"].lower())
    _check("short script has two beats", michael_g_script(stories[:2]).count("\n") == 4)

    empty = build_morning_flow([])
    _check("empty report invents nothing", "Thanks, Dave." in empty["michael_g_script"])
    _check("empty report still introduces Michael", MICHAEL_STRAIGHT_OPEN in empty["michael_g_script"])
    _check("empty report keeps the conversational beat", empty["michael_g_script"].splitlines()[1] == MICHAEL_BEAT)
    _check("empty report still hands off", "DJ Mo, back to you." in empty["michael_g_script"])
    _check("empty prompt forbids gossip", "do not invent" in empty["michael_g_prompt"].lower())
    _check("mo still thanks Michael G", empty["mo_thanks"] == "Thanks, Michael G.")

    death = _story(
        "Beloved actor dies at 88",
        summary="The actor died Thursday.",
        source_id="tmz",
        kind="celebrity",
    )
    death_script = michael_g_script([death])
    death_lines = death_script.splitlines()
    _check(
        "death-day open is exact",
        death_lines[0] == "Thanks, Dave. Michael G here with the entertainment report.",
    )
    _check("death-day open matches the straight line", death_lines[0] == MICHAEL_STRAIGHT_OPEN)
    _check("death-day open has no joke after it", death_lines[1] != MICHAEL_BEAT)
    _check("death-day open is only the straight line", len(death_lines[0]) == len(MICHAEL_STRAIGHT_OPEN))
    death_stories = death_lines[1:-1]
    _check("death story is still read", any("died" in line.lower() for line in death_stories))
    _check(
        "death story stays respectful",
        death_stories
        and all(
            MICHAEL_BEAT not in line
            and "popcorn" not in line.lower()
            and "grandkids" not in line.lower()
            and "coffee" not in line.lower()
            and "classic rock" not in line.lower()
            for line in death_stories
        ),
    )
    _check("death-day script has no comical beat", MICHAEL_BEAT not in death_script)
    _check("death-day script has no popcorn joke", "popcorn" not in death_script.lower())
    _check("death-day script has no coffee", "coffee" not in death_script.lower())
    _check("death-day script has no classic rock", "classic rock" not in death_script.lower())
    _check("death-day open has no coffee", "coffee" not in death_lines[0].lower())
    _check("death-day open has no rock", "rock" not in death_lines[0].lower())
    _check("death-day open has no grandkids joke", "grandkids" not in death_lines[0].lower())
    _check("death-day open has no dog joke", "dog" not in death_lines[0].lower())
    _check("death-day open has no husband joke", "husband" not in death_lines[0].lower())
    _check("death-day open has no popcorn joke", "popcorn" not in death_lines[0].lower())
    _check("spoken death story has no comical beat", MICHAEL_BEAT not in spoken_story(death))
    _check("spoken death story stays respectful", spoken_story(death) == "The actor died Thursday.")

    mixed = michael_g_script(
        [
            _story(
                "Singer spotted leaving a downtown diner",
                summary="Fans saw the singer just after midnight.",
                source_id="tmz",
                kind="celebrity",
            ),
            death,
            _story(
                "Ocean Light trailer",
                summary=MOVIE_SUMMARY,
                source_id="variety_film",
                kind="film_news",
            ),
            _story(
                "Weekend ticket sales climb again",
                summary="The family comedy led the chart.",
                source_id="tmz",
                kind="celebrity",
            ),
        ]
    )
    _check("a death in any slot straightens the whole open", mixed.splitlines()[0] == MICHAEL_STRAIGHT_OPEN)
    _check(
        "a death day open has no coffee or rock",
        "coffee" not in mixed.splitlines()[0].lower() and "rock" not in mixed.splitlines()[0].lower(),
    )
    _check("a death day does not keep the conversational beat", MICHAEL_BEAT not in mixed and "popcorn" not in mixed.lower())
    _check("a death day still reads the other stories", "Ocean Light" in mixed and "family comedy" in mixed)
    _check("a death day still reads the death", "died" in mixed.lower())

    mourning = michael_g_script(
        [
            _story(
                "Hollywood mourns a beloved singer",
                summary="Friends shared quiet tributes.",
                source_id="tmz",
                kind="celebrity",
            )
        ]
    )
    _check("a mourning item straightens the open", mourning.splitlines()[0] == MICHAEL_STRAIGHT_OPEN)
    _check("a mourning day has no conversational beat", MICHAEL_BEAT not in mourning)
    _check("a mourning day has no coffee or rock", "coffee" not in mourning.lower() and "classic rock" not in mourning.lower())

    obituary = michael_g_script(
        [
            _story(
                "Obituary: the comic who made Tuesday nights",
                summary="He died Sunday at home.",
                source_id="tmz",
                kind="celebrity",
            )
        ]
    )
    _check("an obituary straightens the open", obituary.splitlines()[0] == MICHAEL_STRAIGHT_OPEN)
    _check("an obituary is still read", "died" in obituary.lower())

    killed_it = michael_g_script(
        [
            _story(
                "Singer killed it at the box office",
                summary="The tour stop sold out.",
                source_id="tmz",
                kind="celebrity",
            )
        ]
    )
    _check(
        "killed-it slang keeps the normal-day open",
        killed_it.startswith(f"{MICHAEL_STRAIGHT_OPEN}\n{MICHAEL_BEAT}"),
    )

    cottage_open = michael_g_script(
        [
            _story(
                "Dolly Parton's Former Solvang Cottage Sells for $2 Million",
                summary=(
                    "The Solvang cottage that once belonged to Dolly Parton is officially off the market. "
                    "The late legend's former retreat sold this month for $1,945,150, "
                    "weeks after the singer's late August death."
                ),
                source_id="tmz",
                kind="celebrity",
            )
        ]
    )
    _check(
        "a sale blurb that mentions death does not straighten the open",
        cottage_open.startswith(f"{MICHAEL_STRAIGHT_OPEN}\n{MICHAEL_BEAT}"),
    )

    death_flow = build_morning_flow(
        [
            death,
            _story(
                "Studio renews the drama for two more seasons",
                summary="The series returns in November.",
                source_id="deadline",
                kind="entertainment_news",
            ),
            _story(
                "Ocean Light trailer",
                summary=MOVIE_SUMMARY,
                source_id="variety_film",
                kind="film_news",
            ),
            _story(
                "Weekend ticket sales climb again",
                summary="The family comedy led the chart.",
                source_id="tmz",
                kind="celebrity",
            ),
        ]
    )
    _check(
        "death-day package open is straight",
        death_flow["michael_g_script"].splitlines()[0] == MICHAEL_STRAIGHT_OPEN,
    )
    _check(
        "death-day package has no joke",
        MICHAEL_BEAT not in death_flow["michael_g_script"] and "popcorn" not in death_flow["michael_g_script"].lower(),
    )
    _check(
        "death-day prompt forbids the joke",
        "a supplied story is a death, obituary, or mourning item" in death_flow["michael_g_prompt"].lower()
        and         "do not add a comical beat" in death_flow["michael_g_prompt"].lower()
        and "no popcorn joke" in death_flow["michael_g_prompt"].lower()
        and "no coffee" in death_flow["michael_g_prompt"].lower()
        and "no classic rock" in death_flow["michael_g_prompt"].lower(),
    )
    _check("death-day prompt keeps the exact open", MICHAEL_STRAIGHT_OPEN in death_flow["michael_g_prompt"])

    mourning_later = build_morning_flow(
        [
            _story(
                "Singer spotted leaving a downtown diner",
                summary="Fans saw the singer just after midnight.",
                source_id="tmz",
                kind="celebrity",
                published=_dt(9),
            ),
            _story(
                "Studio mourns a longtime editor",
                summary="Colleagues shared tributes on Monday.",
                source_id="deadline",
                kind="entertainment_news",
                published=_dt(12),
            ),
            _story(
                "Ocean Light trailer",
                summary=MOVIE_SUMMARY,
                source_id="variety_film",
                kind="film_news",
                published=_dt(10),
            ),
            _story(
                "Weekend ticket sales climb again",
                summary="The family comedy led the chart.",
                source_id="tmz",
                kind="celebrity",
                published=_dt(8),
            ),
        ]
    )
    _check(
        "mourning in a later slot straightens the package",
        mourning_later["michael_g_script"].splitlines()[0] == MICHAEL_STRAIGHT_OPEN,
    )
    _check("later-slot mourning drops the beat", MICHAEL_BEAT not in mourning_later["michael_g_script"])
    _check("later-slot mourning still reads the movie", "Ocean Light" in mourning_later["michael_g_script"])


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
    _check("reviews feed is not saved", RETIRED_REVIEWS_URL not in upgraded["entertainment_feeds"])
    rules = upgraded["entertainment_report_rules"].lower()
    _check("rules use the movie-news shape", "in movie news" in rules)
    _check("rules forbid saying review", "do not say review" in rules)
    _check("rules do not invent a friday", "do not invent a plot" in rules)
    _check("rules do not name a reviews feed", "variety reviews" not in rules and "reviews/feed" not in rules)
    _check("rules introduce the entertainment report", "michael g here with the entertainment report" in rules)
    _check("rules keep comedy off death", "not sarcastic about death" in rules)
    _check("rules straighten the whole open for a death", "whole open is straight" in rules)
    _check(
        "rules name the exact straight open",
        "thanks, dave. michael g here with the entertainment report." in rules,
    )
    _check("rules use coffee or classic rock on a normal day", "coffee or classic rock" in rules)
    _check("rules reject a disconnected gag", "not a disconnected gag" in rules)
    _check("rules ban coffee and rock on a death day", "no coffee" in rules and "no classic rock" in rules)
    _check("rules do not require the same sentence every day", "not the same sentence every day" in rules)
    _check("rules say he does not read his biography", "does not read his biography" in rules)
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
            ),
            "entertainment_feeds": [
                RETIRED_REVIEWS_URL,
                VARIETY_NEWS_URL,
                "https://station.example/extra.xml",
            ],
        }
    )
    _check(
        "old movie-and-review wording upgrades",
        legacy_rules["entertainment_report_rules"] == DEFAULT_ENTERTAINMENT_REPORT_RULES,
    )
    _check(
        "old wording no longer treats film news as the review",
        "new movies and reviews" not in legacy_rules["entertainment_report_rules"].lower(),
    )
    _check(
        "saved reviews feed is removed",
        RETIRED_REVIEWS_URL not in legacy_rules["entertainment_feeds"]
        and all("variety.com/v/film/reviews" not in url for url in legacy_rules["entertainment_feeds"]),
    )
    _check("film news feed stays in the saved list", VARIETY_NEWS_URL in legacy_rules["entertainment_feeds"])
    _check("extra saved feed stays", "https://station.example/extra.xml" in legacy_rules["entertainment_feeds"])
    stale_open = normalize_script_rules(
        {
            "entertainment_report_rules": (
                "Michael G reads the entertainment report after Dave's sports. "
                "Use only the supplied stories. "
                "Movie news that starts with In movie news. "
                "Do not say review. "
                "Do not invent a plot."
            ),
        }
    )
    _check(
        "saved rules gain the entertainment introduction",
        "michael g here with the entertainment report" in stale_open["entertainment_report_rules"].lower(),
    )
    _check(
        "saved rules gain the death boundary",
        "not sarcastic about death" in stale_open["entertainment_report_rules"].lower(),
    )
    popcorn_open = normalize_script_rules(
        {
            "entertainment_report_rules": (
                "Michael G reads the entertainment report after Dave's sports. "
                'Open with "Thanks, Dave. Michael G here with the entertainment report." '
                "then one short comical beat. "
                "Do not put that comical beat on a death or illness story. "
                "Movie news that starts with In movie news. "
                "Do not say review. "
                "Not sarcastic about death."
            ),
        }
    )
    _check(
        "popcorn-only open upgrades to the straight death rule",
        popcorn_open["entertainment_report_rules"] == DEFAULT_ENTERTAINMENT_REPORT_RULES,
    )
    _check(
        "upgraded rules drop the joke on a death day",
        "whole open is straight" in popcorn_open["entertainment_report_rules"].lower()
        and "no popcorn joke" in popcorn_open["entertainment_report_rules"].lower(),
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
    _check("preview introduces the entertainment report", MICHAEL_STRAIGHT_OPEN in text)
    _check("preview keeps the normal-day beat", MICHAEL_BEAT in text)
    _check(
        "preview beat follows the straight open",
        text.index(MICHAEL_STRAIGHT_OPEN) < text.index(MICHAEL_BEAT),
    )
    _check("preview still signs off", "For Mo's Place Radio, I'm DJ Mo." in text)


def test_config_files() -> None:
    config = ROOT / "config"
    voices = json.loads((config / "voice_library.json").read_text(encoding="utf-8"))
    michael_voice = next(voice for voice in voices["voices"] if voice["display_name"] == "Michael G")
    _check("voicebox id matches the profile", michael_voice["voicebox_id"] == MICHAEL_G_VOICEBOX_ID)
    _check("voice id is the studio record", michael_voice["id"] == "vb-michael-g")
    prompt = michael_voice["personality_prompt"]
    _check("voice prompt uses movie news", "In movie news" in prompt)
    _check("voice prompt forbids saying review", "Do not say review" in prompt)
    _check("voice prompt introduces the entertainment report", "Michael G here with the entertainment report" in prompt)
    _check("voice prompt is not sarcastic about death", "Not sarcastic about death" in prompt)
    _check("voice prompt does not read the biography every morning", "does not read his biography" in prompt.lower())
    _check(
        "voice prompt uses coffee or classic rock",
        "coffee or classic rock" in prompt.lower() and "not a disconnected gag" in prompt.lower(),
    )
    _check(
        "voice prompt bars coffee and rock on a death day",
        "no coffee" in prompt.lower() and "no classic rock" in prompt.lower(),
    )
    _check("voice prompt does not put the degrees on the air", "roger williams" not in prompt.lower())
    _check("voice prompt straightens a death open", "whole open is straight" in prompt.lower())
    _check("voice prompt has the exact straight open", MICHAEL_STRAIGHT_OPEN in prompt)
    _check("voice prompt bars popcorn on a death day", "no popcorn joke" in prompt.lower())
    _check("voice prompt has no reviews feed", "reviews/feed" not in prompt and "Star Wars" not in prompt)
    personalities = json.loads((config / "personalities.json").read_text(encoding="utf-8"))
    michael = next(person for person in personalities["personalities"] if person["display_name"] == "Michael G")
    _check(
        "personality description introduces the report",
        "Michael G here with the entertainment report" in michael["personality_description"],
    )
    _check("bio stored", michael["bio"] == MICHAEL_G_BIO)
    _check(
        "bio is Mike Gleason's",
        "Mike Gleason" in michael["bio"] and "Roger Williams University" in michael["bio"],
    )
    _check(
        "bio includes home, husband, grandkids, and the dog",
        "Southeast Massachusetts" in michael["bio"]
        and "husband" in michael["bio"]
        and "grandkids" in michael["bio"]
        and "their dog" in michael["bio"],
    )
    _check(
        "bio appends the coffee and classic rock line",
        michael["bio"].endswith(
            "Oh, right. I drink a lot of coffee and enjoy listening to classic rock "
            "and talking about all the different sub genres of rock music going back to the golden age."
        ),
    )
    _check("on-air name stays Michael G", michael["display_name"] == "Michael G")
    _check(
        "personality does not read the bio every morning",
        "does not read his biography" in michael["personality_description"].lower(),
    )
    _check(
        "personality uses coffee or classic rock",
        "coffee or classic rock" in michael["personality_description"].lower()
        and "not a disconnected gag" in michael["personality_description"].lower(),
    )
    _check(
        "personality bars coffee and rock on a death day",
        "no coffee" in michael["personality_description"].lower()
        and "no classic rock" in michael["personality_description"].lower(),
    )
    _check(
        "personality straightens a death open",
        "whole open is straight" in michael["personality_description"].lower(),
    )
    _check("personality voicebox id", michael["voicebox_voice_id"] == MICHAEL_G_VOICEBOX_ID)
    _check("personality stores the UNC profile", MICHAEL_G_VOICEBOX_PROFILE in michael["voice_description"])
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
    print(MOVIE_LINE)


if __name__ == "__main__":
    main()

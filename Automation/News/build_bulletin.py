"""Write the spoken newscast the news launcher can hand to the engine.

Office PC files:
  D:\\MosPlaceRadioPlatform\\Automation\\News\\build_bulletin.py
  D:\\MosPlaceRadioPlatform\\Automation\\News\\bulletin.txt

run_news_now.bat runs this builder, then still calls engine.local.cmd when
that file is present. engine.local.cmd is not in git. Until that Office PC
file speaks bulletin.txt, the old newscast is what airs.

Morning order is locked: Mo, Johnny J, Dave, Michael G, then Mo.
A 12:15 bulletin says 12:15. Yesterday's news_copy is skipped so stale hard
news cannot air. A down feed is logged and the rest is still written.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Studio"))

from app.core.entertainment_report import (  # noqa: E402
    DAVE_SPORTS_CLOSE,
    MICHAEL_HANDOFF,
    MO_THANKS,
    EntertainmentStory,
    build_morning_flow,
    collect_entertainment_report,
    split_morning_news_copy,
)
from app.core.sports_report import build_dave_sports_script, format_sports_story  # noqa: E402

LOGGER = logging.getLogger("mos.news.bulletin")
STATION_TZ = ZoneInfo("America/New_York")
NEWS_DIR = Path(__file__).resolve().parent
BULLETIN_NAME = "bulletin.txt"
AUDIT_NAME = "bulletin-audit.txt"
NEWS_COPY_NAME = "news_copy.txt"
# Hard news older than this is treated as yesterday's copy and skipped.
NEWS_COPY_MAX_AGE = timedelta(hours=18)

# Air clocks on the station schedule. The label is what Mo says.
AIR_SLOTS = (
    (7 * 60 + 15, "7:15"),
    (12 * 60 + 15, "12:15"),
    (17 * 60 + 15, "5:15"),
)


def next_air_label(now: datetime | None = None) -> str:
    """Next 7:15, 12:15, or 5:15 air time in Eastern time."""
    current = now or datetime.now(STATION_TZ)
    if current.tzinfo is None:
        current = current.replace(tzinfo=STATION_TZ)
    else:
        current = current.astimezone(STATION_TZ)
    minutes = current.hour * 60 + current.minute
    for slot, label in AIR_SLOTS:
        if minutes < slot:
            return label
    return "7:15"


def thanks_for_air(air: str) -> str:
    """Mo's thanks. 7:15 keeps the locked morning line. Other clocks name themselves."""
    clock = str(air or "").strip().lower().replace(" pm", "").replace(" am", "")
    if clock in {"7:15", "07:15"}:
        return MO_THANKS
    if clock in {"17:15", "5:15"}:
        clock = "5:15"
    if not clock:
        clock = "12:15"
    return f"Thanks, Michael G. Weekdays at {clock} on Mo's Place Radio."


def _strip_previous_handoff(text: str) -> str:
    """Keep the hard-news body. Drop a Dave/Michael block already appended."""
    body = str(text or "").replace("\r\n", "\n").strip()
    if not body:
        return ""
    for marker in ("[Dave]", DAVE_SPORTS_CLOSE, "[Michael G]"):
        index = body.find(marker)
        if index >= 0:
            body = body[:index]
    return body.strip()


def news_copy_is_fresh(path: Path, *, now: datetime | None = None) -> bool:
    """True when news_copy was written today in Eastern time, within max age."""
    current = now or datetime.now(STATION_TZ)
    if current.tzinfo is None:
        current = current.replace(tzinfo=STATION_TZ)
    else:
        current = current.astimezone(STATION_TZ)
    try:
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=STATION_TZ)
    except OSError:
        return False
    if mtime.date() != current.date():
        return False
    return (current - mtime) <= NEWS_COPY_MAX_AGE


def load_news_copy(path: Path | None = None, *, now: datetime | None = None) -> str:
    """Today's hard-news copy beside the launcher. Yesterday's file is skipped."""
    candidate = path if path is not None else NEWS_DIR / NEWS_COPY_NAME
    if not candidate.is_file():
        return ""
    if not news_copy_is_fresh(candidate, now=now):
        _log_failure(
            f"Existing news copy skipped as stale ({candidate}); "
            "Mo and Johnny still open, and sports/entertainment still refresh"
        )
        return ""
    try:
        return _strip_previous_handoff(candidate.read_text(encoding="utf-8"))
    except OSError as exc:
        _log_failure(f"Existing news copy skipped ({candidate}): {exc}")
        return ""


def _log_failure(message: str) -> None:
    LOGGER.warning(message)
    try:
        with (NEWS_DIR / "news.log").open("a", encoding="utf-8") as handle:
            handle.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {message}\n")
    except OSError:
        LOGGER.warning("Could not append news.log")


def _sports_sentence(fetch: bool, sports_lines: list[str] | None) -> str:
    if sports_lines is not None:
        return format_sports_story(sports_lines)
    try:
        return format_sports_story(build_dave_sports_script(fetch=fetch))
    except Exception as exc:
        _log_failure(f"Sports feed skipped: {exc}")
        return ""


def _entertainment_flow(
    fetch: bool,
    stories: list[EntertainmentStory] | None,
    air: str,
    *,
    sports_body: str = "",
    mo_body: str = "",
    johnny_body: str = "",
) -> tuple[dict, str]:
    selected: list[EntertainmentStory] = []
    audit = ""
    if stories is not None:
        selected = list(stories)
    else:
        try:
            report = collect_entertainment_report(fetch=fetch)
            selected = list(report.get("stories") or [])
            audit_payload = report.get("audit") if isinstance(report, dict) else None
            if isinstance(audit_payload, dict):
                audit = str(audit_payload.get("text") or "")
        except Exception as exc:
            _log_failure(f"Entertainment feed skipped: {exc}")
            selected = []
    if audit:
        LOGGER.info("Entertainment story selection audit:\n%s", audit)
    try:
        flow = build_morning_flow(
            selected,
            sports_body=sports_body,
            mo_body=mo_body,
            johnny_body=johnny_body,
            mo_thanks=thanks_for_air(air),
        )
    except Exception as exc:
        _log_failure(f"Entertainment handoff skipped: {exc}")
        flow = build_morning_flow(
            [],
            sports_body=sports_body,
            mo_body=mo_body,
            johnny_body=johnny_body,
            mo_thanks=thanks_for_air(air),
        )
    return flow, audit


def build_bulletin_text(
    *,
    air: str = "12:15",
    fetch: bool = False,
    news_copy: str = "",
    sports_lines: list[str] | None = None,
    stories: list[EntertainmentStory] | None = None,
) -> str:
    """Spoken bulletin in Mo, Johnny, Dave, Michael G, Mo order."""
    script, _audit = assemble_bulletin(
        air=air,
        fetch=fetch,
        news_copy=news_copy,
        sports_lines=sports_lines,
        stories=stories,
    )
    return script


def assemble_bulletin(
    *,
    air: str = "12:15",
    fetch: bool = False,
    news_copy: str = "",
    sports_lines: list[str] | None = None,
    stories: list[EntertainmentStory] | None = None,
) -> tuple[str, str]:
    """Script text plus the operator audit. The audit is not part of the script."""
    sports = _sports_sentence(fetch, sports_lines)
    if not sports:
        _log_failure("Sports copy is empty; Dave still hands to Michael G")
    body = _strip_previous_handoff(news_copy)
    mo_body, johnny_body = split_morning_news_copy(body)
    flow, audit = _entertainment_flow(
        fetch,
        stories,
        air,
        sports_body=sports,
        mo_body=mo_body,
        johnny_body=johnny_body,
    )
    script = str(flow.get("script") or "").strip() + "\n"
    if MICHAEL_HANDOFF not in script:
        _log_failure("Michael G handoff was missing; the rest of the bulletin was still written")
    return script, audit


def write_bulletin(
    *,
    air: str,
    fetch: bool = True,
    news_file: Path | None = None,
    output: Path | None = None,
    sports_lines: list[str] | None = None,
    stories: list[EntertainmentStory] | None = None,
    now: datetime | None = None,
) -> Path:
    """Write bulletin.txt. The audit file is for the operator, not the air."""
    if news_file is not None:
        news_copy = load_news_copy(news_file, now=now)
    else:
        news_copy = load_news_copy(now=now)
    if not news_copy:
        _log_failure(
            "No fresh news copy was supplied; Mo and Johnny still open, "
            "and sports and entertainment were still written"
        )
    script, audit = assemble_bulletin(
        air=air,
        fetch=fetch,
        news_copy=news_copy,
        sports_lines=sports_lines,
        stories=stories,
    )
    destination = output or (NEWS_DIR / BULLETIN_NAME)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(script, encoding="utf-8")
    if audit:
        audit_path = destination.with_name(AUDIT_NAME) if output is not None else NEWS_DIR / AUDIT_NAME
        audit_path.write_text(audit + "\n", encoding="utf-8")
    return destination


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write the spoken news bulletin.")
    parser.add_argument("--air", default="", help="7:15, 12:15, or 5:15. Default is the next Eastern air time.")
    parser.add_argument("--news-file", default="", help="Existing news copy. Defaults to news_copy.txt beside this script.")
    parser.add_argument("--output", default="", help="Defaults to bulletin.txt beside this script.")
    parser.add_argument("--no-fetch", action="store_true", help="Skip the network and write the handoff only.")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO)
    air = args.air.strip() or next_air_label()
    news_file = Path(args.news_file) if args.news_file else None
    output = Path(args.output) if args.output else None
    path = write_bulletin(air=air, fetch=not args.no_fetch, news_file=news_file, output=output)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

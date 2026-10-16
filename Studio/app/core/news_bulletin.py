"""Build the spoken newscast written beside the News launcher.

Morning (7:15): Mo, Johnny J, Dave, Michael G, then Mo.
Midday (12:15): Mo, Johnny J, Dave, Michael G, Bailey, then Mo.
Yesterday's news_copy is skipped so stale hard news cannot air. A down feed
is logged and the rest is still written.

Studio Run News Now installs the Automation/News launcher files and calls
this builder. Task Scheduler uses Automation/News/run_news_now.bat, which
runs the thin build_bulletin.py wrapper that imports this module.
"""

from __future__ import annotations

import argparse
import logging
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from app.core.bailey_report import collect_bailey_report
from app.core.entertainment_report import (
    DAVE_SPORTS_CLOSE,
    MICHAEL_HANDOFF,
    MICHAEL_MIDDAY_HANDOFF,
    MO_THANKS,
    MO_THANKS_BAILEY,
    EntertainmentStory,
    build_midday_flow,
    build_morning_flow,
    collect_entertainment_report,
    split_morning_news_copy,
)
from app.core.sports_report import build_dave_sports_script, format_sports_story

LOGGER = logging.getLogger("mos.news.bulletin")
STATION_TZ = ZoneInfo("America/New_York")
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


def default_news_dir() -> Path:
    """Live Automation/News folder on the platform, when configured."""
    try:
        from app.core.platform_manager import platform_path

        return platform_path("automation_news")
    except Exception:
        return Path.cwd()


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


def normalize_air(air: str) -> str:
    clock = str(air or "").strip().lower().replace(" pm", "").replace(" am", "")
    if clock in {"07:15", "7:15"}:
        return "7:15"
    if clock in {"12:15"}:
        return "12:15"
    if clock in {"17:15", "5:15"}:
        return "5:15"
    return clock or "7:15"


def is_midday_air(air: str) -> bool:
    return normalize_air(air) == "12:15"


def thanks_for_air(air: str) -> str:
    """Mo's thanks. 7:15 thanks Michael G. Midday thanks Bailey after her close."""
    clock = normalize_air(air)
    if clock == "7:15":
        return MO_THANKS
    if clock == "12:15" or not clock:
        return "Love you, hun. Thanks, Bailey. Weekdays at 12:15 on Mo's Place Radio."
    return f"Thanks, Michael G. Weekdays at {clock} on Mo's Place Radio."


def _strip_previous_handoff(text: str) -> str:
    """Keep the hard-news body. Drop a Dave/Michael/Bailey block already appended."""
    body = str(text or "").replace("\r\n", "\n").strip()
    if not body:
        return ""
    for marker in ("[Dave]", DAVE_SPORTS_CLOSE, "[Bailey]", "[Michael G]"):
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


def _log_failure(message: str, news_dir: Path) -> None:
    LOGGER.warning(message)
    try:
        with (news_dir / "news.log").open("a", encoding="utf-8") as handle:
            handle.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {message}\n")
    except OSError:
        LOGGER.warning("Could not append news.log")


def load_news_copy(
    path: Path | None = None,
    *,
    now: datetime | None = None,
    news_dir: Path | None = None,
) -> str:
    """Today's hard-news copy beside the launcher. Yesterday's file is skipped."""
    folder = news_dir or default_news_dir()
    candidate = path if path is not None else folder / NEWS_COPY_NAME
    if not candidate.is_file():
        return ""
    if not news_copy_is_fresh(candidate, now=now):
        _log_failure(
            f"Existing news copy skipped as stale ({candidate}); "
            "Mo and Johnny still open, and sports/entertainment still refresh",
            folder,
        )
        return ""
    try:
        return _strip_previous_handoff(candidate.read_text(encoding="utf-8"))
    except OSError as exc:
        _log_failure(f"Existing news copy skipped ({candidate}): {exc}", folder)
        return ""


def _sports_sentence(
    fetch: bool,
    sports_lines: list[str] | None,
    news_dir: Path,
) -> str:
    if sports_lines is not None:
        return format_sports_story(sports_lines)
    try:
        return format_sports_story(build_dave_sports_script(fetch=fetch))
    except Exception as exc:
        _log_failure(f"Sports feed skipped: {exc}", news_dir)
        return ""


def _collect_stories(
    fetch: bool,
    stories: list[EntertainmentStory] | None,
    news_dir: Path,
) -> tuple[list[EntertainmentStory], str]:
    if stories is not None:
        return list(stories), ""
    try:
        report = collect_entertainment_report(fetch=fetch)
        selected = list(report.get("stories") or [])
        audit = ""
        audit_payload = report.get("audit") if isinstance(report, dict) else None
        if isinstance(audit_payload, dict):
            audit = str(audit_payload.get("text") or "")
        return selected, audit
    except Exception as exc:
        _log_failure(f"Entertainment feed skipped: {exc}", news_dir)
        return [], ""


def _build_flow(
    air: str,
    selected: list[EntertainmentStory],
    *,
    sports_body: str = "",
    mo_body: str = "",
    johnny_body: str = "",
    bailey_script: str = "",
) -> dict:
    thanks = thanks_for_air(air)
    if is_midday_air(air):
        return build_midday_flow(
            selected,
            sports_body=sports_body,
            mo_body=mo_body,
            johnny_body=johnny_body,
            bailey_script=bailey_script,
            mo_thanks=thanks,
        )
    return build_morning_flow(
        selected,
        sports_body=sports_body,
        mo_body=mo_body,
        johnny_body=johnny_body,
        mo_thanks=thanks,
    )


def _collect_bailey(
    fetch: bool,
    bailey_script: str | None,
    news_dir: Path,
) -> str:
    """Bailey's Hidden Boston + Good News Wag page. Midday only."""
    if bailey_script is not None:
        return str(bailey_script or "").strip()
    try:
        report = collect_bailey_report(fetch=fetch)
        return str(report.get("script") or "").strip()
    except Exception as exc:
        _log_failure(f"Bailey Hidden Boston / animal feeds skipped: {exc}", news_dir)
        return ""


def build_bulletin_text(
    *,
    air: str = "12:15",
    fetch: bool = False,
    news_copy: str = "",
    sports_lines: list[str] | None = None,
    stories: list[EntertainmentStory] | None = None,
    bailey_script: str | None = None,
    news_dir: Path | None = None,
) -> str:
    """Spoken bulletin for the air clock: morning or midday desk order."""
    script, _audit = assemble_bulletin(
        air=air,
        fetch=fetch,
        news_copy=news_copy,
        sports_lines=sports_lines,
        stories=stories,
        bailey_script=bailey_script,
        news_dir=news_dir,
    )
    return script


def assemble_bulletin(
    *,
    air: str = "12:15",
    fetch: bool = False,
    news_copy: str = "",
    sports_lines: list[str] | None = None,
    stories: list[EntertainmentStory] | None = None,
    bailey_script: str | None = None,
    news_dir: Path | None = None,
) -> tuple[str, str]:
    """Script text plus the operator audit. The audit is not part of the script."""
    folder = news_dir or default_news_dir()
    body = _strip_previous_handoff(news_copy)
    mo_body, johnny_body = split_morning_news_copy(body)
    selected, audit = _collect_stories(fetch, stories, folder)
    if audit:
        LOGGER.info("Entertainment story selection audit:\n%s", audit)

    sports = _sports_sentence(fetch, sports_lines, folder)
    if not sports:
        _log_failure("Sports copy is empty; Dave still hands to Michael G", folder)

    bailey_page = ""
    if is_midday_air(air):
        bailey_page = _collect_bailey(fetch, bailey_script, folder)

    try:
        flow = _build_flow(
            air,
            selected,
            sports_body=sports,
            mo_body=mo_body,
            johnny_body=johnny_body,
            bailey_script=bailey_page,
        )
    except Exception as exc:
        _log_failure(f"Entertainment handoff skipped: {exc}", folder)
        flow = _build_flow(
            air,
            [],
            sports_body=sports,
            mo_body=mo_body,
            johnny_body=johnny_body,
            bailey_script=bailey_page,
        )

    script = str(flow.get("script") or "").strip() + "\n"
    expected_handoff = MICHAEL_MIDDAY_HANDOFF if is_midday_air(air) else MICHAEL_HANDOFF
    if expected_handoff not in script:
        _log_failure(
            "Michael G handoff was missing; the rest of the bulletin was still written",
            folder,
        )
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
    news_dir: Path | None = None,
) -> Path:
    """Write bulletin.txt. The audit file is for the operator, not the air."""
    folder = news_dir or default_news_dir()
    if news_file is not None:
        news_copy = load_news_copy(news_file, now=now, news_dir=folder)
    else:
        news_copy = load_news_copy(now=now, news_dir=folder)
    if not news_copy:
        _log_failure(
            "No fresh news copy was supplied; Mo and Johnny still open, "
            "and the rest of the bulletin was still written",
            folder,
        )
    script, audit = assemble_bulletin(
        air=air,
        fetch=fetch,
        news_copy=news_copy,
        sports_lines=sports_lines,
        stories=stories,
        news_dir=folder,
    )
    destination = output or (folder / BULLETIN_NAME)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(script, encoding="utf-8")
    if audit:
        audit_path = destination.with_name(AUDIT_NAME) if output is not None else folder / AUDIT_NAME
        audit_path.write_text(audit + "\n", encoding="utf-8")
    return destination


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write the spoken news bulletin.")
    parser.add_argument("--air", default="", help="7:15, 12:15, or 5:15. Default is the next Eastern air time.")
    parser.add_argument("--news-file", default="", help="Existing news copy. Defaults to news_copy.txt beside the news folder.")
    parser.add_argument("--output", default="", help="Defaults to bulletin.txt in the news folder.")
    parser.add_argument("--news-dir", default="", help="Automation/News folder. Defaults to the platform news path or cwd.")
    parser.add_argument("--no-fetch", action="store_true", help="Skip the network and write the handoff only.")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO)
    folder = Path(args.news_dir) if args.news_dir else default_news_dir()
    air = args.air.strip() or next_air_label()
    news_file = Path(args.news_file) if args.news_file else None
    output = Path(args.output) if args.output else None
    path = write_bulletin(
        air=air,
        fetch=not args.no_fetch,
        news_file=news_file,
        output=output,
        news_dir=folder,
    )
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

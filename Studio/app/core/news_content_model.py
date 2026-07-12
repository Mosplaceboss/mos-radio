"""News & Content Manager data models, validation, RSS testing, and reports."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from app.core.news_content_storage import (
    load_news_content_bundle,
    news_dev_output_dir,
    news_reports_dir,
    rss_sources_path,
    save_news_content_bundle,
)
from app.core.platform_manager import platform_path
from app.core.schedule_model import DAYS

DEFAULT_PERSONALITIES = (
    ("dj_mo", "DJ Mo", "anchor"),
    ("johnny_j", "Johnny J", "anchor"),
    ("mos_place_dave", "Mo's Place Dave", "anchor"),
    ("bonnie", "Bonnie", "reporter"),
    ("flea", "Flea", "reporter"),
    ("future", "Future Personalities", "anchor"),
)

DEFAULT_CATEGORIES = (
    "Breaking News",
    "Local",
    "Community Safety",
    "Regional",
    "National",
    "Traffic",
    "Weather",
    "Sports",
    "Entertainment",
    "Food",
    "Beer",
    "Birthdays",
)

DEFAULT_SCHEDULE_SLOTS = (
    ("morning", "Morning", "06:30"),
    ("midday", "Midday", "12:00"),
    ("afternoon", "Afternoon", "16:30"),
)

NEWS_ROLES = ("anchor", "reporter", "weather", "sports", "traffic", "backup")

SPEAKING_STYLES = ("conversational", "authoritative", "upbeat", "calm", "urgent")


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


def default_personalities() -> list[dict[str, Any]]:
    return [
        {
            "id": key,
            "name": name,
            "role": role,
            "voice_id": "",
            "enabled": key != "future",
            "notes": "",
        }
        for key, name, role in DEFAULT_PERSONALITIES
    ]


def default_categories() -> list[dict[str, Any]]:
    return [
        {
            "id": _new_id("cat"),
            "name": name,
            "enabled": True,
            "priority": index + 1,
        }
        for index, name in enumerate(DEFAULT_CATEGORIES)
    ]


def default_schedule_slots() -> list[dict[str, Any]]:
    return [
        {
            "id": _new_id("slot"),
            "slot_type": slot_type,
            "name": label,
            "time": time_value,
            "days": list(DAYS),
            "enabled": True,
            "personality_id": "",
            "notes": "",
        }
        for slot_type, label, time_value in DEFAULT_SCHEDULE_SLOTS
    ]


def default_script_rules() -> dict[str, Any]:
    return {
        "story_order": [cat for cat in DEFAULT_CATEGORIES[:6]],
        "maximum_stories": 8,
        "personality_handoffs": True,
        "opening": "This is Mo's Place Radio news.",
        "closing": "For Mo's Place Radio, I'm {personality}.",
        "pronunciation_rules": [],
        "pause_sound_between_stories": "news_bed.mp3",
        "news_first_personality_rules": "Lead anchor opens every newscast.",
        "stale_hours_warning": 12,
    }


def default_voice_settings() -> dict[str, Any]:
    return {
        "voicebox_id": "",
        "voice_volume": 100,
        "speaking_style": "conversational",
        "pronunciation_dictionary": [],
    }


def normalize_personalities(data: dict[str, Any] | None) -> dict[str, Any]:
    personalities = data.get("personalities", []) if data else []
    if not personalities:
        personalities = default_personalities()
    normalized = []
    for item in personalities:
        record = deepcopy(item)
        record.setdefault("id", _new_id("np"))
        record.setdefault("name", "Personality")
        record.setdefault("role", "anchor")
        record.setdefault("voice_id", "")
        record.setdefault("enabled", True)
        record.setdefault("notes", "")
        normalized.append(record)
    return {"personalities": normalized}


def normalize_categories(data: dict[str, Any] | None) -> dict[str, Any]:
    categories = data.get("categories", []) if data else []
    if not categories:
        categories = default_categories()
    normalized = []
    for item in categories:
        record = deepcopy(item)
        record.setdefault("id", _new_id("cat"))
        record.setdefault("name", "Category")
        record.setdefault("enabled", True)
        record.setdefault("priority", 99)
        normalized.append(record)
    return {"categories": normalized}


def normalize_rss_sources(data: dict[str, Any] | None) -> dict[str, Any]:
    sources = data.get("sources", []) if data else []
    normalized = []
    for item in sources:
        record = deepcopy(item)
        record.setdefault("id", _new_id("rss"))
        record.setdefault("name", "")
        record.setdefault("url", "")
        record.setdefault("enabled", True)
        record.setdefault("category_id", "")
        record.setdefault("last_successful_update", "")
        record.setdefault("last_test_status", "")
        record.setdefault("last_test_message", "")
        record.setdefault("duplicate_key", "")
        normalized.append(record)
    return {"sources": normalized}


def normalize_schedule(data: dict[str, Any] | None) -> dict[str, Any]:
    slots = data.get("slots", []) if data else []
    if not slots:
        slots = default_schedule_slots()
    normalized_slots = []
    for item in slots:
        record = deepcopy(item)
        record.setdefault("id", _new_id("slot"))
        record.setdefault("slot_type", "morning")
        record.setdefault("name", "News Slot")
        record.setdefault("time", "06:30")
        record.setdefault("days", list(DAYS))
        record.setdefault("enabled", True)
        record.setdefault("personality_id", "")
        record.setdefault("notes", "")
        normalized_slots.append(record)
    overrides = data.get("overrides", []) if data else []
    normalized_overrides = []
    for item in overrides:
        record = deepcopy(item)
        record.setdefault("id", _new_id("ovr"))
        record.setdefault("override_type", "temporary")
        record.setdefault("date", "")
        record.setdefault("slot_type", "morning")
        record.setdefault("time", "")
        record.setdefault("enabled", True)
        record.setdefault("notes", "")
        normalized_overrides.append(record)
    return {
        "slots": normalized_slots,
        "overrides": overrides if overrides else normalized_overrides,
        "timezone": data.get("timezone", "America/New_York") if data else "America/New_York",
    }


def normalize_script_rules(data: dict[str, Any] | None) -> dict[str, Any]:
    base = default_script_rules()
    if not data:
        return base
    merged = deepcopy(base)
    merged.update(data)
    merged.setdefault("pronunciation_rules", [])
    return merged


def normalize_voice_settings(data: dict[str, Any] | None) -> dict[str, Any]:
    base = default_voice_settings()
    if not data:
        return base
    merged = deepcopy(base)
    merged.update(data)
    merged.setdefault("pronunciation_dictionary", [])
    return merged


def normalize_overview(data: dict[str, Any] | None) -> dict[str, Any]:
    base = {
        "morning_status": "Not run",
        "midday_status": "Not run",
        "afternoon_status": "Not run",
        "last_successful_run": "",
        "next_scheduled_run": "",
        "current_output_files": [],
        "errors_warnings": [],
    }
    if not data:
        return base
    merged = deepcopy(base)
    merged.update(data)
    merged.setdefault("current_output_files", [])
    merged.setdefault("errors_warnings", [])
    return merged


def normalize_run_history(data: dict[str, Any] | None) -> dict[str, Any]:
    runs = data.get("runs", []) if data else []
    normalized = []
    for item in runs:
        record = deepcopy(item)
        record.setdefault("id", _new_id("run"))
        record.setdefault("slot_type", "")
        record.setdefault("started_at", "")
        record.setdefault("finished_at", "")
        record.setdefault("status", "unknown")
        record.setdefault("stories_used", 0)
        record.setdefault("output_file", "")
        record.setdefault("message", "")
        normalized.append(record)
    return {"runs": normalized}


def normalize_feed_reliability(data: dict[str, Any] | None) -> dict[str, Any]:
    feeds = data.get("feeds", {}) if data else {}
    if not isinstance(feeds, dict):
        feeds = {}
    return {"feeds": feeds}


def normalize_bundle(data: dict[str, Any] | None) -> dict[str, Any]:
    payload = data or {}
    return {
        "personalities": normalize_personalities(payload.get("personalities")),
        "categories": normalize_categories(payload.get("categories")),
        "rss_sources": normalize_rss_sources(payload.get("rss_sources")),
        "schedule": normalize_schedule(payload.get("schedule")),
        "script_rules": normalize_script_rules(payload.get("script_rules")),
        "voice_settings": normalize_voice_settings(payload.get("voice_settings")),
        "overview": normalize_overview(payload.get("overview")),
        "state": payload.get("state", {"last_validated": "", "version": 1}),
        "run_history": normalize_run_history(payload.get("run_history")),
        "feed_reliability": normalize_feed_reliability(payload.get("feed_reliability")),
    }


def seed_rss_from_studio_news(news_data: dict[str, Any], categories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    category_by_name = {item["name"].lower(): item["id"] for item in categories}
    local_id = category_by_name.get("local", "")
    sources = []
    for feed in news_data.get("rss_feeds", []):
        sources.append(
            {
                "id": feed.get("id", _new_id("rss")),
                "name": feed.get("name", ""),
                "url": feed.get("url", ""),
                "enabled": feed.get("enabled", True),
                "category_id": local_id,
                "last_successful_update": "",
                "last_test_status": "",
                "last_test_message": "",
                "duplicate_key": feed.get("url", "").strip().lower(),
            }
        )
    return sources


def ensure_news_content_data(config_manager=None) -> None:
    if rss_sources_path(config_manager).exists():
        return
    bundle = normalize_bundle({})
    news_config = config_manager.load("news", {"rss_feeds": []}) if config_manager else {"rss_feeds": []}
    if news_config.get("rss_feeds"):
        bundle["rss_sources"]["sources"] = seed_rss_from_studio_news(
            news_config, bundle["categories"]["categories"]
        )
    if news_config.get("last_successful_run"):
        bundle["overview"]["last_successful_run"] = news_config["last_successful_run"]
    save_news_content_bundle(bundle, config_manager)


def test_rss_feed(url: str, timeout: float = 8.0) -> tuple[str, str]:
    cleaned = url.strip()
    if not cleaned:
        return "error", "URL is required"
    if not cleaned.lower().startswith(("http://", "https://")):
        return "error", "URL must start with http:// or https://"
    try:
        request = Request(cleaned, headers={"User-Agent": "MoPlaceStudio/2.0"})
        with urlopen(request, timeout=timeout) as response:
            content = response.read(65536)
        if b"<rss" not in content.lower() and b"<feed" not in content.lower():
            return "warn", "Response received but RSS/Atom markers not found"
        try:
            ET.fromstring(content)
        except ET.ParseError:
            return "warn", "Feed downloaded but XML could not be parsed"
        return "ok", "Feed responded successfully"
    except URLError as exc:
        return "error", f"Feed request failed: {exc.reason}"
    except OSError as exc:
        return "error", str(exc)


def _duplicate_feed_keys(sources: list[dict[str, Any]]) -> list[str]:
    seen: dict[str, list[str]] = {}
    for source in sources:
        key = source.get("duplicate_key") or source.get("url", "").strip().lower()
        if not key:
            continue
        seen.setdefault(key, []).append(source.get("name", source.get("id", "")))
    return [f"{names[0]} ({len(names)} feeds)" for names in seen.values() if len(names) > 1]


def _duplicate_story_titles(sources: list[dict[str, Any]]) -> list[str]:
    titles: dict[str, int] = {}
    for source in sources:
        title = source.get("name", "").strip().lower()
        if title:
            titles[title] = titles.get(title, 0) + 1
    return [title for title, count in titles.items() if count > 1]


def list_output_files(config_manager=None) -> list[str]:
    paths: list[str] = []
    audio_news = platform_path("audio_news", config_manager)
    if audio_news.exists():
        for path in sorted(audio_news.glob("*.mp3"))[:20]:
            paths.append(str(path))
    dev_output = news_dev_output_dir(config_manager)
    for path in sorted(dev_output.glob("*"))[:20]:
        paths.append(str(path))
    return paths


def generate_dev_script_preview(bundle: dict[str, Any], config_manager=None) -> str:
    personalities = [p for p in bundle["personalities"]["personalities"] if p.get("enabled")]
    anchor = personalities[0]["name"] if personalities else "Anchor"
    categories = [c["name"] for c in bundle["categories"]["categories"] if c.get("enabled")][: bundle["script_rules"]["maximum_stories"]]
    lines = [
        bundle["script_rules"].get("opening", ""),
        "",
        f"Good morning, I'm {anchor}.",
        "",
    ]
    for index, category in enumerate(categories, start=1):
        lines.append(f"Story {index} — {category}: Sample headline for development preview.")
        if bundle["script_rules"].get("pause_sound_between_stories"):
            lines.append(f"[pause: {bundle['script_rules']['pause_sound_between_stories']}]")
        lines.append("")
    closing = bundle["script_rules"].get("closing", "").replace("{personality}", anchor)
    lines.append(closing)
    lines.append("")
    lines.append("— Development preview only. Not published to live News.")
    content = "\n".join(lines)
    output_dir = news_dev_output_dir(config_manager)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    script_path = output_dir / f"news_preview_{timestamp}.txt"
    script_path.write_text(content, encoding="utf-8")
    return str(script_path)


def refresh_overview_from_bundle(bundle: dict[str, Any], config_manager=None) -> dict[str, Any]:
    overview = deepcopy(bundle["overview"])
    runs = bundle["run_history"]["runs"]
    for slot_type, key in (
        ("morning", "morning_status"),
        ("midday", "midday_status"),
        ("afternoon", "afternoon_status"),
    ):
        slot_runs = [run for run in runs if run.get("slot_type") == slot_type]
        if not slot_runs:
            overview[key] = "Not run"
            continue
        latest = sorted(slot_runs, key=lambda item: item.get("finished_at", ""), reverse=True)[0]
        overview[key] = latest.get("status", "unknown").title()

    successful = [run for run in runs if run.get("status") == "success"]
    if successful:
        latest_success = sorted(successful, key=lambda item: item.get("finished_at", ""), reverse=True)[0]
        overview["last_successful_run"] = latest_success.get("finished_at", "")

    enabled_slots = [slot for slot in bundle["schedule"]["slots"] if slot.get("enabled")]
    if enabled_slots:
        next_slot = sorted(enabled_slots, key=lambda item: item.get("time", ""))[0]
        overview["next_scheduled_run"] = f"{next_slot.get('name', 'News')} at {next_slot.get('time', '')}"

    overview["current_output_files"] = list_output_files(config_manager)
    overview["errors_warnings"] = validate_news_content(bundle)[:12]
    return overview


def validate_news_content(bundle: dict[str, Any], config_manager=None) -> list[str]:
    warnings: list[str] = []
    personalities = bundle["personalities"]["personalities"]
    enabled_personalities = [p for p in personalities if p.get("enabled")]
    for personality in enabled_personalities:
        if not personality.get("voice_id"):
            warnings.append(f"Missing voice: {personality.get('name', personality.get('id', ''))}")

    sources = bundle["rss_sources"]["sources"]
    enabled_sources = [source for source in sources if source.get("enabled")]
    if not enabled_sources:
        warnings.append("Missing source: no enabled RSS feeds configured")
    for source in enabled_sources:
        if not source.get("url", "").strip():
            warnings.append(f"Missing source URL: {source.get('name', source.get('id', ''))}")
        elif source.get("last_test_status") == "error":
            warnings.append(f"Broken RSS feed: {source.get('name', '')} — {source.get('last_test_message', '')}")

    output_folder = platform_path("audio_news", config_manager)
    if not output_folder.exists():
        warnings.append(f"Missing output folder: {output_folder}")

    dev_output = news_dev_output_dir(config_manager)
    if not dev_output.exists():
        warnings.append(f"Missing development output folder: {dev_output}")

    for dup in _duplicate_feed_keys(sources):
        warnings.append(f"Duplicate feed URL: {dup}")

    pronunciation = bundle["voice_settings"].get("pronunciation_dictionary", [])
    rules = bundle["script_rules"].get("pronunciation_rules", [])
    if not pronunciation and not rules:
        warnings.append("Missing pronunciation dictionary entries")

    stale_hours = int(bundle["script_rules"].get("stale_hours_warning", 12) or 12)
    last_run = bundle["overview"].get("last_successful_run", "")
    if last_run:
        try:
            parsed = datetime.fromisoformat(last_run.replace("Z", ""))
            age_hours = (datetime.now() - parsed).total_seconds() / 3600
            if age_hours > stale_hours:
                warnings.append(f"Stale news warning: last successful run was {int(age_hours)} hours ago")
        except ValueError:
            pass

    for title in _duplicate_story_titles(sources):
        warnings.append(f"Duplicate story source name: {title}")

    if not bundle["voice_settings"].get("voicebox_id"):
        warnings.append("Missing Voicebox ID in voice settings")

    return warnings


@dataclass
class NewsOverviewSnapshot:
    morning_status: str = "Not run"
    midday_status: str = "Not run"
    afternoon_status: str = "Not run"
    last_successful_run: str = "—"
    next_scheduled_run: str = "—"
    current_output_files: list[str] = field(default_factory=list)
    errors_warnings: list[str] = field(default_factory=list)


def build_overview_snapshot(bundle: dict[str, Any]) -> NewsOverviewSnapshot:
    overview = bundle["overview"]
    return NewsOverviewSnapshot(
        morning_status=overview.get("morning_status", "Not run"),
        midday_status=overview.get("midday_status", "Not run"),
        afternoon_status=overview.get("afternoon_status", "Not run"),
        last_successful_run=overview.get("last_successful_run") or "—",
        next_scheduled_run=overview.get("next_scheduled_run") or "—",
        current_output_files=overview.get("current_output_files", []),
        errors_warnings=overview.get("errors_warnings", []),
    )


REPORT_OPTIONS = (
    ("run_history", "News Run History"),
    ("failed_runs", "Failed Runs"),
    ("feed_reliability", "Feed Reliability"),
    ("stories_used", "Stories Used"),
    ("duplicate_stories", "Duplicate Stories"),
    ("last_successful_output", "Last Successful Output"),
)


def build_report_lines(bundle: dict[str, Any], report_key: str) -> list[str]:
    runs = bundle["run_history"]["runs"]
    sources = bundle["rss_sources"]["sources"]
    reliability = bundle["feed_reliability"]["feeds"]

    if report_key == "run_history":
        lines = ["News Run History", ""]
        if not runs:
            lines.append("  No runs recorded yet.")
            return lines
        for run in sorted(runs, key=lambda item: item.get("finished_at", ""), reverse=True)[:25]:
            lines.append(
                f"  {run.get('finished_at', '')} · {run.get('slot_type', '')} · "
                f"{run.get('status', '')} · {run.get('stories_used', 0)} stories"
            )
        return lines

    if report_key == "failed_runs":
        lines = ["Failed Runs", ""]
        failed = [run for run in runs if run.get("status") != "success"]
        if not failed:
            lines.append("  No failed runs recorded.")
            return lines
        for run in failed[:25]:
            lines.append(f"  {run.get('finished_at', '')} · {run.get('message', run.get('status', ''))}")
        return lines

    if report_key == "feed_reliability":
        lines = ["Feed Reliability", ""]
        if not sources:
            lines.append("  No RSS sources configured.")
            return lines
        for source in sources:
            feed_key = source.get("id", "")
            stats = reliability.get(feed_key, {})
            status = source.get("last_test_status") or stats.get("status", "unknown")
            lines.append(
                f"  {source.get('name', '')}: {status} · last update {source.get('last_successful_update') or '—'}"
            )
        return lines

    if report_key == "stories_used":
        lines = ["Stories Used", ""]
        if not runs:
            lines.append("  No story usage recorded.")
            return lines
        total = sum(int(run.get("stories_used", 0) or 0) for run in runs)
        lines.append(f"  Total stories used across runs: {total}")
        for run in sorted(runs, key=lambda item: item.get("finished_at", ""), reverse=True)[:15]:
            lines.append(f"  {run.get('finished_at', '')}: {run.get('stories_used', 0)} stories")
        return lines

    if report_key == "duplicate_stories":
        lines = ["Duplicate Stories", ""]
        duplicates = _duplicate_feed_keys(sources) + _duplicate_story_titles(sources)
        if not duplicates:
            lines.append("  No duplicate story sources detected.")
            return lines
        for item in duplicates:
            lines.append(f"  {item}")
        return lines

    if report_key == "last_successful_output":
        lines = ["Last Successful Output", ""]
        successful = [run for run in runs if run.get("status") == "success"]
        if not successful:
            lines.append("  No successful output recorded.")
            return lines
        latest = sorted(successful, key=lambda item: item.get("finished_at", ""), reverse=True)[0]
        lines.append(f"  Finished: {latest.get('finished_at', '')}")
        lines.append(f"  Slot: {latest.get('slot_type', '')}")
        lines.append(f"  Output: {latest.get('output_file', '—')}")
        return lines

    return [f"Unknown report: {report_key}"]

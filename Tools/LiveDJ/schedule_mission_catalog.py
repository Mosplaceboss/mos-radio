"""Mission categories and custom missions for LiveDJ Schedule editor."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

MPR_ROOT = Path(r"D:\MPR")
CATEGORIES_FILE = MPR_ROOT / "Config" / "schedule_mission_categories.json"
CUSTOM_FILE = MPR_ROOT / "Config" / "custom_schedule_missions.json"

EVENT_TYPE_TO_CATEGORY: dict[str, str] = {
    "Show Open": "Welcome / Show Open",
    "Check-In": "General Check-In",
    "Weekend Check-In": "Weekend",
    "Artist Spotlight": "Artist Spotlight",
    "Music Story": "Music Story",
    "This Day in Music History": "Music History",
    "On This Day in the 70s": "Music History",
    "Coming Up": "General Check-In",
    "Coming Up Next": "General Check-In",
    "Today's Countdown": "Music History",
    "Final Half Hour": "Time of Day",
    "Listener Memory": "Listener Memory",
    "Format Change": "Format Change",
    "Handoff": "DJ Handoff",
    "Show Close": "Show Close",
    "Community Mention": "Community Mention",
    "Request Reminder": "Requests",
    "News Check-In": "General Check-In",
}

DEFAULT_CATEGORIES: dict[str, list[str]] = {
    "Welcome / Show Open": [
        "Welcome listeners and introduce the show.",
        "Set the mood for the current music format.",
        "Preview what listeners can expect during the show.",
        "Introduce the DJ and invite listeners to stay tuned.",
        "Open the show with energy and a clear sense of direction.",
    ],
    "General Check-In": [
        "Reconnect with listeners and keep the show moving.",
        "Give a natural time check and look ahead.",
        "Maintain the live-radio feel between songs.",
        "Remind listeners who they are listening to.",
        "Tease upcoming music without listing too many songs.",
    ],
    "Music Story": [
        "Share a short story connected to the upcoming artist or song.",
        "Add interesting context before the next song.",
        "Explain why the song or artist is memorable.",
        "Connect the music to its era.",
        "Share a brief behind-the-scenes music fact.",
    ],
    "Artist Spotlight": [
        "Highlight an important moment in the artist's career.",
        "Mention what makes the artist's sound recognizable.",
        "Share a short fact about the artist.",
        "Connect the artist to another familiar song or album.",
        "Introduce the artist to listeners who may not know them well.",
    ],
    "Song Background": [
        "Explain what the upcoming song is about.",
        "Share when the song was released and why it mattered.",
        "Mention an interesting fact about the recording.",
        "Describe the mood or message of the song.",
        "Connect the song to a memorable time or place.",
    ],
    "Music History": [
        "Share one This Day in Music History fact from the supplied factual source only. Do not invent history.",
        "Share a music-history moment connected to this date using only supplied facts.",
        "Mention an important album, concert, or chart achievement from the supplied source only.",
        "Connect the upcoming song to a larger music trend without inventing details.",
        "Give listeners a short look back at the music of the time using only verified context.",
        "Look back on this calendar date in the 1970s. Share three facts from the supplied 1970-1979 source only. Do not invent history.",
    ],
    "Listener Memory": [
        "Encourage listeners to connect the song with a personal memory.",
        "Share a relatable memory tied to the era.",
        "Ask listeners where they were when they first heard this music.",
        "Create a nostalgic moment before the next song.",
        "Connect the song to summer, school, travel, family, or friends.",
    ],
    "Time of Day": [
        "Acknowledge the current time of day and match the mood.",
        "Give listeners a natural morning check-in.",
        "Help listeners settle into the afternoon.",
        "Keep the energy moving into the evening.",
        "Recognize listeners working early, late, or overnight.",
    ],
    "Weekend": [
        "Welcome listeners into the weekend.",
        "Match the break to a relaxed Saturday or Sunday mood.",
        "Mention common weekend plans without asking a direct question.",
        "Create a backyard, road trip, beach, or pool atmosphere.",
        "Help listeners ease into the rest of the weekend.",
    ],
    "Local / New England": [
        "Add a light New England reference.",
        "Mention the local season, weather mood, or weekend atmosphere.",
        "Connect the music to Boston or New England life.",
        "Recognize listeners around the Merrimack Valley.",
        "Add a familiar local touch without turning it into a news report.",
    ],
    "Requests": [
        "Remind listeners that requests are open.",
        "Encourage listeners to submit a request through the website.",
        "Introduce an upcoming listener request.",
        "Thank listeners for helping shape the music.",
        "Mention request availability without interrupting the flow.",
    ],
    "Community Mention": [
        "Highlight a local event or community activity.",
        "Give a short community reminder.",
        "Recognize a local business, fundraiser, or organization.",
        "Encourage community support in a natural way.",
        "Share a brief local announcement and return to the music.",
    ],
    "Format Change": [
        "Acknowledge that the music format is changing.",
        "Explain the transition to the next style of music.",
        "Reset the mood for the next programming block.",
        "Introduce the new format without sounding formal.",
        "Connect the outgoing format to the incoming format.",
    ],
    "DJ Handoff": [
        "Close the current DJ's segment and introduce the next DJ.",
        "Thank listeners and preview what the next DJ will bring.",
        "Make the transition sound live and natural.",
        "Clearly identify who is leaving and who is taking over.",
        "Keep the handoff brief and upbeat.",
    ],
    "Show Close": [
        "Thank listeners and close the show.",
        "Wrap up the current format and identify what follows.",
        "End with a natural final thought.",
        "Hand off to the next show or DJ.",
        "Leave listeners with a warm station reminder.",
    ],
    "Custom": [
        "Write my own mission.",
        "Save this mission for future use.",
    ],
}


@dataclass(frozen=True)
class MissionOption:
    label: str
    text: str
    custom_id: str = ""
    is_custom: bool = False


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def ensure_catalog_files() -> None:
    if not CATEGORIES_FILE.is_file():
        _write_json(
            CATEGORIES_FILE,
            {
                "version": 1,
                "description": "LiveDJ mission categories and ready-to-use objectives.",
                "categories": DEFAULT_CATEGORIES,
            },
        )
    if not CUSTOM_FILE.is_file():
        _write_json(CUSTOM_FILE, {"version": 1, "missions": []})


def load_builtin_categories() -> dict[str, list[str]]:
    ensure_catalog_files()
    data = _read_json(CATEGORIES_FILE)
    categories = data.get("categories") or DEFAULT_CATEGORIES
    result: dict[str, list[str]] = {}
    for name, items in categories.items():
        if isinstance(items, list):
            result[str(name)] = [str(item).strip() for item in items if str(item).strip()]
    if not result:
        return dict(DEFAULT_CATEGORIES)
    return result


def load_custom_missions() -> list[dict[str, Any]]:
    ensure_catalog_files()
    data = _read_json(CUSTOM_FILE)
    missions = data.get("missions", [])
    return [item for item in missions if isinstance(item, dict)]


def save_custom_missions(missions: list[dict[str, Any]]) -> None:
    _write_json(CUSTOM_FILE, {"version": 1, "missions": missions})


def mission_categories() -> list[str]:
    builtin = load_builtin_categories()
    order = list(builtin.keys())
    if "Custom" in order:
        order.remove("Custom")
        order.append("Custom")
    return order


def category_for_event_type(event_type: str) -> str:
    return EVENT_TYPE_TO_CATEGORY.get(str(event_type or "").strip(), "General Check-In")


def options_for_category(category: str) -> list[MissionOption]:
    category = str(category or "").strip()
    options: list[MissionOption] = []
    builtin = load_builtin_categories()
    for index, text in enumerate(builtin.get(category, [])):
        if category == "Custom" and text.lower().startswith("write my own"):
            continue
        if category == "Custom" and text.lower().startswith("save this mission"):
            continue
        short = text if len(text) <= 70 else text[:67] + "…"
        options.append(MissionOption(label=f"{index + 1}. {short}", text=text, is_custom=False))

    for item in load_custom_missions():
        if str(item.get("category") or "").strip() != category:
            continue
        label = str(item.get("label") or item.get("text") or "Custom mission").strip()
        text = str(item.get("text") or "").strip()
        custom_id = str(item.get("id") or "").strip()
        if text and custom_id:
            options.append(
                MissionOption(
                    label=f"★ {label}",
                    text=text,
                    custom_id=custom_id,
                    is_custom=True,
                )
            )
    return options


def default_option_for_category(category: str) -> MissionOption | None:
    options = options_for_category(category)
    return options[0] if options else None


def find_match_for_mission_text(mission_text: str) -> tuple[str, MissionOption | None]:
    text = str(mission_text or "").strip()
    if not text:
        return "General Check-In", None
    for category in mission_categories():
        for option in options_for_category(category):
            if option.text.strip() == text:
                return category, option
    return "Custom", None


def add_custom_mission(*, category: str, label: str, text: str) -> MissionOption:
    missions = load_custom_missions()
    custom_id = uuid.uuid4().hex[:12]
    entry = {
        "id": custom_id,
        "category": str(category or "Custom").strip(),
        "label": str(label or "My mission").strip() or "My mission",
        "text": str(text or "").strip(),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    missions.append(entry)
    save_custom_missions(missions)
    return MissionOption(label=f"★ {entry['label']}", text=entry["text"], custom_id=custom_id, is_custom=True)


def delete_custom_mission(custom_id: str) -> bool:
    missions = load_custom_missions()
    kept = [item for item in missions if str(item.get("id") or "") != custom_id]
    if len(kept) == len(missions):
        return False
    save_custom_missions(kept)
    return True


def get_custom_mission(custom_id: str) -> dict[str, Any] | None:
    for item in load_custom_missions():
        if str(item.get("id") or "") == custom_id:
            return dict(item)
    return None


def time_options_15min() -> list[str]:
    return [f"{hour:02d}:{minute:02d}" for hour in range(24) for minute in (0, 15, 30, 45)]

"""Mission category catalog — built-in objectives and user custom missions."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

_MPR_ROOT = Path(r"D:\MPR")
_CATEGORIES_FILE = _MPR_ROOT / "Config" / "schedule_mission_categories.json"
_CUSTOM_FILE = _MPR_ROOT / "Config" / "custom_schedule_missions.json"

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


def load_builtin_categories() -> dict[str, list[str]]:
    data = _read_json(_CATEGORIES_FILE)
    categories = data.get("categories", {})
    result: dict[str, list[str]] = {}
    for name, items in categories.items():
        if isinstance(items, list):
            result[str(name)] = [str(item).strip() for item in items if str(item).strip()]
    return result


def load_custom_missions() -> list[dict[str, Any]]:
    data = _read_json(_CUSTOM_FILE)
    missions = data.get("missions", [])
    return [item for item in missions if isinstance(item, dict)]


def save_custom_missions(missions: list[dict[str, Any]]) -> None:
    _write_json(_CUSTOM_FILE, {"version": 1, "missions": missions})


def mission_categories() -> list[str]:
    builtin = load_builtin_categories()
    order = list(builtin.keys())
    if "Custom" in order:
        order.remove("Custom")
        order.append("Custom")
    return order


def category_for_event_type(event_type: str) -> str:
    return EVENT_TYPE_TO_CATEGORY.get(str(event_type or "").strip(), "General Check-In")


def _option_label(text: str, index: int) -> str:
    short = text if len(text) <= 72 else text[:69] + "…"
    return f"{index + 1}. {short}"


def options_for_category(category: str) -> list[MissionOption]:
    category = str(category or "").strip()
    options: list[MissionOption] = []
    builtin = load_builtin_categories()
    for index, text in enumerate(builtin.get(category, [])):
        if category == "Custom" and text.lower().startswith("write my own"):
            continue
        options.append(MissionOption(label=_option_label(text, index), text=text, is_custom=False))

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
    if not options:
        return None
    if category == "Custom":
        return options[0] if options else None
    for option in options:
        if option.text and not option.text.lower().startswith("save this mission"):
            return option
    return options[0]


def find_match_for_mission_text(mission_text: str) -> tuple[str, MissionOption | None]:
    text = str(mission_text or "").strip()
    if not text:
        return "General Check-In", None
    for category in mission_categories():
        for option in options_for_category(category):
            if option.text.strip() == text:
                return category, option
    for category in mission_categories():
        for option in options_for_category(category):
            if text.lower() in option.text.lower() or option.text.lower() in text.lower():
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


def update_custom_mission(custom_id: str, *, category: str, label: str, text: str) -> bool:
    missions = load_custom_missions()
    updated = False
    for item in missions:
        if str(item.get("id") or "") == custom_id:
            item["category"] = str(category or "Custom").strip()
            item["label"] = str(label or "My mission").strip()
            item["text"] = str(text or "").strip()
            item["updated_at"] = datetime.now().isoformat(timespec="seconds")
            updated = True
            break
    if updated:
        save_custom_missions(missions)
    return updated


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

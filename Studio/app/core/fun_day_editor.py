"""Edit Fun Day fields for the Fun / National Days panel.

The form rows match the studio screen: title, when, date, days of the month,
who says it, selected DJs, note, and enabled. Category is the extra choice
on that same panel.
"""

from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_LIVEDJ = Path(__file__).resolve().parents[3] / "Tools" / "LiveDJ"
if str(_LIVEDJ) not in sys.path:
    sys.path.insert(0, str(_LIVEDJ))

FunDays = importlib.import_module("FunDays")

CATEGORY_CHOICES = FunDays.CATEGORY_LABELS

WHEN_CHOICES = ("One-day", "Whole month", "Selected days")
WHO_CHOICES = ("Each DJ, each day", "Only selected DJs")


@dataclass(frozen=True)
class FormField:
    """One row on Edit Fun Day."""

    label: str
    key: str
    kind: str
    choices: tuple[str, ...] = ()


# Same order as the studio form, with Category under the title.
FORM_FIELDS: tuple[FormField, ...] = (
    FormField("Title (e.g. Breast Cancer Awareness Month)", "title", "entry"),
    FormField("Category", "category", "choice", CATEGORY_CHOICES),
    FormField("When", "when", "choice", WHEN_CHOICES),
    FormField("Date or month (February 22, October, or 2nd Sunday of October)", "date", "entry"),
    FormField("Days of the month, only if Selected days (1, 15, 20)", "days_of_month", "entry"),
    FormField("Who says it", "who", "choice", WHO_CHOICES),
    FormField("Selected DJs, comma separated (only if Only selected DJs)", "selected_djs", "entry"),
    FormField("Read by (one-day items)", "read_by", "entry"),
    FormField("Note for the DJ (optional)", "note", "entry"),
    FormField("Enabled", "enabled", "check"),
)


def category_field() -> FormField:
    for field in FORM_FIELDS:
        if field.key == "category":
            return field
    raise RuntimeError("Edit Fun Day is missing Category")


def _when_choice(value: str) -> str:
    text = str(value or "").strip()
    lower = text.lower()
    if "selected" in lower:
        return "Selected days"
    if lower in {"month", "whole month", "all month", "every day", "all the days", "all days"} or "whole month" in lower:
        return "Whole month"
    if text in WHEN_CHOICES:
        return text
    return "One-day"


def _who_choice(value: str) -> str:
    text = str(value or "").strip().lower()
    if "selected" in text or text.startswith("only "):
        return "Only selected DJs"
    return "Each DJ, each day"


def form_values(record: dict | None) -> dict[str, Any]:
    """What Edit Fun Day shows when this row is selected.

    Category is the combobox label: Funny, Regular, or Serious.
    A stored Breast Cancer Awareness Month with no category shows Serious.
    Every other day with no category shows Funny. fun and Fun Day show as Funny.
    serious and Serious Day show as Serious.
    """
    day = FunDays.normalize_day(record or {})
    return {
        "title": day["title"],
        "category": FunDays.category_label(day["category"]),
        "when": _when_choice(day["when"]),
        "date": day["date"],
        "days_of_month": day["days_of_month"],
        "who": _who_choice(day["who"]),
        "selected_djs": day["selected_djs"],
        "read_by": day["read_by"],
        "note": day["note"],
        "enabled": bool(day["enabled"]),
    }


def record_from_form(values: dict[str, Any], previous: dict | None = None) -> dict:
    """Saved observance. The Category choice on the form is stored as category."""
    raw = dict(previous or {})
    raw["title"] = str(values.get("title") or "").strip()
    token = FunDays.stored_category_token(str(values.get("category") or ""))
    if token:
        raw["category"] = token
    else:
        raw.pop("category", None)
        raw.pop("Category", None)
    raw["when"] = str(values.get("when") or "One-day").strip() or "One-day"
    raw["date"] = str(values.get("date") or "").strip()
    raw["days_of_month"] = str(values.get("days_of_month") or "").strip()
    raw["who"] = str(values.get("who") or "Each DJ, each day").strip() or "Each DJ, each day"
    raw["selected_djs"] = str(values.get("selected_djs") or "").strip()
    raw["read_by"] = str(values.get("read_by") or "").strip()
    raw["note"] = str(values.get("note") or "").strip()
    raw["enabled"] = bool(values.get("enabled", True))
    return FunDays.normalize_day(raw)

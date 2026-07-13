"""Website & Audience Manager models."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any
from uuid import uuid4

from app.core.health_constants import HEALTH_OK
from app.core.platform_manager import platform_path, test_platform_path
from app.core.website_audience_storage import load_website_bundle, save_website_bundle, website_state_path

DEFAULT_SEGMENTS = ("Listeners", "Contest Entrants", "Newsletter", "Mobile App", "Social Followers")


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


def default_segments() -> list[dict[str, Any]]:
    return [{"id": _new_id("seg"), "name": name, "enabled": True, "notes": ""} for name in DEFAULT_SEGMENTS]


def normalize_bundle(data: dict[str, Any] | None) -> dict[str, Any]:
    payload = data or {}
    audience = payload.get("audience", {})
    segments = audience.get("segments", []) if audience else []
    if not segments:
        segments = default_segments()
    return {
        "content": payload.get("content", {"pages": [], "posts": []}),
        "audience": {
            "segments": segments,
            "newsletter_enabled": audience.get("newsletter_enabled", False) if audience else False,
            "social_links": audience.get("social_links", {}) if audience else {},
        },
        "schedule": payload.get(
            "schedule",
            {"publish_slots": [], "timezone": "America/New_York"},
        ),
        "state": payload.get("state", {"last_validated": "", "version": 1}),
    }


def ensure_website_audience_data(config_manager=None) -> None:
    if website_state_path(config_manager).exists():
        return
    save_website_bundle(normalize_bundle({}), config_manager)


def validate_website(bundle: dict[str, Any], config_manager=None) -> list[str]:
    warnings: list[str] = []
    website_folder = platform_path("website", config_manager)
    automation = platform_path("automation_website", config_manager)
    for label, path in (("Website content", website_folder), ("Website automation", automation)):
        result = test_platform_path("website", str(path))
        if result["status"] != HEALTH_OK:
            warnings.append(f"{label}: {result['message']}")
    if not bundle["audience"]["segments"]:
        warnings.append("No audience segments configured.")
    return warnings


def build_overview_lines(bundle: dict[str, Any], config_manager=None) -> list[str]:
    warnings = validate_website(bundle, config_manager)
    lines = [
        f"Content items: {len(bundle['content'].get('pages', []))} pages, {len(bundle['content'].get('posts', []))} posts",
        f"Audience segments: {len(bundle['audience']['segments'])}",
        f"Publish slots: {len(bundle['schedule'].get('publish_slots', []))}",
        f"Last validated: {bundle['state'].get('last_validated') or 'Never'}",
        "",
        "Alerts:",
    ]
    if warnings:
        lines.extend(f"• {line}" for line in warnings)
    else:
        lines.append("• No warnings.")
    return lines

"""Advertising Manager models."""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import uuid4

from app.core.advertising_storage import advertising_state_path, load_advertising_bundle, save_advertising_bundle
from app.core.health_constants import HEALTH_OK
from app.core.platform_manager import platform_path, test_platform_path

DEFAULT_SPONSORS = (
    "Local Business Spotlight",
    "Restaurant Partner",
    "Event Sponsor",
    "Community Partner",
)


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


def default_sponsors() -> list[dict[str, Any]]:
    return [
        {"id": _new_id("sp"), "name": name, "enabled": True, "contact": "", "notes": ""}
        for name in DEFAULT_SPONSORS
    ]


def normalize_bundle(data: dict[str, Any] | None) -> dict[str, Any]:
    payload = data or {}
    sponsors = payload.get("sponsors", {}).get("sponsors", []) if payload.get("sponsors") else []
    if not sponsors:
        sponsors = default_sponsors()
    campaigns = payload.get("campaigns", {}).get("campaigns", []) if payload.get("campaigns") else []
    return {
        "sponsors": {"sponsors": sponsors},
        "campaigns": {"campaigns": campaigns},
        "state": payload.get("state", {"last_validated": "", "version": 1}),
    }


def ensure_advertising_data(config_manager=None) -> None:
    if advertising_state_path(config_manager).exists():
        return
    save_advertising_bundle(normalize_bundle({}), config_manager)


def validate_advertising(bundle: dict[str, Any], config_manager=None) -> list[str]:
    warnings: list[str] = []
    folder = platform_path("automation_advertising", config_manager)
    result = test_platform_path("automation_advertising", str(folder))
    if result["status"] != HEALTH_OK:
        warnings.append(f"Advertising folder: {result['message']}")
    enabled = [s for s in bundle["sponsors"]["sponsors"] if s.get("enabled")]
    if not enabled:
        warnings.append("No active sponsors configured.")
    return warnings


def build_overview_lines(bundle: dict[str, Any], config_manager=None) -> list[str]:
    warnings = validate_advertising(bundle, config_manager)
    active = sum(1 for s in bundle["sponsors"]["sponsors"] if s.get("enabled"))
    lines = [
        f"Sponsors: {len(bundle['sponsors']['sponsors'])} total, {active} active",
        f"Campaigns: {len(bundle['campaigns']['campaigns'])}",
        "",
        "Alerts:",
    ]
    if warnings:
        lines.extend(f"• {line}" for line in warnings)
    else:
        lines.append("• No warnings.")
    return lines

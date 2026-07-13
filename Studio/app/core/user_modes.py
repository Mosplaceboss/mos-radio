"""Operating modes: Owner, Staff, and Advanced."""

from __future__ import annotations

from typing import Any

USER_MODE_OWNER = "owner"
USER_MODE_STAFF = "staff"
USER_MODE_ADVANCED = "advanced"

USER_MODES = (USER_MODE_OWNER, USER_MODE_STAFF, USER_MODE_ADVANCED)

DEFAULT_ADVANCED_PASSWORD = "moplace"

STAFF_VISIBLE_PAGES = frozenset(
    {
        "daily_operations",
        "help",
        "schedule",
        "personalities",
        "voice_library",
        "requests",
        "settings",
    }
)

OWNER_HIDDEN_PAGES = frozenset(
    {
        "platform_manager",
        "advanced",
        "connection",
        "livedj",
        "automation",
        "news",
        "setup_wizard",
        "updates",
    }
)

ADVANCED_ONLY_PAGES = frozenset(
    {
        "platform_manager",
        "advanced",
        "connection",
        "livedj",
        "automation",
        "news",
        "setup_wizard",
        "updates",
    }
)


def user_mode(settings: dict[str, Any] | None) -> str:
    data = settings or {}
    mode = str(data.get("user_mode", USER_MODE_OWNER)).strip().lower()
    if mode in USER_MODES:
        return mode
    return USER_MODE_OWNER


def is_staff_mode(settings: dict[str, Any] | None) -> bool:
    return user_mode(settings) == USER_MODE_STAFF


def is_advanced_mode(settings: dict[str, Any] | None) -> bool:
    return user_mode(settings) == USER_MODE_ADVANCED


def advanced_password(settings: dict[str, Any] | None) -> str:
    data = settings or {}
    password = str(data.get("advanced_password", "")).strip()
    return password or DEFAULT_ADVANCED_PASSWORD


def verify_advanced_password(settings: dict[str, Any] | None, entered: str) -> bool:
    return entered.strip() == advanced_password(settings)


def page_allowed(page_id: str, settings: dict[str, Any] | None) -> bool:
    mode = user_mode(settings)
    if mode == USER_MODE_ADVANCED:
        return True
    if mode == USER_MODE_STAFF:
        return page_id in STAFF_VISIBLE_PAGES
    if page_id in OWNER_HIDDEN_PAGES:
        return False
    return True


def visible_nav_items(nav_items: tuple[tuple[str, str], ...], settings: dict[str, Any] | None) -> tuple[tuple[str, str], ...]:
    return tuple(item for item in nav_items if page_allowed(item[0], settings))


def visible_nav_sections(
    sections: tuple[tuple[str, tuple[str, ...]], ...],
    settings: dict[str, Any] | None,
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    filtered: list[tuple[str, tuple[str, ...]]] = []
    for title, page_ids in sections:
        ids = tuple(page_id for page_id in page_ids if page_allowed(page_id, settings))
        if ids:
            filtered.append((title, ids))
    return tuple(filtered)


def mode_label(settings: dict[str, Any] | None) -> str:
    mode = user_mode(settings)
    return {
        USER_MODE_OWNER: "Owner Mode",
        USER_MODE_STAFF: "Staff Mode",
        USER_MODE_ADVANCED: "Advanced Mode",
    }.get(mode, "Owner Mode")


def show_git_metadata(settings: dict[str, Any] | None) -> bool:
    return is_advanced_mode(settings)

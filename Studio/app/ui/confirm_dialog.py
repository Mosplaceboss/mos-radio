"""Reusable confirmation dialogs for operational safety."""

from __future__ import annotations

from typing import Any

from ttkbootstrap.dialogs import Messagebox

from app.core.integration_settings import is_production_mode


def confirm_action(title: str, message: str, settings: dict[str, Any] | None = None) -> bool:
    if not Messagebox.yesno(message, title=title):
        return False
    if settings and is_production_mode(settings):
        return Messagebox.yesno(
            f"PRODUCTION MODE — confirm again:\n\n{message}",
            title="Confirm Production Action",
        )
    return True

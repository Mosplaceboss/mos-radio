"""Studio application metadata (version, git, profile, environment)."""

from __future__ import annotations

import sys
from typing import Any

from app.core.hidden_process import read_git_commit_short
from app.core.integration_settings import operation_mode
from app.core.paths import studio_root

APP_VERSION = "1.0.0"


def environment_mode(settings: dict[str, Any] | None = None) -> str:
    if settings:
        mode = operation_mode(settings)
        return "Production" if mode == "production" else "Development"
    return "Production" if getattr(sys, "frozen", False) else "Development"


def git_commit_short() -> str:
    return read_git_commit_short(studio_root().parent)


def current_profile(settings: dict[str, Any] | None = None) -> str:
    data = settings or {}
    return data.get("station_name", "Mo's Place Radio")


def environment_badge(settings: dict[str, Any] | None = None) -> tuple[str, str]:
    mode = environment_mode(settings)
    if mode == "Production":
        return "On Air", "success"
    return "Setup Mode", "warning"


def status_bar_summary(settings: dict[str, Any] | None = None) -> str:
    profile = current_profile(settings)
    if getattr(sys, "frozen", False):
        return f"Mo's Place Studio v{APP_VERSION}  ·  {profile}"
    mode = environment_mode(settings)
    if mode == "Production":
        return f"Mo's Place Studio v{APP_VERSION}  ·  {profile}  ·  On Air"
    return (
        f"Mo's Place Studio v{APP_VERSION}  ·  {profile}  ·  "
        f"Setup  ·  Git {git_commit_short()}"
    )

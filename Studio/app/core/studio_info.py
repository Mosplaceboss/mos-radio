"""Studio application metadata (version, git, profile, environment)."""

from __future__ import annotations

import sys
from typing import Any

from app.core.hidden_process import read_git_commit_short
from app.core.integration_settings import operation_mode
from app.core.paths import studio_root
from app.core.user_modes import mode_label, show_git_metadata

APP_VERSION = "2.0.0-rc1"
APP_VERSION_LABEL = "Mo's Place Studio v2.0 Release Candidate"


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
    role = mode_label(settings)
    if getattr(sys, "frozen", False):
        return f"{APP_VERSION_LABEL}  ·  {profile}  ·  {role}"
    mode = environment_mode(settings)
    if mode == "Production":
        return f"{APP_VERSION_LABEL}  ·  {profile}  ·  {role}  ·  On Air"
    if show_git_metadata(settings):
        return (
            f"{APP_VERSION_LABEL}  ·  {profile}  ·  {role}  ·  "
            f"Setup  ·  Git {git_commit_short()}"
        )
    return f"{APP_VERSION_LABEL}  ·  {profile}  ·  {role}  ·  Setup"

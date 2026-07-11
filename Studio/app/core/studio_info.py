"""Studio application metadata (version, git, profile, environment)."""

from __future__ import annotations

import subprocess
import sys
from typing import Any

from app.core.paths import studio_root

APP_VERSION = "1.0.0"


def environment_mode() -> str:
    return "Production" if getattr(sys, "frozen", False) else "Development"


def git_commit_short() -> str:
    repo = studio_root().parent
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if result.returncode == 0:
            commit = result.stdout.strip()
            if commit:
                return commit
    except (OSError, subprocess.SubprocessError):
        pass
    return "unknown"


def current_profile(settings: dict[str, Any] | None = None) -> str:
    data = settings or {}
    return data.get("station_name", "Mo's Place Radio")


def status_bar_summary(settings: dict[str, Any] | None = None) -> str:
    profile = current_profile(settings)
    return (
        f"Mo's Place Studio v{APP_VERSION}  ·  Git {git_commit_short()}  ·  "
        f"Profile: {profile}  ·  {environment_mode()} Mode"
    )

"""Install News launcher files into the live Automation/News folder.

Studio owns these scripts the same way it publishes news.json. Opening Studio
or clicking Run News Now copies them into the configured news folder — the
operator does not copy files by hand.

Never touches engine.local.cmd, news.json, news_copy.txt, bulletin.txt, or logs.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from app.core.paths import resource_root, studio_root

LOGGER = logging.getLogger("moplace.studio.news_runtime")

# Files Studio keeps current in Automation/News.
MANAGED_NEWS_FILES = (
    "run_news_now.bat",
    "build_bulletin.bat",
    "build_bulletin.py",
)


def news_runtime_template_dir() -> Path | None:
    """Bundled templates shipped with Studio (source tree or EXE package)."""
    candidates = (
        resource_root() / "runtime" / "News",
        studio_root() / "runtime" / "News",
        studio_root().parent / "Automation" / "News",
    )
    for path in candidates:
        if (path / "run_news_now.bat").is_file() and (path / "build_bulletin.py").is_file():
            return path
    return None


def ensure_news_runtime_scripts(news_dir: Path | None = None) -> tuple[bool, str]:
    """Copy managed News launcher files into the live news folder."""
    if news_dir is None:
        from app.core.platform_manager import platform_path

        news_dir = platform_path("automation_news")
    destination = Path(news_dir)
    template_dir = news_runtime_template_dir()
    if template_dir is None:
        return False, "News runtime templates were not found beside Studio."

    try:
        destination.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return False, f"Could not create news folder {destination}: {exc}"

    # Do not copy a folder onto itself (git checkout already has the files).
    if template_dir.resolve() == destination.resolve():
        return True, f"News launcher already live at {destination}"

    updated: list[str] = []
    for name in MANAGED_NEWS_FILES:
        source = template_dir / name
        if not source.is_file():
            continue
        target = destination / name
        try:
            if target.is_file() and source.read_bytes() == target.read_bytes():
                continue
            shutil.copy2(source, target)
            updated.append(name)
        except OSError as exc:
            return False, f"Could not install {name} into {destination}: {exc}"

    if updated:
        message = f"Installed news launcher ({', '.join(updated)}) into {destination}"
        LOGGER.info(message)
        return True, message
    return True, f"News launcher already current in {destination}"

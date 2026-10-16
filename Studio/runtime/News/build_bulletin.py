"""Thin launcher for Task Scheduler / run_news_now.bat.

Studio owns the bulletin builder. This file prefers the Studio Python package
on disk, then falls back to Studio.exe --build-news-bulletin for EXE installs.
Studio Run News Now installs this file into Automation/News automatically.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _news_dir() -> Path:
    return Path(__file__).resolve().parent


def _studio_candidates() -> list[Path]:
    here = _news_dir()
    return [
        here.parents[1] / "Studio",  # D:\\MosPlaceRadioPlatform\\Studio
        here.parents[2] / "Studio",  # repo checkout layout
    ]


def _bootstrap_studio_source() -> bool:
    for studio in _studio_candidates():
        if (studio / "app" / "core" / "news_bulletin.py").is_file():
            text = str(studio)
            if text not in sys.path:
                sys.path.insert(0, text)
            return True
    return False


def _studio_exe() -> Path | None:
    for studio in _studio_candidates():
        for name in ("Studio.exe", "MoPlaceStudio.exe"):
            candidate = studio / name
            if candidate.is_file():
                return candidate
    return None


def main(argv: list[str] | None = None) -> int:
    args = list(argv) if argv is not None else sys.argv[1:]
    if "--news-dir" not in args:
        args = ["--news-dir", str(_news_dir()), *args]

    if _bootstrap_studio_source():
        try:
            from app.core.news_bulletin import main as bulletin_main

            return bulletin_main(args)
        except ImportError:
            pass

    exe = _studio_exe()
    if exe is not None:
        completed = subprocess.run(
            [str(exe), "--build-news-bulletin", *args],
            cwd=str(_news_dir()),
            check=False,
        )
        return int(completed.returncode)

    print(
        "Could not import Studio news bulletin builder. "
        "Open Mo's Place Studio once so it can install the news launcher, "
        "or confirm Studio is installed beside the platform root.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

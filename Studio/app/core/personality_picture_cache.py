"""Cached personality picture thumbnails for fast Personalities display."""

from __future__ import annotations

import logging
from pathlib import Path
from threading import Lock

from PIL import Image

from app.core.paths import studio_root

logger = logging.getLogger("moplace.studio.personality_pictures")

THUMB_SIZE = (112, 112)
_cache: dict[str, Image.Image] = {}
_lock = Lock()


def resolve_personality_picture_path(picture: str) -> Path | None:
    if not picture:
        return None
    path = Path(picture)
    if path.is_absolute():
        return path
    return studio_root() / "assets" / picture


def cache_key(path: Path) -> str | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    return f"{path.resolve()}|{stat.st_mtime_ns}|{stat.st_size}"


def warm_thumbnail(path: Path, *, size: tuple[int, int] = THUMB_SIZE) -> tuple[bool, str | None]:
    key = cache_key(path)
    if key is None:
        return False, f"Picture file not accessible: {path}"

    with _lock:
        if key in _cache:
            return True, None

    try:
        with Image.open(path) as image:
            thumb = image.convert("RGBA")
            thumb.thumbnail(size, Image.Resampling.LANCZOS)
            prepared = thumb.copy()
    except OSError as exc:
        logger.warning("Failed to load personality picture %s: %s", path, exc)
        return False, f"Could not read picture: {path.name}"
    except Exception as exc:
        logger.warning("Failed to process personality picture %s: %s", path, exc)
        return False, f"Could not process picture: {path.name}"

    with _lock:
        _cache[key] = prepared
    return True, None


def get_thumbnail(path: Path) -> Image.Image | None:
    key = cache_key(path)
    if key is None:
        return None
    with _lock:
        cached = _cache.get(key)
        if cached is not None:
            return cached.copy()
    return None


def invalidate_path(path: Path) -> None:
    resolved = str(path.resolve())
    with _lock:
        stale = [key for key in _cache if key.startswith(resolved)]
        for key in stale:
            _cache.pop(key, None)

"""Music Manager data models, library scanning, validation, and reports."""

from __future__ import annotations

import hashlib
import re
import struct
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.music_storage import (
    catalog_path,
    load_music_bundle,
    save_music_bundle,
)
from app.core.platform_manager import platform_path

AUDIO_EXTENSIONS = frozenset(
    {".mp3", ".flac", ".wav", ".m4a", ".aac", ".ogg", ".wma", ".aiff", ".aif"}
)

ARTWORK_NAMES = (
    "folder.jpg",
    "folder.jpeg",
    "folder.png",
    "cover.jpg",
    "cover.jpeg",
    "cover.png",
    "album.jpg",
    "album.jpeg",
    "album.png",
    "front.jpg",
    "front.jpeg",
    "front.png",
)

DEFAULT_FORMATS = (
    "Classic Rock",
    "Daily Mix",
    "Trop Rock",
    "Blues",
    "Casey",
    "Christmas",
    "Future Formats",
)

DEFAULT_CATEGORIES = (
    ("gold", "Gold"),
    ("recurrent", "Recurrent"),
    ("current", "Current"),
    ("specialty", "Specialty"),
    ("instrumental", "Instrumental"),
    ("holiday", "Holiday"),
    ("local_artists", "Local Artists"),
    ("custom", "Custom"),
)

ID3_GENRES = (
    "Blues",
    "Classic Rock",
    "Country",
    "Dance",
    "Disco",
    "Funk",
    "Grunge",
    "Hip-Hop",
    "Jazz",
    "Metal",
    "New Age",
    "Oldies",
    "Other",
    "Pop",
    "R&B",
    "Rap",
    "Reggae",
    "Rock",
    "Techno",
    "Unknown",
)


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


def song_id_for_path(path: str) -> str:
    digest = hashlib.md5(path.lower().encode("utf-8", errors="replace")).hexdigest()[:12]
    return f"song-{digest}"


def format_bytes(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    if size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    return f"{size / (1024 * 1024 * 1024):.2f} GB"


def format_duration(seconds: int) -> str:
    if seconds <= 0:
        return "—"
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def default_formats() -> list[dict[str, Any]]:
    return [
        {
            "id": _new_id("fmt"),
            "name": name,
            "enabled": name != "Future Formats",
            "description": "",
        }
        for name in DEFAULT_FORMATS
    ]


def default_categories() -> list[dict[str, Any]]:
    return [
        {
            "id": key,
            "name": label,
            "enabled": True,
            "description": "",
        }
        for key, label in DEFAULT_CATEGORIES
    ]


def normalize_settings(data: dict[str, Any] | None, config_manager=None) -> dict[str, Any]:
    default_root = str(platform_path("music_library", config_manager))
    record = deepcopy(data) if data else {}
    record.setdefault("music_root", default_root)
    record.setdefault("last_scan_at", "")
    return record


def normalize_formats(data: dict[str, Any] | None) -> dict[str, Any]:
    formats = data.get("formats", []) if data else []
    if not formats:
        formats = default_formats()
    normalized = []
    for item in formats:
        record = deepcopy(item)
        record.setdefault("id", _new_id("fmt"))
        record.setdefault("name", "Format")
        record.setdefault("enabled", True)
        record.setdefault("description", "")
        normalized.append(record)
    return {"formats": normalized}


def normalize_categories(data: dict[str, Any] | None) -> dict[str, Any]:
    categories = data.get("categories", []) if data else []
    if not categories:
        categories = default_categories()
    normalized = []
    for item in categories:
        record = deepcopy(item)
        record.setdefault("id", _new_id("cat"))
        record.setdefault("name", "Category")
        record.setdefault("enabled", True)
        record.setdefault("description", "")
        normalized.append(record)
    return {"categories": normalized}


def normalize_playlists(data: dict[str, Any] | None) -> dict[str, Any]:
    playlists = data.get("playlists", []) if data else []
    normalized = []
    for item in playlists:
        record = deepcopy(item)
        record.setdefault("id", _new_id("pl"))
        record.setdefault("name", "Playlist")
        record.setdefault("description", "")
        record.setdefault("song_ids", [])
        record.setdefault("format_id", "")
        record.setdefault("archived", False)
        record.setdefault("created_at", "")
        normalized.append(record)
    return {"playlists": normalized}


def normalize_resources(data: dict[str, Any] | None) -> dict[str, Any]:
    resources = data.get("resources", {}) if data else {}
    if not isinstance(resources, dict):
        resources = {}
    normalized: dict[str, Any] = {}
    for song_id, item in resources.items():
        record = deepcopy(item) if isinstance(item, dict) else {}
        record.setdefault("album_art", "")
        record.setdefault("artist_image", "")
        record.setdefault("lyrics", "")
        record.setdefault("notes", "")
        record.setdefault("tags", [])
        normalized[song_id] = record
    return {"resources": normalized}


def normalize_song(item: dict[str, Any]) -> dict[str, Any]:
    record = deepcopy(item)
    path = record.get("file_path", "")
    record.setdefault("id", song_id_for_path(path) if path else _new_id("song"))
    record.setdefault("artist", "")
    record.setdefault("title", "")
    record.setdefault("album", "")
    record.setdefault("year", "")
    record.setdefault("genre", "")
    record.setdefault("length_seconds", 0)
    record.setdefault("file_path", "")
    record.setdefault("file_size", 0)
    record.setdefault("artwork_path", "")
    record.setdefault("format_ids", [])
    record.setdefault("category_ids", [])
    record.setdefault("added_at", "")
    record.setdefault("last_seen_at", "")
    record.setdefault("missing_file", False)
    return record


def normalize_catalog(data: dict[str, Any] | None) -> dict[str, Any]:
    songs = data.get("songs", []) if data else []
    normalized = [normalize_song(item) for item in songs]
    return {
        "songs": normalized,
        "last_scan_at": data.get("last_scan_at", "") if data else "",
    }


def normalize_bundle(data: dict[str, Any] | None, config_manager=None) -> dict[str, Any]:
    payload = data or {}
    return {
        "settings": normalize_settings(payload.get("settings"), config_manager),
        "catalog": normalize_catalog(payload.get("catalog")),
        "formats": normalize_formats(payload.get("formats")),
        "playlists": normalize_playlists(payload.get("playlists")),
        "categories": normalize_categories(payload.get("categories")),
        "resources": normalize_resources(payload.get("resources")),
        "state": payload.get("state", {"last_validated": "", "version": 1}),
    }


def ensure_music_data(config_manager=None) -> None:
    if not catalog_path(config_manager).exists():
        normalized = normalize_bundle({}, config_manager)
        save_music_bundle(normalized, config_manager)


def _parse_filename(stem: str) -> tuple[str, str, str]:
    parts = [part.strip() for part in re.split(r"\s*[-–—]\s*", stem) if part.strip()]
    if len(parts) >= 3:
        return parts[0], parts[1], parts[2]
    if len(parts) == 2:
        return parts[0], "", parts[1]
    return "", "", stem


def _read_id3v1(path: Path) -> dict[str, str]:
    tags: dict[str, str] = {}
    try:
        with path.open("rb") as handle:
            handle.seek(-128, 2)
            block = handle.read(128)
    except OSError:
        return tags
    if len(block) != 128 or block[:3] != b"TAG":
        return tags
    title = block[3:33].decode("latin-1", errors="replace").strip("\x00 ").strip()
    artist = block[33:63].decode("latin-1", errors="replace").strip("\x00 ").strip()
    album = block[63:93].decode("latin-1", errors="replace").strip("\x00 ").strip()
    year = block[93:97].decode("latin-1", errors="replace").strip("\x00 ").strip()
    genre_index = block[127]
    genre = ID3_GENRES[genre_index] if genre_index < len(ID3_GENRES) else "Unknown"
    if title:
        tags["title"] = title
    if artist:
        tags["artist"] = artist
    if album:
        tags["album"] = album
    if year:
        tags["year"] = year
    if genre and genre != "Unknown":
        tags["genre"] = genre
    return tags


def _estimate_mp3_duration(path: Path) -> int:
    try:
        with path.open("rb") as handle:
            handle.seek(0, 2)
            file_size = handle.tell()
            if file_size < 128:
                return 0
            handle.seek(0)
            while True:
                header = handle.read(4)
                if len(header) < 4:
                    return 0
                if header[:2] != b"\xff\xfb" and header[:2] != b"\xff\xfa" and header[:2] != b"\xff\xf3":
                    continue
                bitrate_index = (header[2] >> 4) & 0x0F
                sample_index = (header[2] >> 2) & 0x03
                bitrates = [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0]
                sample_rates = [44100, 48000, 32000, 0]
                bitrate = bitrates[bitrate_index] * 1000
                sample_rate = sample_rates[sample_index]
                if bitrate <= 0 or sample_rate <= 0:
                    return 0
                return int((file_size * 8) / bitrate)
    except OSError:
        return 0
    return 0


def _read_wav_duration(path: Path) -> int:
    try:
        with path.open("rb") as handle:
            header = handle.read(44)
        if len(header) < 44 or header[:4] != b"RIFF" or header[8:12] != b"WAVE":
            return 0
        sample_rate = struct.unpack("<I", header[24:28])[0]
        byte_rate = struct.unpack("<I", header[28:32])[0]
        data_size = struct.unpack("<I", header[40:44])[0]
        if byte_rate:
            return int(data_size / byte_rate)
        if sample_rate:
            channels = struct.unpack("<H", header[22:24])[0] or 1
            bits = struct.unpack("<H", header[34:36])[0] or 16
            bytes_per_sample = channels * bits // 8
            if bytes_per_sample:
                return int(data_size / (sample_rate * bytes_per_sample))
    except OSError:
        return 0
    return 0


def _duration_for_file(path: Path) -> int:
    suffix = path.suffix.lower()
    if suffix == ".mp3":
        return _estimate_mp3_duration(path)
    if suffix == ".wav":
        return _read_wav_duration(path)
    return 0


def _find_artwork(audio_path: Path) -> str:
    folder = audio_path.parent
    stem = audio_path.stem
    candidates = [folder / name for name in ARTWORK_NAMES]
    candidates.extend(
        [
            folder / f"{stem}.jpg",
            folder / f"{stem}.jpeg",
            folder / f"{stem}.png",
        ]
    )
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return ""


def _inspect_audio_file(path: Path) -> dict[str, Any]:
    tags = _read_id3v1(path) if path.suffix.lower() == ".mp3" else {}
    artist, album, title = _parse_filename(path.stem)
    artist = tags.get("artist") or artist
    album = tags.get("album") or album
    title = tags.get("title") or title or path.stem
    stat = path.stat()
    file_path = str(path)
    return normalize_song(
        {
            "id": song_id_for_path(file_path),
            "artist": artist,
            "title": title,
            "album": album,
            "year": tags.get("year", ""),
            "genre": tags.get("genre", ""),
            "length_seconds": _duration_for_file(path),
            "file_path": file_path,
            "file_size": stat.st_size,
            "artwork_path": _find_artwork(path),
            "added_at": datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d"),
            "last_seen_at": datetime.now().strftime("%Y-%m-%d %I:%M %p"),
            "missing_file": False,
        }
    )


def scan_music_library(music_root: str | Path, existing_catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    root = Path(music_root)
    existing_by_path = {
        item.get("file_path", ""): item
        for item in (existing_catalog or {}).get("songs", [])
        if item.get("file_path")
    }
    songs: list[dict[str, Any]] = []
    seen_paths: set[str] = set()

    if root.exists() and root.is_dir():
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in AUDIO_EXTENSIONS:
                continue
            file_path = str(path)
            seen_paths.add(file_path)
            song = _inspect_audio_file(path)
            prior = existing_by_path.get(file_path)
            if prior:
                song["format_ids"] = prior.get("format_ids", [])
                song["category_ids"] = prior.get("category_ids", [])
                if prior.get("added_at"):
                    song["added_at"] = prior["added_at"]
            songs.append(song)

    for file_path, prior in existing_by_path.items():
        if file_path not in seen_paths:
            clone = normalize_song(prior)
            clone["missing_file"] = True
            songs.append(clone)

    songs.sort(key=lambda item: (item.get("artist", "").lower(), item.get("title", "").lower()))
    return {
        "songs": songs,
        "last_scan_at": datetime.now().strftime("%Y-%m-%d %I:%M %p"),
    }


@dataclass
class LibraryOverview:
    total_songs: int = 0
    total_artists: int = 0
    total_albums: int = 0
    total_genres: int = 0
    total_playlists: int = 0
    storage_used: str = "0 B"


@dataclass
class MusicDashboard:
    total_library_size: str = "0 B"
    new_music: int = 0
    missing_files: int = 0
    duplicate_files: int = 0
    recently_added: list[str] = field(default_factory=list)


def build_library_overview(bundle: dict[str, Any]) -> LibraryOverview:
    songs = [song for song in bundle["catalog"]["songs"] if not song.get("missing_file")]
    artists = {song.get("artist", "").strip().lower() for song in songs if song.get("artist", "").strip()}
    albums = {song.get("album", "").strip().lower() for song in songs if song.get("album", "").strip()}
    genres = {song.get("genre", "").strip().lower() for song in songs if song.get("genre", "").strip()}
    playlists = [pl for pl in bundle["playlists"]["playlists"] if not pl.get("archived")]
    total_bytes = sum(song.get("file_size", 0) for song in songs)
    return LibraryOverview(
        total_songs=len(songs),
        total_artists=len(artists),
        total_albums=len(albums),
        total_genres=len(genres),
        total_playlists=len(playlists),
        storage_used=format_bytes(total_bytes),
    )


def _duplicate_groups(songs: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for song in songs:
        if song.get("missing_file"):
            continue
        artist = song.get("artist", "").strip().lower()
        title = song.get("title", "").strip().lower()
        if not artist and not title:
            continue
        key = f"{artist}::{title}"
        buckets.setdefault(key, []).append(song)
    return [group for group in buckets.values() if len(group) > 1]


def build_music_dashboard(bundle: dict[str, Any], warnings: list[str] | None = None) -> MusicDashboard:
    songs = bundle["catalog"]["songs"]
    present = [song for song in songs if not song.get("missing_file")]
    total_bytes = sum(song.get("file_size", 0) for song in present)
    missing_files = sum(1 for song in songs if song.get("missing_file"))
    duplicate_files = sum(len(group) for group in _duplicate_groups(songs))
    recently_added = sorted(
        present,
        key=lambda item: item.get("added_at", ""),
        reverse=True,
    )[:5]
    recent_lines = [
        f"{song.get('artist', 'Unknown')} — {song.get('title', 'Untitled')}"
        for song in recently_added
    ]
    scan_at = bundle["catalog"].get("last_scan_at", "")
    new_music = 0
    if scan_at:
        for song in present:
            if song.get("last_seen_at", "").startswith(scan_at[:10]):
                new_music += 1
    return MusicDashboard(
        total_library_size=format_bytes(total_bytes),
        new_music=new_music,
        missing_files=missing_files,
        duplicate_files=duplicate_files,
        recently_added=recent_lines or ["No songs in catalog yet."],
    )


def validate_music(bundle: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    root = Path(bundle["settings"].get("music_root", r"W:\Music"))
    if not root.exists():
        warnings.append(f"Music root not found: {root}")

    songs = bundle["catalog"]["songs"]
    for song in songs:
        label = f"{song.get('artist', 'Unknown')} — {song.get('title', 'Untitled')}"
        path = song.get("file_path", "")
        if song.get("missing_file") or (path and not Path(path).exists()):
            warnings.append(f"Missing file: {label}")
            continue
        if not song.get("artwork_path"):
            warnings.append(f"Missing artwork: {label}")
        if not song.get("artist", "").strip() or not song.get("title", "").strip():
            warnings.append(f"Missing metadata: {label}")
        year = str(song.get("year", "")).strip()
        if year:
            if not year.isdigit() or int(year) < 1900 or int(year) > datetime.now().year + 1:
                warnings.append(f"Incorrect year: {label} ({year})")
        genre = song.get("genre", "").strip()
        if genre and genre not in ID3_GENRES and genre.lower() not in {name.lower() for name in DEFAULT_FORMATS}:
            warnings.append(f"Incorrect genre: {label} ({genre})")

    for group in _duplicate_groups(songs):
        label = f"{group[0].get('artist', '')} — {group[0].get('title', '')}"
        warnings.append(f"Duplicate song: {label} ({len(group)} copies)")

    for song in songs:
        if not song.get("missing_file") and song.get("file_path") and root.exists():
            try:
                Path(song["file_path"]).resolve().relative_to(root.resolve())
            except (OSError, ValueError):
                warnings.append(f"Broken path: {song.get('file_path')}")

    enabled_formats = {item["id"] for item in bundle["formats"]["formats"] if item.get("enabled")}
    for song in songs:
        for format_id in song.get("format_ids", []):
            if format_id and format_id not in enabled_formats:
                warnings.append(
                    f"Song uses disabled format: {song.get('artist', '')} — {song.get('title', '')}"
                )

    return warnings


def build_report_lines(bundle: dict[str, Any], report_key: str) -> list[str]:
    songs = [song for song in bundle["catalog"]["songs"] if not song.get("missing_file")]
    warnings = validate_music(bundle)

    if report_key == "songs_by_format":
        formats = {item["id"]: item["name"] for item in bundle["formats"]["formats"]}
        counts: dict[str, int] = {name: 0 for name in formats.values()}
        unassigned = 0
        for song in songs:
            ids = song.get("format_ids", [])
            if not ids:
                unassigned += 1
                continue
            for format_id in ids:
                counts[formats.get(format_id, "Unknown")] = counts.get(formats.get(format_id, "Unknown"), 0) + 1
        lines = ["Songs by Format", ""]
        for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"  {name}: {count}")
        lines.append(f"  Unassigned: {unassigned}")
        return lines

    if report_key == "songs_by_genre":
        counts: dict[str, int] = {}
        for song in songs:
            genre = song.get("genre", "").strip() or "Unknown"
            counts[genre] = counts.get(genre, 0) + 1
        lines = ["Songs by Genre", ""]
        for genre, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"  {genre}: {count}")
        return lines

    if report_key == "songs_by_year":
        counts: dict[str, int] = {}
        for song in songs:
            year = str(song.get("year", "")).strip() or "Unknown"
            counts[year] = counts.get(year, 0) + 1
        lines = ["Songs by Year", ""]
        for year, count in sorted(counts.items(), key=lambda item: (-int(item[0]) if item[0].isdigit() else 0, item[0])):
            lines.append(f"  {year}: {count}")
        return lines

    if report_key == "duplicate_songs":
        lines = ["Duplicate Songs", ""]
        groups = _duplicate_groups(songs)
        if not groups:
            lines.append("  No duplicate songs detected.")
            return lines
        for group in groups:
            lines.append(f"  {group[0].get('artist', '')} — {group[0].get('title', '')} ({len(group)} copies)")
        return lines

    if report_key == "missing_artwork":
        lines = ["Missing Artwork", ""]
        missing = [song for song in songs if not song.get("artwork_path")]
        if not missing:
            lines.append("  All scanned songs have artwork.")
            return lines
        for song in missing[:50]:
            lines.append(f"  {song.get('artist', '')} — {song.get('title', '')}")
        if len(missing) > 50:
            lines.append(f"  …and {len(missing) - 50} more")
        return lines

    if report_key == "missing_metadata":
        lines = ["Missing Metadata", ""]
        missing = [
            song
            for song in songs
            if not song.get("artist", "").strip() or not song.get("title", "").strip()
        ]
        if not missing:
            lines.append("  All scanned songs have artist and title.")
            return lines
        for song in missing[:50]:
            lines.append(f"  {song.get('file_path', '')}")
        if len(missing) > 50:
            lines.append(f"  …and {len(missing) - 50} more")
        return lines

    return [f"Unknown report: {report_key}"]

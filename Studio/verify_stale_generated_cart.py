"""Verify stale Generated Voice carts surface a replay alert."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from app.core.broadcasting_manager_model import (  # noqa: E402
    AudioFolderSummary,
    _generated_voice_stale_message,
)
from app.core.health_constants import HEALTH_OK, HEALTH_WARN  # noqa: E402


@dataclass
class _Svc:
    name: str
    status: str
    detail: str
    running: bool


class _Status:
    def __init__(self, services: list[_Svc]) -> None:
        self.services = services


def _check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)


def main() -> None:
    livedj_up = _Status([_Svc("LiveDJ Watcher", HEALTH_OK, "Watcher running", True)])
    livedj_down = _Status([_Svc("LiveDJ Watcher", HEALTH_WARN, "Watcher not detected", False)])

    fresh = [
        AudioFolderSummary(
            "audio_generated",
            "Generated Voice",
            r"D:\MosPlaceRadioPlatform\Audio\Generated",
            HEALTH_OK,
            3,
            ["kathy.wav · 420.0 KB · 0.2h ago"],
            [],
        )
    ]
    stale = [
        AudioFolderSummary(
            "audio_generated",
            "Generated Voice",
            r"D:\MosPlaceRadioPlatform\Audio\Generated",
            HEALTH_OK,
            3,
            ["kathy.wav · 420.0 KB · 2.5h ago"],
            [],
        )
    ]
    empty = [
        AudioFolderSummary(
            "audio_generated",
            "Generated Voice",
            r"D:\MosPlaceRadioPlatform\Audio\Generated",
            HEALTH_WARN,
            0,
            [],
            ["No audio files found"],
        )
    ]

    # Force daytime path by calling with patched hour via monkeypatch of datetime is heavy;
    # instead assert helper logic with known folder ages when hour is in range.
    import app.core.broadcasting_manager_model as mod

    original_now = mod.datetime

    class _Daytime(original_now):  # type: ignore[misc,valid-type]
        @classmethod
        def now(cls, tz=None):  # noqa: ANN001
            return original_now(2026, 10, 5, 14, 30, 0)

    mod.datetime = _Daytime  # type: ignore[misc]
    try:
        _check("fresh carts do not alert", _generated_voice_stale_message(fresh, livedj_up) is None)
        msg = _generated_voice_stale_message(stale, livedj_up)
        _check("stale carts alert while LiveDJ running", msg is not None and "replaying the previous break" in msg)
        _check("no alert when LiveDJ stopped", _generated_voice_stale_message(stale, livedj_down) is None)
        empty_msg = _generated_voice_stale_message(empty, livedj_up)
        _check("empty Generated Voice alerts", empty_msg is not None and "no cart audio" in empty_msg.lower())
    finally:
        mod.datetime = original_now

    print("verify_stale_generated_cart: OK")


if __name__ == "__main__":
    main()

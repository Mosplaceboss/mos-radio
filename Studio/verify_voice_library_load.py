"""Verify Voice Library opens without freezing or event-loop recursion."""

from __future__ import annotations

import sys
import time
from pathlib import Path

STUDIO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(STUDIO_ROOT))

import ttkbootstrap as ttk

from app.core.config_manager import ConfigManager
from app.core.voice_library_loader import load_voice_library_page_data
from app.pages.voice_library import VoiceLibraryPage
from app.ui.main_window import MainWindow
from app.ui.theme import StudioTheme

MAX_ON_SHOW_MS = 200
FIRST_BUILD_MS = 500
SWITCH_ROUNDS = 12
STATUS_CALL_LIMIT = 20


def test_background_loader() -> None:
    config = ConfigManager()
    for _round in range(SWITCH_ROUNDS):
        result = load_voice_library_page_data(
            config.path_for("personalities"),
            config.path_for("voice_library"),
        )
        if not result.voices_data.get("voices"):
            raise RuntimeError("Expected existing voice records in voice_library.json")
    print(f"LOADER OK: {SWITCH_ROUNDS} background loads")


def _switch_and_wait(
    root: ttk.Window,
    window: MainWindow,
    source: str,
    round_index: int,
    *,
    allow_first_build: bool = False,
) -> None:
    started = time.perf_counter()
    window.show_page(source)
    root.update_idletasks()
    window.show_page("voice_library")
    elapsed_ms = (time.perf_counter() - started) * 1000
    root.update_idletasks()
    limit = FIRST_BUILD_MS if allow_first_build else MAX_ON_SHOW_MS
    if elapsed_ms > limit:
        raise RuntimeError(
            f"{source} -> Voice Library switch {round_index + 1} blocked main thread for {elapsed_ms:.0f} ms"
        )

    status_calls = {"count": 0}

    def counting_status(message: str) -> None:
        status_calls["count"] += 1
        window.set_status(message)

    voice_page = window._pages["voice_library"]
    voice_page.on_status = counting_status

    deadline = time.perf_counter() + 3.0
    while time.perf_counter() < deadline:
        root.update()
        if not voice_page._load_in_progress:
            break
        time.sleep(0.02)
    else:
        raise RuntimeError(f"Voice Library load did not finish during round {round_index + 1}")

    voices = len(voice_page._data.get("voices", []))
    if voices == 0:
        raise RuntimeError(f"Voice Library opened with zero voices during round {round_index + 1}")

    if status_calls["count"] > STATUS_CALL_LIMIT:
        raise RuntimeError(
            f"Voice Library triggered {status_calls['count']} status updates; likely event recursion"
        )

    if voice_page._error_label.cget("text"):
        raise RuntimeError(
            f"Voice Library showed error banner: {voice_page._error_label.cget('text')}"
        )


def test_navigation_loops() -> None:
    root = ttk.Window(themename=StudioTheme.BOOTSTRAP_THEME)
    root.withdraw()
    try:
        StudioTheme.apply_custom_styles(ttk.Style())
        config = ConfigManager()
        window = MainWindow(root, config)

        for round_index in range(SWITCH_ROUNDS):
            _switch_and_wait(
                root,
                window,
                "settings",
                round_index,
                allow_first_build=round_index == 0,
            )
            _switch_and_wait(root, window, "dashboard", round_index)

        print(
            f"SWITCH OK: {SWITCH_ROUNDS * 2} Settings/Dashboard <-> Voice Library switches "
            f"under {MAX_ON_SHOW_MS} ms with voices loaded"
        )
    finally:
        root.destroy()


def main() -> int:
    test_background_loader()
    test_navigation_loops()
    print("Voice Library freeze checks verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

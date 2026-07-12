"""Verify Voice Library loads off the main thread without blocking navigation."""

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

MAX_ON_SHOW_MS = 120
SWITCH_ROUNDS = 12


def test_background_loader() -> None:
    config = ConfigManager()
    for _round in range(SWITCH_ROUNDS):
        result = load_voice_library_page_data(
            config.path_for("personalities"),
            config.path_for("voice_library"),
        )
        if result.load_errors:
            raise RuntimeError(f"Loader errors: {result.load_errors}")
    print(f"LOADER OK: {SWITCH_ROUNDS} background loads")


def test_settings_voice_switch() -> None:
    root = ttk.Window(themename=StudioTheme.BOOTSTRAP_THEME)
    root.withdraw()
    try:
        StudioTheme.apply_custom_styles(ttk.Style())
        config = ConfigManager()
        window = MainWindow(root, config)

        window.show_page("settings")
        root.update_idletasks()

        for round_index in range(SWITCH_ROUNDS):
            started = time.perf_counter()
            window.show_page("voice_library")
            elapsed_ms = (time.perf_counter() - started) * 1000
            root.update_idletasks()
            if elapsed_ms > MAX_ON_SHOW_MS:
                raise RuntimeError(
                    f"Voice Library switch {round_index + 1} blocked main thread for {elapsed_ms:.0f} ms"
                )

            started = time.perf_counter()
            window.show_page("settings")
            elapsed_ms = (time.perf_counter() - started) * 1000
            root.update_idletasks()
            if elapsed_ms > MAX_ON_SHOW_MS:
                raise RuntimeError(
                    f"Settings switch {round_index + 1} blocked main thread for {elapsed_ms:.0f} ms"
                )

            deadline = time.perf_counter() + 2.0
            while time.perf_counter() < deadline:
                root.update()
                voice_page = window._pages.get("voice_library")
                if isinstance(voice_page, VoiceLibraryPage) and not voice_page._load_in_progress:
                    break
                time.sleep(0.05)
            else:
                raise RuntimeError(f"Voice Library load did not finish during round {round_index + 1}")

        print(f"SWITCH OK: {SWITCH_ROUNDS} Settings <-> Voice Library switches under {MAX_ON_SHOW_MS} ms")
    finally:
        root.destroy()


def main() -> int:
    test_background_loader()
    test_settings_voice_switch()
    print("Voice Library freeze checks verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

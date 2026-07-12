"""Verify Personalities opens without freezing or event-loop recursion."""

from __future__ import annotations

import sys
import time
from pathlib import Path

STUDIO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(STUDIO_ROOT))

import ttkbootstrap as ttk

from app.core.config_manager import ConfigManager
from app.core.personalities_loader import load_personalities_page_data
from app.pages.personalities import PersonalitiesPage
from app.ui.main_window import MainWindow
from app.ui.theme import StudioTheme

MAX_ON_SHOW_MS = 200
FIRST_BUILD_MS = 500
SWITCH_ROUNDS = 12
STATUS_CALL_LIMIT = 20


def test_background_loader() -> None:
    config = ConfigManager()
    for _round in range(SWITCH_ROUNDS):
        result = load_personalities_page_data(config.path_for("personalities"))
        if not result.personalities_data.get("personalities"):
            raise RuntimeError("Expected existing personality records in personalities.json")
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
    window.show_page("personalities")
    elapsed_ms = (time.perf_counter() - started) * 1000
    root.update_idletasks()
    limit = FIRST_BUILD_MS if allow_first_build else MAX_ON_SHOW_MS
    if elapsed_ms > limit:
        raise RuntimeError(
            f"{source} -> Personalities switch {round_index + 1} blocked main thread for {elapsed_ms:.0f} ms"
        )

    status_calls = {"count": 0}

    def counting_status(message: str) -> None:
        status_calls["count"] += 1
        window.set_status(message)

    page = window._pages["personalities"]
    page.on_status = counting_status

    deadline = time.perf_counter() + 3.0
    while time.perf_counter() < deadline:
        root.update()
        if not page._load_in_progress:
            break
        time.sleep(0.02)
    else:
        raise RuntimeError(f"Personalities load did not finish during round {round_index + 1}")

    count = len(page._data.get("personalities", []))
    if count == 0:
        raise RuntimeError(f"Personalities opened with zero records during round {round_index + 1}")

    if status_calls["count"] > STATUS_CALL_LIMIT:
        raise RuntimeError(
            f"Personalities triggered {status_calls['count']} status updates; likely event recursion"
        )

    if page._error_label.cget("text"):
        raise RuntimeError(f"Personalities showed error banner: {page._error_label.cget('text')}")


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
            f"SWITCH OK: {SWITCH_ROUNDS * 2} Settings/Dashboard <-> Personalities switches "
            f"under {MAX_ON_SHOW_MS} ms with records loaded"
        )
    finally:
        root.destroy()


def test_repeat_on_show() -> None:
    root = ttk.Window(themename=StudioTheme.BOOTSTRAP_THEME)
    root.geometry("1000x700")
    StudioTheme.apply_custom_styles(ttk.Style())
    config = ConfigManager()
    counts: list[int] = []

    page = PersonalitiesPage(root, config, on_status=lambda _m: counts.append(1))
    page.pack(fill="both", expand=True)

    try:
        for round_index in range(10):
            counts.clear()
            page.on_show()
            deadline = time.perf_counter() + 3.0
            while time.perf_counter() < deadline:
                root.update()
                if not page._load_in_progress:
                    break
                time.sleep(0.02)
            else:
                raise RuntimeError(f"Personalities load timeout on round {round_index + 1}")

            page.on_hide()
            if len(counts) > STATUS_CALL_LIMIT:
                raise RuntimeError(
                    f"Personalities status spam ({len(counts)}) on round {round_index + 1}"
                )

        print("REPEAT OK: 10 Personalities open/close cycles")
    finally:
        root.destroy()


def main() -> int:
    test_background_loader()
    test_navigation_loops()
    test_repeat_on_show()
    print("Personalities freeze checks verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Comprehensive UI stability checks: page open times, button commands, CRUD flows."""

from __future__ import annotations

import sys
import time
import traceback
import unittest.mock as mock
from pathlib import Path

STUDIO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(STUDIO_ROOT))

import tkinter as tk

import ttkbootstrap as ttk

from app.core.config_manager import ConfigManager
from app.ui.main_window import MainWindow
from app.ui.navigation import NavigationPanel
from app.ui.theme import StudioTheme

MAX_PAGE_OPEN_MS = 1000
FIRST_BUILD_MS = 500
LOAD_WAIT_S = 5.0
STATUS_CALL_LIMIT = 25
CRUD_ROUNDS = 10
BACKGROUND_REFRESH_PAGES = frozenset({"dashboard", "automation", "station_manager", "operations_manager"})

SKIP_BUTTON_TEXT = frozenset(
    {
        "Publish to Production",
        "Publish to LiveDJ",
        "Restore from Backup",
        "Restore Last Backup",
        "Import from Live",
        "Import from LiveDJ",
        "Start Request Watcher",
        "Restart Request Watcher",
        "Start LiveDJ Watcher",
        "Restart LiveDJ Watcher",
        "Run News Now",
        "Refresh All Statuses",
        "Start",
        "Stop",
        "Restart",
        "Test Run",
        "Upload Picture",
        "Upload Portrait",
        "Refresh Now",
        "Station Information",
        "Back to Station Manager",
        "Save Programming",
        "Apply Show Changes",
        "Apply Event Changes",
        "Add Show",
        "Delete Show",
        "Add Format",
        "Add Event",
        "Copy Day",
        "Copy Week",
        "Add Holiday Override",
        "Duplicate Event",
        "Disable Event",
        "Save Assignment",
        "Save Music Data",
        "Scan Library",
        "Apply Format Changes",
        "Add Format",
        "Create Playlist",
        "Duplicate Playlist",
        "Archive Playlist",
        "Delete Playlist",
        "Apply Playlist Changes",
        "Apply Category Changes",
        "Save Resources",
        "Save Settings",
        "Use Platform Default",
        "Run Report",
        "Save News Data",
        "Save Operations Data",
        "Refresh Status",
        "Create Backup",
        "Restore Last Backup",
        "Validate Deployment",
        "Create Deployment Package",
        "Roll Back",
        "Copy Module",
        "Verify Copy",
        "Mark Testing",
        "Mark Ready",
        "Add Personality",
        "Delete Personality",
        "Apply Personality Changes",
        "Apply Category Changes",
        "Add Feed",
        "Delete Feed",
        "Test Feed",
        "Apply Feed Changes",
        "Add Holiday Override",
        "Apply Schedule Changes",
        "Apply Script Rules",
        "Save Voice Settings",
        "Test Voice",
        "Generate Dev Script",
        "Open Output Folder",
        "Upload Logo",
        "Remove Logo",
        "Validate All Paths",
        "Save All Paths",
        "Browse",
        "Open Folder",
        "Reset to Default",
        "Open Platform Manager",
        "Add Event",
        "Delete Event",
        "Add Personality",
        "Delete Personality",
        "Add Voice",
        "Delete Voice",
        "Import LiveDJ Personalities",
        "Import LiveDJ Schedule",
        "Import News Status",
        "Import Request Settings",
        "Test Connections",
        "Use Local Automation Folders",
        "Open Personalities",
        "Open Schedule",
        "Open Voice Library",
        "Open Requests",
        "Open News",
        "Open LiveDJ",
        "Open Automation",
        "Open Connection Setup",
        "Open Settings",
        "Open Configuration",
        "Open Log",
        "Health Check",
        "Remove Picture",
        "Remove Portrait",
    }
)


def _pump_events(root: ttk.Window, seconds: float = 0.75) -> None:
    deadline = time.perf_counter() + seconds
    while time.perf_counter() < deadline:
        root.update()
        time.sleep(0.02)


def _wait_for_idle(root: ttk.Window, predicate, *, timeout: float = LOAD_WAIT_S) -> None:
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        root.update()
        if predicate():
            return
        time.sleep(0.02)
    raise RuntimeError("Timed out waiting for page to become idle")


def _page_idle(page) -> bool:
    if getattr(page, "_load_in_progress", False):
        return False
    if getattr(page, "_refresh_in_progress", False):
        return False
    if getattr(page, "_scan_in_progress", False):
        return False
    if getattr(page, "_busy", False):
        return False
    if getattr(page, "_busy_depth", 0) > 0:
        return False
    return True


def _collect_buttons(widget: tk.Misc) -> list[ttk.Button]:
    buttons: list[ttk.Button] = []
    for child in widget.winfo_children():
        if isinstance(child, ttk.Button):
            buttons.append(child)
        buttons.extend(_collect_buttons(child))
    return buttons


def test_all_pages_open_quickly() -> None:
    root = ttk.Window(themename=StudioTheme.BOOTSTRAP_THEME)
    root.withdraw()
    try:
        StudioTheme.apply_custom_styles(ttk.Style())
        config = ConfigManager()
        window = MainWindow(root, config)

        for index, page_id in enumerate(MainWindow.PAGE_CLASSES):
            started = time.perf_counter()
            window.show_page(page_id)
            root.update_idletasks()
            page = window._pages[page_id]
            limit = FIRST_BUILD_MS if index == 0 else MAX_PAGE_OPEN_MS
            elapsed_ms = (time.perf_counter() - started) * 1000
            if elapsed_ms > limit:
                raise RuntimeError(
                    f"Page '{page_id}' show_page blocked main thread for {elapsed_ms:.0f} ms (limit {limit} ms)"
                )

            if page_id not in BACKGROUND_REFRESH_PAGES:
                _wait_for_idle(root, lambda p=page: _page_idle(p))
            if hasattr(page, "_error_label") and page._error_label.cget("text"):
                raise RuntimeError(f"Page '{page_id}' error banner: {page._error_label.cget('text')}")

            print(f"PAGE OPEN OK: {page_id} ({elapsed_ms:.0f} ms to show)")

    finally:
        root.destroy()


def test_page_button_commands() -> None:
    root = ttk.Window(themename=StudioTheme.BOOTSTRAP_THEME)
    root.withdraw()
    patches = [
        mock.patch("ttkbootstrap.dialogs.Messagebox.yesno", return_value="No"),
        mock.patch("ttkbootstrap.dialogs.Messagebox.show_info", return_value=None),
        mock.patch("ttkbootstrap.dialogs.Messagebox.show_warning", return_value=None),
        mock.patch("ttkbootstrap.dialogs.Messagebox.show_error", return_value=None),
        mock.patch("app.ui.confirm_dialog.confirm_action", return_value=False),
    ]
    try:
        for patch in patches:
            patch.start()
        StudioTheme.apply_custom_styles(ttk.Style())
        config = ConfigManager()
        window = MainWindow(root, config)
        clicked = 0
        failures: list[str] = []

        for page_id in MainWindow.PAGE_CLASSES:
            window.show_page(page_id)
            root.update_idletasks()
            page = window._pages[page_id]
            if page_id in BACKGROUND_REFRESH_PAGES:
                _pump_events(root, 2.0)
            else:
                _wait_for_idle(root, lambda p=page: _page_idle(p))

            button_specs: list[tuple[str, object]] = []
            for button in _collect_buttons(page):
                try:
                    label = button.cget("text")
                    command = button.cget("command")
                except tk.TclError:
                    continue
                if label in SKIP_BUTTON_TEXT or label.startswith("Open ") or not command:
                    continue
                button_specs.append((label, command))

            for label, command in button_specs:
                try:
                    root.update_idletasks()
                    started = time.perf_counter()
                    if callable(command):
                        command()
                    root.update_idletasks()
                    elapsed_ms = (time.perf_counter() - started) * 1000
                    if elapsed_ms > MAX_PAGE_OPEN_MS:
                        failures.append(
                            f"{page_id}/{label}: command blocked {elapsed_ms:.0f} ms"
                        )
                    clicked += 1
                except Exception as exc:
                    failures.append(f"{page_id}/{label}: {exc}")
                    traceback.print_exc()

        if failures:
            raise RuntimeError("Button command failures:\n" + "\n".join(failures))

        print(f"BUTTONS OK: invoked {clicked} safe button commands without blocking")
    finally:
        for patch in reversed(patches):
            patch.stop()
        root.destroy()


def _crud_personalities(root: ttk.Window, config: ConfigManager) -> None:
    from app.pages.personalities import PersonalitiesPage

    status_calls: list[str] = []

    page = PersonalitiesPage(root, config, on_status=status_calls.append)
    page.pack(fill="both", expand=True)

    with (
        mock.patch("ttkbootstrap.dialogs.Messagebox.yesno", return_value="Yes"),
        mock.patch("ttkbootstrap.dialogs.Messagebox.show_warning", return_value=None),
        mock.patch("ttkbootstrap.dialogs.Messagebox.show_info", return_value=None),
        mock.patch("ttkbootstrap.dialogs.Messagebox.show_error", return_value=None),
    ):
        page.on_show()
        _wait_for_idle(root, lambda: not page._load_in_progress)

        for round_index in range(CRUD_ROUNDS):
            status_calls.clear()
            before = len(page._data.get("personalities", []))
            page._add_personality()
            _pump_events(root)
            after_add = len(page._data.get("personalities", []))
            if after_add != before + 1:
                raise RuntimeError(f"Personalities add failed on round {round_index + 1}")

            personality = page._selected_personality()
            if not personality:
                raise RuntimeError(f"Personalities selection missing after add (round {round_index + 1})")
            personality["display_name"] = f"Stability Test {round_index}"
            page._field_vars["display_name"].set(personality["display_name"])
            page._apply_form_to_selected()
            page._save_now()
            _pump_events(root)

            page._delete_personality()
            _pump_events(root)
            if len(page._data.get("personalities", [])) != before:
                raise RuntimeError(f"Personalities delete failed on round {round_index + 1}")

            if len(status_calls) > STATUS_CALL_LIMIT:
                raise RuntimeError(
                    f"Personalities status spam ({len(status_calls)}) on round {round_index + 1}"
                )

        page.on_hide()

    print(f"CRUD OK: Personalities add/edit/save/delete x{CRUD_ROUNDS}")


def _crud_voice_library(root: ttk.Window, config: ConfigManager) -> None:
    from app.pages.voice_library import VoiceLibraryPage

    status_calls: list[str] = []

    page = VoiceLibraryPage(root, config, on_status=status_calls.append)
    page.pack(fill="both", expand=True)

    with (
        mock.patch("ttkbootstrap.dialogs.Messagebox.yesno", return_value="Yes"),
        mock.patch("ttkbootstrap.dialogs.Messagebox.show_warning", return_value=None),
        mock.patch("ttkbootstrap.dialogs.Messagebox.show_info", return_value=None),
        mock.patch("ttkbootstrap.dialogs.Messagebox.show_error", return_value=None),
    ):
        page.on_show()
        _wait_for_idle(root, lambda: not page._load_in_progress)

        for round_index in range(CRUD_ROUNDS):
            status_calls.clear()
            before = len(page._data.get("voices", []))
            page._add_voice()
            _pump_events(root)
            after_add = len(page._data.get("voices", []))
            if after_add != before + 1:
                raise RuntimeError(f"Voice add failed on round {round_index + 1}")

            voice = page._selected_voice()
            if not voice:
                raise RuntimeError(f"Voice selection missing after add (round {round_index + 1})")
            voice["display_name"] = f"Stability Voice {round_index}"
            page._field_vars["display_name"].set(voice["display_name"])
            page._apply_form_to_selected()
            page._save_now()
            _pump_events(root)

            page._delete_voice()
            _pump_events(root)
            if len(page._data.get("voices", [])) != before:
                raise RuntimeError(f"Voice delete failed on round {round_index + 1}")

            if len(status_calls) > STATUS_CALL_LIMIT:
                raise RuntimeError(
                    f"Voice Library status spam ({len(status_calls)}) on round {round_index + 1}"
                )

        page.on_hide()

    print(f"CRUD OK: Voice Library add/edit/save/delete x{CRUD_ROUNDS}")


def test_crud_flows() -> None:
    root = ttk.Window(themename=StudioTheme.BOOTSTRAP_THEME)
    root.geometry("1100x760")
    StudioTheme.apply_custom_styles(ttk.Style())
    config = ConfigManager()
    personalities_backup = config.load("personalities", {"personalities": []})
    voices_backup = config.load("voice_library", {"voices": []})
    if not personalities_backup.get("personalities"):
        personalities_path = STUDIO_ROOT.parent / "Automation" / "LiveDJ" / "personalities.json"
        if personalities_path.exists():
            from app.core.config_io import read_json

            personalities_backup, _ = read_json(personalities_path, {"personalities": []})
    if not voices_backup.get("voices"):
        voices_path = STUDIO_ROOT.parent / "Automation" / "LiveDJ" / "voice_library.json"
        if voices_path.exists():
            from app.core.config_io import read_json

            voices_backup, _ = read_json(voices_path, {"voices": []})
    try:
        _crud_personalities(root, config)
        for child in root.winfo_children():
            child.destroy()
        _crud_voice_library(root, config)
    finally:
        from app.core.config_io import write_json

        write_json(config.path_for("personalities"), personalities_backup)
        write_json(config.path_for("voice_library"), voices_backup)
        config._cache["personalities"] = personalities_backup
        config._cache["voice_library"] = voices_backup
        root.destroy()


def test_navigation_stress() -> None:
    root = ttk.Window(themename=StudioTheme.BOOTSTRAP_THEME)
    root.withdraw()
    try:
        StudioTheme.apply_custom_styles(ttk.Style())
        config = ConfigManager()
        window = MainWindow(root, config)
        sequence = list(MainWindow.PAGE_CLASSES.keys()) * 2

        for index, page_id in enumerate(sequence):
            started = time.perf_counter()
            window.show_page(page_id)
            root.update_idletasks()
            elapsed_ms = (time.perf_counter() - started) * 1000
            limit = FIRST_BUILD_MS if index == 0 else MAX_PAGE_OPEN_MS
            if elapsed_ms > limit:
                raise RuntimeError(
                    f"Navigation to '{page_id}' blocked {elapsed_ms:.0f} ms (limit {limit} ms)"
                )
            page = window._pages[page_id]
            if page_id not in BACKGROUND_REFRESH_PAGES:
                _wait_for_idle(root, lambda p=page: _page_idle(p))

        print(f"NAV OK: {len(sequence)} page switches under {MAX_PAGE_OPEN_MS} ms")
    finally:
        root.destroy()


def test_nav_panel_buttons() -> None:
    root = ttk.Window(themename=StudioTheme.BOOTSTRAP_THEME)
    root.withdraw()
    try:
        StudioTheme.apply_custom_styles(ttk.Style())
        config = ConfigManager()
        window = MainWindow(root, config)

        for page_id, label in NavigationPanel.NAV_ITEMS:
            started = time.perf_counter()
            window._navigation.select(page_id)
            root.update_idletasks()
            elapsed_ms = (time.perf_counter() - started) * 1000
            if elapsed_ms > MAX_PAGE_OPEN_MS:
                raise RuntimeError(
                    f"Nav button '{label}' blocked {elapsed_ms:.0f} ms (limit {MAX_PAGE_OPEN_MS} ms)"
                )
            page = window._pages[page_id]
            if page_id not in BACKGROUND_REFRESH_PAGES:
                _wait_for_idle(root, lambda p=page: _page_idle(p))
            print(f"NAV BUTTON OK: {label}")

        print(f"NAV BUTTONS OK: {len(NavigationPanel.NAV_ITEMS)} navigation buttons")
    finally:
        root.destroy()


def main() -> int:
    test_all_pages_open_quickly()
    test_nav_panel_buttons()
    test_navigation_stress()
    test_page_button_commands()
    test_crud_flows()
    print("UI stability checks verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

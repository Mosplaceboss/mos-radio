"""Headless verification: instantiate app and open every page."""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

STUDIO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(STUDIO_ROOT))

import ttkbootstrap as ttk

from app.core.config_manager import ConfigManager
from app.ui.main_window import MainWindow
from app.ui.navigation import NavigationPanel
from app.ui.theme import StudioTheme


def main() -> int:
    errors: list[str] = []
    root = ttk.Window(themename=StudioTheme.BOOTSTRAP_THEME)
    root.withdraw()

    try:
        StudioTheme.apply_custom_styles(ttk.Style())
        config_manager = ConfigManager()
        window = MainWindow(root, config_manager)

        for page_id in MainWindow.PAGE_CLASSES:
            try:
                window.show_page(page_id)
                root.update_idletasks()
                page = window._pages[page_id]
                page.on_show()
                root.update_idletasks()
                print(f"PAGE OK: {page_id} ({page.page_title})")
            except Exception as exc:
                errors.append(f"{page_id}: {exc}")
                print(f"PAGE FAIL: {page_id}: {exc}")
                traceback.print_exc()

        for page_id, label in NavigationPanel.NAV_ITEMS:
            try:
                window._navigation.select(page_id)
                root.update_idletasks()
                print(f"NAV OK: {label}")
            except Exception as exc:
                errors.append(f"nav/{page_id}: {exc}")
                print(f"NAV FAIL: {label}: {exc}")
                traceback.print_exc()

    finally:
        root.destroy()

    if errors:
        print(f"\n{len(errors)} page(s) failed.")
        return 1

    print("\nAll pages verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

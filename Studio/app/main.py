"""Mo's Place Studio desktop application entry point."""

from __future__ import annotations

import sys
from pathlib import Path

import ttkbootstrap as ttk

# Ensure the Studio directory is on sys.path for package imports.
STUDIO_ROOT = Path(__file__).resolve().parent.parent
if str(STUDIO_ROOT) not in sys.path:
    sys.path.insert(0, str(STUDIO_ROOT))

from app.core.config_manager import ConfigManager
from app.core.live_connector import ensure_local_integration_template
from app.core.logger import setup_logging
from app.core.paths import ensure_default_configs
from app.core.platform_manager import ensure_default_platform_config
from app.core.programming_model import ensure_programming_data
from app.core.station_data import ensure_station_data
from app.ui.main_window import MainWindow
from app.ui.theme import StudioTheme


class StudioApplication:
    """Top-level application controller."""

    def __init__(self) -> None:
        ensure_default_configs()
        ensure_default_platform_config()
        ensure_station_data()
        ensure_local_integration_template()
        self.config_manager = ConfigManager()
        ensure_programming_data(self.config_manager)
        settings = self.config_manager.load("settings")
        log_level = settings.get("log_level", "INFO")
        self.logger = setup_logging(log_level)

        theme_name = settings.get("theme", StudioTheme.BOOTSTRAP_THEME)
        self.root = ttk.Window(
            title="Mo's Place Studio",
            themename=theme_name,
            size=(1280, 800),
            minsize=(1024, 680),
        )
        StudioTheme.apply_custom_styles(ttk.Style())

        self.main_window = MainWindow(self.root, self.config_manager)
        self.main_window.pack(fill="both", expand=True)

        self.logger.info("Mo's Place Studio started")

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    StudioApplication().run()


if __name__ == "__main__":
    main()

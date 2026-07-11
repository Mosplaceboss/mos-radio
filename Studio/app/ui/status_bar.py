"""Application status bar."""

from __future__ import annotations

import tkinter as tk
from datetime import datetime
from typing import TYPE_CHECKING

import ttkbootstrap as ttk

from app.core.studio_info import status_bar_summary
from app.ui.theme import StudioTheme

if TYPE_CHECKING:
    from app.core.config_manager import ConfigManager


class StatusBar(ttk.Frame):
    """Bottom status bar for messages, studio metadata, and clock."""

    def __init__(self, parent: tk.Misc, config_manager: ConfigManager | None = None) -> None:
        super().__init__(parent, style="StudioStatus.TFrame", height=StudioTheme.STATUS_HEIGHT)
        self.pack_propagate(False)
        self._config_manager = config_manager

        self._message = ttk.Label(
            self,
            text="Ready",
            style="StudioStatus.TLabel",
        )
        self._message.pack(side="left", padx=12)

        self._meta = ttk.Label(
            self,
            text="",
            style="StudioStatus.TLabel",
        )
        self._meta.pack(side="left", padx=8)

        self._clock = ttk.Label(
            self,
            text="",
            style="StudioStatus.TLabel",
        )
        self._clock.pack(side="right", padx=12)

        self.refresh_meta()
        self._tick()

    def set_message(self, message: str) -> None:
        self._message.configure(text=message)

    def refresh_meta(self) -> None:
        settings = {}
        if self._config_manager:
            settings = self._config_manager.load("settings", {})
        self._meta.configure(text=status_bar_summary(settings))

    def _tick(self) -> None:
        self._clock.configure(text=datetime.now().strftime("%I:%M %p"))
        self.after(30_000, self._tick)

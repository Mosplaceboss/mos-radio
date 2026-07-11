"""Application status bar."""

from __future__ import annotations

import tkinter as tk
from datetime import datetime

import ttkbootstrap as ttk

from app.ui.theme import StudioTheme


class StatusBar(ttk.Frame):
    """Bottom status bar for messages and clock."""

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent, style="StudioStatus.TFrame", height=StudioTheme.STATUS_HEIGHT)
        self.pack_propagate(False)

        self._message = ttk.Label(
            self,
            text="Ready",
            style="StudioStatus.TLabel",
        )
        self._message.pack(side="left", padx=12)

        self._clock = ttk.Label(
            self,
            text="",
            style="StudioStatus.TLabel",
        )
        self._clock.pack(side="right", padx=12)
        self._tick()

    def set_message(self, message: str) -> None:
        self._message.configure(text=message)

    def _tick(self) -> None:
        self._clock.configure(text=datetime.now().strftime("%I:%M %p"))
        self.after(30_000, self._tick)

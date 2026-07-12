"""Left-docked navigation panel."""

from __future__ import annotations

import tkinter as tk
from typing import Callable

import ttkbootstrap as ttk

from app.ui.theme import StudioTheme


class NavigationPanel(ttk.Frame):
    """Vertical navigation with page selection callbacks."""

    NAV_ITEMS = (
        ("dashboard", "Dashboard"),
        ("integration", "Live Integration"),
        ("automation", "Automation"),
        ("personalities", "Personalities"),
        ("voice_library", "Voice Library"),
        ("schedule", "Schedule"),
        ("requests", "Requests"),
        ("news", "News"),
        ("livedj", "LiveDJ"),
        ("settings", "Settings"),
    )

    def __init__(self, parent: tk.Misc, on_navigate: Callable[[str], None]) -> None:
        super().__init__(parent, style="StudioNav.TFrame", width=StudioTheme.NAV_WIDTH)
        self.pack_propagate(False)
        self._on_navigate = on_navigate
        self._buttons: dict[str, ttk.Button] = {}
        self._active_id = "dashboard"

        header = ttk.Label(
            self,
            text="Navigation",
            font=("Segoe UI", 9, "bold"),
            foreground=StudioTheme.TEXT_MUTED,
            background=StudioTheme.BG_NAV,
        )
        header.pack(anchor="w", padx=16, pady=(16, 8))

        for page_id, label in self.NAV_ITEMS:
            button = ttk.Button(
                self,
                text=label,
                style="StudioNav.TButton",
                bootstyle="secondary",
                command=lambda pid=page_id: self.select(pid),
            )
            button.pack(fill="x", padx=12, pady=2)
            self._buttons[page_id] = button

    def select(self, page_id: str, *, notify: bool = True) -> None:
        if page_id not in self._buttons:
            return
        self._active_id = page_id
        for pid, button in self._buttons.items():
            if pid == page_id:
                button.configure(style="StudioNavActive.TButton", bootstyle="primary")
            else:
                button.configure(style="StudioNav.TButton", bootstyle="secondary")
        if notify:
            self._on_navigate(page_id)

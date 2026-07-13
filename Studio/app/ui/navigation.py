"""Left-docked navigation panel."""

from __future__ import annotations

import tkinter as tk
from typing import Any, Callable

import ttkbootstrap as ttk

from app.core.user_modes import visible_nav_items, visible_nav_sections
from app.ui.theme import StudioTheme


class NavigationPanel(ttk.Frame):
    """Vertical navigation with page selection callbacks."""

    NAV_ITEMS = (
        ("daily_operations", "Daily Operations"),
        ("station_manager", "Station Manager"),
        ("dashboard", "Dashboard"),
        ("help", "Help"),
        ("programming", "Programming"),
        ("music_manager", "Music"),
        ("personalities", "Personalities"),
        ("voice_library", "Voice Library"),
        ("schedule", "Schedule"),
        ("requests", "Requests"),
        ("advertising_manager", "Advertising"),
        ("website_audience_manager", "Website & Audience"),
        ("news_content_manager", "News & Content"),
        ("inventory", "Inventory"),
        ("broadcasting_manager", "Broadcasting"),
        ("operations_manager", "Operations"),
        ("reports", "Reports"),
        ("settings", "Settings"),
        ("platform_manager", "Platform Manager"),
        ("advanced", "Advanced"),
    )

    NAV_SECTIONS = (
        ("Control", ("daily_operations", "station_manager", "dashboard", "help")),
        (
            "On Air",
            ("programming", "music_manager", "personalities", "voice_library", "schedule", "requests"),
        ),
        ("Station Content", ("advertising_manager", "website_audience_manager", "news_content_manager")),
        ("Operations", ("inventory", "broadcasting_manager", "operations_manager", "reports")),
        ("Setup", ("settings", "platform_manager", "advanced")),
    )

    OFF_NAV_PARENTS = {
        "connection": "advanced",
        "livedj": "advanced",
        "station_information": "station_manager",
        "news": "news_content_manager",
        "automation": "operations_manager",
        "advertising": "advertising_manager",
        "setup_wizard": "settings",
        "updates": "settings",
    }

    PRIMARY_PAGES = frozenset(page_id for page_id, _label in NAV_ITEMS)

    def __init__(
        self,
        parent: tk.Misc,
        on_navigate: Callable[[str], None],
        settings: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(parent, style="StudioNav.TFrame", width=StudioTheme.NAV_WIDTH)
        self.pack_propagate(False)
        self._on_navigate = on_navigate
        self._buttons: dict[str, ttk.Button] = {}
        self._active_id = "daily_operations"
        self._settings = settings or {}
        self._body = ttk.Frame(self, style="StudioNav.TFrame")
        self._body.pack(fill="both", expand=True)
        self._render()

    def refresh(self, settings: dict[str, Any] | None = None) -> None:
        if settings is not None:
            self._settings = settings
        for child in self._body.winfo_children():
            child.destroy()
        self._buttons.clear()
        self._render()

    def _render(self) -> None:
        header = ttk.Label(
            self._body,
            text="Mo's Place Studio",
            font=(StudioTheme.FONT_FAMILY, 10, "bold"),
            foreground=StudioTheme.TEXT_PRIMARY,
            background=StudioTheme.BG_NAV,
        )
        header.pack(anchor="w", padx=16, pady=(16, 10))

        labels = {page_id: label for page_id, label in self.NAV_ITEMS}
        for section_title, page_ids in visible_nav_sections(self.NAV_SECTIONS, self._settings):
            ttk.Label(
                self._body,
                text=section_title.upper(),
                style="StudioNavSection.TLabel",
            ).pack(anchor="w", padx=16, pady=(10, 4))
            for page_id in page_ids:
                label = labels[page_id]
                button = ttk.Button(
                    self._body,
                    text=label,
                    style="StudioNav.TButton",
                    bootstyle="secondary",
                    command=lambda pid=page_id: self.select(pid),
                )
                button.pack(fill="x", padx=12, pady=2)
                self._buttons[page_id] = button

    def select(self, page_id: str, *, notify: bool = True) -> None:
        highlight_id = self.OFF_NAV_PARENTS.get(page_id, page_id)
        if highlight_id not in self._buttons:
            return
        self._active_id = highlight_id
        for pid, button in self._buttons.items():
            if pid == highlight_id:
                button.configure(style="StudioNavActive.TButton", bootstyle="primary")
            else:
                button.configure(style="StudioNav.TButton", bootstyle="secondary")
        if notify:
            self._on_navigate(page_id)

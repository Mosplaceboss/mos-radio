"""LiveDJ integration overview page."""

from __future__ import annotations

import ttkbootstrap as ttk

from app.core.paths import config_dir
from app.pages.base_page import BasePage


class LiveDJPage(BasePage):
    page_id = "livedj"
    page_title = "LiveDJ"
    page_subtitle = "LiveDJ automation integration — configuration managed here, engine runs separately"

    def build(self) -> None:
        panel = ttk.Labelframe(
            self._body,
            text="LiveDJ Automation",
            style="StudioCard.TLabelframe",
            padding=20,
        )
        panel.pack(fill="x")

        lines = (
            "The LiveDJ automation engine in Automation/LiveDJ is not modified by Studio.",
            "Personalities, voice library, and schedule data in Studio/config are structured",
            "for future consumption by LiveDJ during safe integration.",
            f"Configuration directory: {config_dir()}",
            "Planned integration points: personality routing, show schedules, and voice playback.",
        )
        for line in lines:
            ttk.Label(panel, text=line, style="StudioCard.TLabel", wraplength=720).pack(anchor="w", pady=4)

        links = ttk.Labelframe(
            self._body,
            text="Shared Configuration Files",
            style="StudioCard.TLabelframe",
            padding=20,
        )
        links.pack(fill="x", pady=16)
        for filename in ("personalities.json", "voice_library.json", "schedule.json"):
            ttk.Label(links, text=f"• {filename}", style="StudioCard.TLabel").pack(anchor="w", pady=2)

    def on_show(self) -> None:
        self.set_status("LiveDJ page — external automation engine")

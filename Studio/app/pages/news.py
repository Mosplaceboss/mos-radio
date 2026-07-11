"""News integration overview page."""

from __future__ import annotations

import ttkbootstrap as ttk

from app.core.paths import config_dir
from app.pages.base_page import BasePage


class NewsPage(BasePage):
    page_id = "news"
    page_title = "News"
    page_subtitle = "News automation integration — configuration managed here, engine runs separately"

    def build(self) -> None:
        panel = ttk.Labelframe(
            self._body,
            text="News Automation",
            style="StudioCard.TLabelframe",
            padding=20,
        )
        panel.pack(fill="x")

        lines = (
            "The News automation engine in Automation/News is not modified by Studio.",
            "Studio will publish shared configuration that News can consume when integration is enabled.",
            f"Configuration directory: {config_dir()}",
            "Planned integration points: voice assignments, segment timing, and bulletin sources.",
        )
        for line in lines:
            ttk.Label(panel, text=line, style="StudioCard.TLabel", wraplength=720).pack(anchor="w", pady=4)

        status = ttk.Labelframe(
            self._body,
            text="Current Status",
            style="StudioCard.TLabelframe",
            padding=20,
        )
        status.pack(fill="x", pady=16)
        ttk.Label(
            status,
            text="News engine: External (not controlled by Studio)",
            style="StudioCard.TLabel",
        ).pack(anchor="w", pady=2)
        ttk.Label(
            status,
            text="Studio role: Configuration publisher only",
            style="StudioCard.TLabel",
        ).pack(anchor="w", pady=2)

    def on_show(self) -> None:
        self.set_status("News page — external automation engine")

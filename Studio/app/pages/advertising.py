"""Advertising placeholder for Studio v2."""

from __future__ import annotations

import ttkbootstrap as ttk

from app.pages.base_page import BasePage


class AdvertisingPage(BasePage):
    page_id = "advertising"
    page_title = "Advertising"
    page_subtitle = "Manage sponsors, liners, and commercial breaks"
    page_help = "Advertising tools will be added in a future Studio release. Your current schedules and automation are unchanged."

    def build(self) -> None:
        card = ttk.Labelframe(self._body, text="Coming Soon", style="StudioCard.TLabelframe", padding=24)
        card.pack(fill="x")
        ttk.Label(
            card,
            text=(
                "This area will help you organize sponsors, ad schedules, and commercial inventory.\n"
                "For now, continue using your existing programming and automation screens."
            ),
            style="StudioCard.TLabel",
            wraplength=720,
            justify="left",
        ).pack(anchor="w")

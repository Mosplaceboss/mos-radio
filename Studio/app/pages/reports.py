"""Station reports placeholder for Studio v2."""

from __future__ import annotations

import ttkbootstrap as ttk

from app.pages.base_page import BasePage


class ReportsPage(BasePage):
    page_id = "reports"
    page_title = "Reports"
    page_subtitle = "Review station activity and operational summaries"
    page_help = "Detailed reporting will be added in a future Studio release. Use the Dashboard for live status today."

    def build(self) -> None:
        card = ttk.Labelframe(self._body, text="Station Reports", style="StudioCard.TLabelframe", padding=24)
        card.pack(fill="x")
        ttk.Label(
            card,
            text=(
                "Future reports will summarize requests, news runs, automation health, and programming changes.\n"
                "Open the Dashboard for current on-air status and service health."
            ),
            style="StudioCard.TLabel",
            wraplength=720,
            justify="left",
        ).pack(anchor="w", pady=(0, 16))
        ttk.Button(
            card,
            text="Open Dashboard",
            style="StudioAction.TButton",
            bootstyle="primary",
            command=lambda: self.on_navigate and self.on_navigate("dashboard"),
        ).pack(anchor="w")

"""Reusable hub pages with large navigation cards."""

from __future__ import annotations

import ttkbootstrap as ttk

from app.pages.base_page import BasePage
from app.ui.theme import StudioTheme


class HubPage(BasePage):
    """Simple landing page that routes to other Studio screens."""

    hub_links: tuple[tuple[str, str, str], ...] = ()

    def build(self) -> None:
        intro = ttk.Label(
            self._body,
            text="Choose a section below.",
            style="StudioSubheading.TLabel",
        )
        intro.pack(anchor="w", pady=(0, 16))

        grid = ttk.Frame(self._body, style="Studio.TFrame")
        grid.pack(fill="both", expand=True)

        for index, (page_id, title, description) in enumerate(self.hub_links):
            card = ttk.Labelframe(grid, text=title, style="StudioCard.TLabelframe", padding=16)
            card.grid(row=index // 2, column=index % 2, sticky="nsew", padx=10, pady=10)
            ttk.Label(card, text=description, style="StudioCard.TLabel", wraplength=360, justify="left").pack(
                anchor="w", pady=(0, 12)
            )
            ttk.Button(
                card,
                text=f"Open {title}",
                style="StudioAction.TButton",
                bootstyle="primary",
                command=lambda pid=page_id: self._open_page(pid),
            ).pack(anchor="w")
            grid.columnconfigure(index % 2, weight=1)
            grid.rowconfigure(index // 2, weight=1)

    def _open_page(self, page_id: str) -> None:
        if self.on_navigate:
            self.on_navigate(page_id)

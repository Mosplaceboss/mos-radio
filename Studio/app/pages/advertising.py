"""Advertising legacy route — redirects to Advertising Manager."""

from __future__ import annotations

from app.pages.base_page import BasePage


class AdvertisingPage(BasePage):
    page_id = "advertising"
    page_title = "Advertising"
    page_subtitle = "Manage sponsors, liners, and commercial breaks"
    page_help = "Advertising is managed in the Advertising Manager screen."

    def build(self) -> None:
        pass

    def on_show(self) -> None:
        if self.on_navigate:
            self.on_navigate("advertising_manager")

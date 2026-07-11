"""Base class for Studio content pages."""

from __future__ import annotations

import tkinter as tk
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Callable

import ttkbootstrap as ttk

if TYPE_CHECKING:
    from app.core.config_manager import ConfigManager


class BasePage(ttk.Frame, ABC):
    """Shared lifecycle for modular Studio pages."""

    page_id: str = "base"
    page_title: str = "Page"
    page_subtitle: str = ""

    def __init__(
        self,
        parent: tk.Misc,
        config_manager: ConfigManager,
        on_status: Callable[[str], None],
        on_navigate: Callable[[str], None] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(parent, style="Studio.TFrame", **kwargs)
        self.config_manager = config_manager
        self.on_status = on_status
        self.on_navigate = on_navigate
        self._header = ttk.Frame(self, style="Studio.TFrame")
        self._header.pack(fill="x", padx=24, pady=(20, 12))
        self._title = ttk.Label(
            self._header,
            text=self.page_title,
            style="StudioHeading.TLabel",
        )
        self._title.pack(anchor="w")
        if self.page_subtitle:
            ttk.Label(
                self._header,
                text=self.page_subtitle,
                style="StudioSubheading.TLabel",
            ).pack(anchor="w", pady=(4, 0))
        self._body = ttk.Frame(self, style="Studio.TFrame")
        self._body.pack(fill="both", expand=True, padx=24, pady=(0, 20))
        self.build()

    @abstractmethod
    def build(self) -> None:
        """Construct page widgets."""

    def on_show(self) -> None:
        """Called when the page becomes visible."""

    def set_status(self, message: str) -> None:
        self.on_status(message)

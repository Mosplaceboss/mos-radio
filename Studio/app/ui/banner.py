"""Top banner with Mo's Place Radio branding."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path

import ttkbootstrap as ttk
from PIL import Image, ImageTk

from app.core.paths import assets_dir
from app.ui.theme import StudioTheme


class BannerBar(ttk.Frame):
    """Header banner displaying the station logo and application title."""

    def __init__(self, parent: tk.Misc, station_name: str) -> None:
        super().__init__(parent, style="StudioBanner.TFrame", height=StudioTheme.BANNER_HEIGHT)
        self.pack_propagate(False)

        self._logo_image: ImageTk.PhotoImage | None = None
        logo_path = assets_dir() / "logo.png"
        if logo_path.exists():
            image = Image.open(logo_path)
            image.thumbnail((56, 56), Image.Resampling.LANCZOS)
            self._logo_image = ImageTk.PhotoImage(image)
            ttk.Label(self, image=self._logo_image, style="StudioTitle.TLabel").pack(
                side="left", padx=(20, 12), pady=8
            )

        text_frame = ttk.Frame(self, style="StudioBanner.TFrame")
        text_frame.pack(side="left", pady=12)
        ttk.Label(
            text_frame,
            text=station_name,
            style="StudioTitle.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            text_frame,
            text="Studio Management",
            style="StudioSubtitle.TLabel",
        ).pack(anchor="w")

        ttk.Label(
            self,
            text="Development",
            bootstyle="info",
        ).pack(side="right", padx=20)

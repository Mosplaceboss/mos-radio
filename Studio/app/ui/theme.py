"""RadioDJ-inspired theme constants and style helpers."""

from __future__ import annotations

import ttkbootstrap as ttk
from ttkbootstrap.constants import *


class StudioTheme:
    """Central theme values for consistent Studio styling."""

    BOOTSTRAP_THEME = "darkly"

    BG_DARK = "#141820"
    BG_PANEL = "#1c2330"
    BG_NAV = "#11161f"
    BG_BANNER = "#0d1118"
    ACCENT = "#3d8bfd"
    ACCENT_HOVER = "#5a9dff"
    TEXT_PRIMARY = "#e8edf5"
    TEXT_MUTED = "#8b95a8"
    BORDER = "#2a3344"
    SUCCESS = "#3ecf8e"
    WARNING = "#f0ad4e"
    DANGER = "#e74c3c"

    NAV_WIDTH = 220
    BANNER_HEIGHT = 72
    STATUS_HEIGHT = 28

    @classmethod
    def apply_custom_styles(cls, style: ttk.Style) -> None:
        style.configure(
            "Studio.TFrame",
            background=cls.BG_DARK,
        )
        style.configure(
            "StudioPanel.TFrame",
            background=cls.BG_PANEL,
        )
        style.configure(
            "StudioNav.TFrame",
            background=cls.BG_NAV,
        )
        style.configure(
            "StudioBanner.TFrame",
            background=cls.BG_BANNER,
        )
        style.configure(
            "StudioStatus.TFrame",
            background=cls.BG_NAV,
        )
        style.configure(
            "StudioTitle.TLabel",
            background=cls.BG_BANNER,
            foreground=cls.TEXT_PRIMARY,
            font=("Segoe UI", 18, "bold"),
        )
        style.configure(
            "StudioSubtitle.TLabel",
            background=cls.BG_BANNER,
            foreground=cls.TEXT_MUTED,
            font=("Segoe UI", 10),
        )
        style.configure(
            "StudioHeading.TLabel",
            background=cls.BG_DARK,
            foreground=cls.TEXT_PRIMARY,
            font=("Segoe UI", 16, "bold"),
        )
        style.configure(
            "StudioSubheading.TLabel",
            background=cls.BG_DARK,
            foreground=cls.TEXT_MUTED,
            font=("Segoe UI", 11),
        )
        style.configure(
            "StudioCard.TLabelframe",
            background=cls.BG_PANEL,
            foreground=cls.TEXT_PRIMARY,
            bordercolor=cls.BORDER,
            relief="solid",
        )
        style.configure(
            "StudioCard.TLabelframe.Label",
            background=cls.BG_PANEL,
            foreground=cls.ACCENT,
            font=("Segoe UI", 11, "bold"),
        )
        style.configure(
            "StudioCard.TLabel",
            background=cls.BG_PANEL,
            foreground=cls.TEXT_PRIMARY,
            font=("Segoe UI", 10),
        )
        style.configure(
            "StudioMuted.TLabel",
            background=cls.BG_PANEL,
            foreground=cls.TEXT_MUTED,
            font=("Segoe UI", 9),
        )
        style.configure(
            "StudioNav.TButton",
            font=("Segoe UI", 10),
            padding=(12, 10),
            anchor="w",
        )
        style.configure(
            "StudioNavActive.TButton",
            font=("Segoe UI", 10, "bold"),
            padding=(12, 10),
            anchor="w",
        )
        style.configure(
            "StudioStatus.TLabel",
            background=cls.BG_NAV,
            foreground=cls.TEXT_MUTED,
            font=("Segoe UI", 9),
        )

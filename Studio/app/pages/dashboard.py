"""Dashboard overview page."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import ttkbootstrap as ttk
from ttkbootstrap.constants import *

from app.core.paths import config_dir
from app.core.requests_model import effective_cooldown_hours, normalize_requests_data, request_mode_label
from app.core.voice_model import normalize_voice_library_data
from app.pages.base_page import BasePage
from app.ui.theme import StudioTheme


class DashboardPage(BasePage):
    page_id = "dashboard"
    page_title = "Dashboard"
    page_subtitle = "Station configuration overview and quick status"

    def build(self) -> None:
        self._cards_frame = ttk.Frame(self._body, style="Studio.TFrame")
        self._cards_frame.pack(fill="x", pady=(0, 16))

        self._summary_frame = ttk.Frame(self._body, style="Studio.TFrame")
        self._summary_frame.pack(fill="both", expand=True)

        self._card_labels: dict[str, ttk.Label] = {}
        self._detail_labels: dict[str, ttk.Label] = {}

        card_specs = (
            ("personalities", "Personalities"),
            ("voices", "Voice Library"),
            ("schedule", "Schedule Slots"),
            ("requests", "Request Settings"),
        )
        for index, (key, title) in enumerate(card_specs):
            card = ttk.Labelframe(
                self._cards_frame,
                text=title,
                style="StudioCard.TLabelframe",
                padding=16,
            )
            card.grid(row=0, column=index, padx=(0, 12), sticky="nsew")
            self._cards_frame.columnconfigure(index, weight=1)

            value_label = ttk.Label(card, text="—", style="StudioCard.TLabel", font=("Segoe UI", 22, "bold"))
            value_label.pack(anchor="w")
            detail_label = ttk.Label(card, text="", style="StudioMuted.TLabel")
            detail_label.pack(anchor="w", pady=(6, 0))
            self._card_labels[key] = value_label
            self._detail_labels[key] = detail_label

        left = ttk.Labelframe(
            self._summary_frame,
            text="Configuration Health",
            style="StudioCard.TLabelframe",
            padding=16,
        )
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))

        self._health_list = ttk.Frame(left, style="StudioPanel.TFrame")
        self._health_list.pack(fill="both", expand=True)

        right = ttk.Labelframe(
            self._summary_frame,
            text="Studio Notes",
            style="StudioCard.TLabelframe",
            padding=16,
        )
        right.pack(side="left", fill="both", expand=True, padx=(8, 0))

        notes = (
            "Studio is the management layer for Mo's Place Radio.",
            "Live automation engines are not modified by this application.",
            "Configuration files in Studio/config are designed for future",
            "consumption by LiveDJ, News, and Requests automation.",
        )
        for line in notes:
            ttk.Label(right, text=line, style="StudioCard.TLabel", wraplength=360).pack(anchor="w", pady=2)

        refresh_row = ttk.Frame(self._body, style="Studio.TFrame")
        refresh_row.pack(fill="x", pady=(12, 0))
        ttk.Button(
            refresh_row,
            text="Refresh Dashboard",
            bootstyle="primary",
            command=self.refresh,
        ).pack(side="left")
        self._last_refresh = ttk.Label(refresh_row, text="", style="StudioSubheading.TLabel")
        self._last_refresh.pack(side="left", padx=12)

    def on_show(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        personalities = self.config_manager.load("personalities", {"personalities": []})
        voices = normalize_voice_library_data(self.config_manager.load("voice_library", {"voices": []}))
        schedule = self.config_manager.load("schedule", {"slots": []})
        requests = normalize_requests_data(self.config_manager.load("requests", {}))

        personality_list = personalities.get("personalities", [])
        voice_list = voices.get("voices", [])
        slot_list = schedule.get("slots", [])

        active_personalities = sum(1 for item in personality_list if item.get("active", True))
        self._card_labels["personalities"].configure(text=str(len(personality_list)))
        self._detail_labels["personalities"].configure(
            text=f"{active_personalities} active personality profile(s)"
        )

        self._card_labels["voices"].configure(text=str(len(voice_list)))
        voicebox_count = sum(1 for item in voice_list if item.get("voicebox_id"))
        self._detail_labels["voices"].configure(text=f"{voicebox_count} Voicebox voice(s)")

        self._card_labels["schedule"].configure(text=str(len(slot_list)))
        days = sorted({slot.get("day", "").title() for slot in slot_list if slot.get("day")})
        self._detail_labels["schedule"].configure(
            text=f"Scheduled on {len(days)} day(s)" if days else "No schedule slots yet"
        )

        mode_label = request_mode_label(requests.get("request_mode", "by_schedule"))
        cooldown_hours = effective_cooldown_hours(requests)
        self._card_labels["requests"].configure(text=mode_label)
        self._detail_labels["requests"].configure(
            text=f"Cooldown: {cooldown_hours} hr · Limit: {requests.get('requests_per_listener', 0)}/user"
        )

        for child in self._health_list.winfo_children():
            child.destroy()

        for config_name in ("personalities", "voice_library", "schedule", "requests", "settings"):
            self._add_health_row(config_name)

        timestamp = datetime.now().strftime("%I:%M:%S %p")
        self._last_refresh.configure(text=f"Last refreshed: {timestamp}")
        self.set_status("Dashboard refreshed")

    def _add_health_row(self, config_name: str) -> None:
        file_path = config_dir() / f"{config_name}.json"
        row = ttk.Frame(self._health_list, style="StudioPanel.TFrame")
        row.pack(fill="x", pady=4)

        if file_path.exists():
            modified = datetime.fromtimestamp(file_path.stat().st_mtime).strftime("%Y-%m-%d %I:%M %p")
            status = "OK"
            bootstyle = "success"
            detail = f"Last modified {modified}"
        else:
            status = "Missing"
            bootstyle = "danger"
            detail = "Configuration file not found"

        ttk.Label(row, text=config_name, style="StudioCard.TLabel", width=18).pack(side="left")
        ttk.Label(row, text=status, bootstyle=bootstyle, width=10).pack(side="left", padx=8)
        ttk.Label(row, text=detail, style="StudioMuted.TLabel").pack(side="left")

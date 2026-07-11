"""Request settings management page."""

from __future__ import annotations

import ttkbootstrap as ttk
from ttkbootstrap.constants import *

from app.pages.base_page import BasePage


class RequestsPage(BasePage):
    page_id = "requests"
    page_title = "Requests"
    page_subtitle = "Configure listener request limits for the Requests automation engine"

    def build(self) -> None:
        form = ttk.Labelframe(
            self._body,
            text="Request Settings",
            style="StudioCard.TLabelframe",
            padding=20,
        )
        form.pack(fill="x")

        self._enabled = ttk.BooleanVar(value=True)
        self._cooldown = ttk.IntVar(value=300)
        self._per_user_limit = ttk.IntVar(value=3)
        self._per_user_period = ttk.IntVar(value=24)
        self._max_queue = ttk.IntVar(value=50)
        self._duplicate_cooldown = ttk.IntVar(value=60)
        self._announce = ttk.BooleanVar(value=True)

        ttk.Checkbutton(form, text="Requests enabled", variable=self._enabled).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=6
        )
        ttk.Checkbutton(form, text="Announce accepted requests on air", variable=self._announce).grid(
            row=1, column=0, columnspan=2, sticky="w", pady=6
        )

        fields = (
            ("Cooldown between requests (seconds)", self._cooldown),
            ("Per-user request limit", self._per_user_limit),
            ("Per-user limit period (hours)", self._per_user_period),
            ("Maximum queue length", self._max_queue),
            ("Duplicate track cooldown (minutes)", self._duplicate_cooldown),
        )
        for row_index, (label, variable) in enumerate(fields, start=2):
            ttk.Label(form, text=label, style="StudioCard.TLabel").grid(
                row=row_index, column=0, sticky="w", pady=8, padx=(0, 16)
            )
            ttk.Spinbox(form, from_=0, to=10000, textvariable=variable, width=12).grid(
                row=row_index, column=1, sticky="w", pady=8
            )

        actions = ttk.Frame(self._body, style="Studio.TFrame")
        actions.pack(fill="x", pady=16)
        ttk.Button(actions, text="Reload", bootstyle="secondary", command=self._load).pack(side="left")
        ttk.Button(actions, text="Save Settings", bootstyle="primary", command=self._save).pack(side="left", padx=8)

        info = ttk.Labelframe(
            self._body,
            text="Automation Integration",
            style="StudioCard.TLabelframe",
            padding=16,
        )
        info.pack(fill="x")
        ttk.Label(
            info,
            text=(
                "These settings are written to Studio/config/requests.json. "
                "The Requests automation engine can read this file when integration is enabled."
            ),
            style="StudioCard.TLabel",
            wraplength=720,
        ).pack(anchor="w")

    def on_show(self) -> None:
        self._load()

    def _load(self) -> None:
        data = self.config_manager.load("requests", {})
        self._enabled.set(data.get("enabled", True))
        self._cooldown.set(data.get("cooldown_seconds", 300))
        self._per_user_limit.set(data.get("per_user_limit", 3))
        self._per_user_period.set(data.get("per_user_period_hours", 24))
        self._max_queue.set(data.get("max_queue_length", 50))
        self._duplicate_cooldown.set(data.get("duplicate_track_cooldown_minutes", 60))
        self._announce.set(data.get("announce_requests", True))
        self.set_status("Request settings loaded")

    def _save(self) -> None:
        data = {
            "enabled": self._enabled.get(),
            "cooldown_seconds": self._cooldown.get(),
            "per_user_limit": self._per_user_limit.get(),
            "per_user_period_hours": self._per_user_period.get(),
            "max_queue_length": self._max_queue.get(),
            "duplicate_track_cooldown_minutes": self._duplicate_cooldown.get(),
            "announce_requests": self._announce.get(),
        }
        self.config_manager.save("requests", data)
        self.set_status("Request settings saved")

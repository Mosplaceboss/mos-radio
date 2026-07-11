"""Application settings page."""

from __future__ import annotations

import ttkbootstrap as ttk
from ttkbootstrap.constants import *

from app.pages.base_page import BasePage


class SettingsPage(BasePage):
    page_id = "settings"
    page_title = "Settings"
    page_subtitle = "Studio application preferences"

    def build(self) -> None:
        form = ttk.Labelframe(
            self._body,
            text="General",
            style="StudioCard.TLabelframe",
            padding=20,
        )
        form.pack(fill="x")

        self._station_name = ttk.StringVar()
        self._timezone = ttk.StringVar()
        self._log_level = ttk.StringVar()
        self._auto_save = ttk.BooleanVar(value=True)
        self._theme = ttk.StringVar()

        fields = (
            ("Station Name", self._station_name, None),
            ("Timezone", self._timezone, None),
            ("Log Level", self._log_level, ("DEBUG", "INFO", "WARNING", "ERROR")),
            ("Theme", self._theme, ("darkly", "cyborg", "superhero")),
        )
        for row, (label, variable, choices) in enumerate(fields):
            ttk.Label(form, text=label, style="StudioCard.TLabel").grid(
                row=row, column=0, sticky="w", pady=8, padx=(0, 16)
            )
            if choices:
                widget = ttk.Combobox(form, textvariable=variable, values=list(choices), state="readonly", width=28)
            else:
                widget = ttk.Entry(form, textvariable=variable, width=30)
            widget.grid(row=row, column=1, sticky="w", pady=8)

        ttk.Checkbutton(form, text="Auto-save configuration changes", variable=self._auto_save).grid(
            row=len(fields), column=0, columnspan=2, sticky="w", pady=8
        )

        actions = ttk.Frame(self._body, style="Studio.TFrame")
        actions.pack(fill="x", pady=16)
        ttk.Button(actions, text="Reload", bootstyle="secondary", command=self._load).pack(side="left")
        ttk.Button(actions, text="Save Settings", bootstyle="primary", command=self._save).pack(side="left", padx=8)

    def on_show(self) -> None:
        self._load()

    def _load(self) -> None:
        data = self.config_manager.load("settings", {})
        self._station_name.set(data.get("station_name", "Mo's Place Radio"))
        self._timezone.set(data.get("timezone", "America/New_York"))
        self._log_level.set(data.get("log_level", "INFO"))
        self._auto_save.set(data.get("auto_save", True))
        self._theme.set(data.get("theme", "darkly"))
        self.set_status("Application settings loaded")

    def _save(self) -> None:
        data = {
            "station_name": self._station_name.get().strip(),
            "timezone": self._timezone.get().strip(),
            "log_level": self._log_level.get(),
            "auto_save": self._auto_save.get(),
            "theme": self._theme.get(),
        }
        self.config_manager.save("settings", data)
        self.set_status("Application settings saved — restart Studio to apply theme changes")

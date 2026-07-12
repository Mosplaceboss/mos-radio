"""Station Information — branding, contact, and default voice settings."""

from __future__ import annotations

import shutil
import tkinter as tk
from tkinter import filedialog
from pathlib import Path

import ttkbootstrap as ttk
from PIL import Image, ImageTk

from app.core.background_tasks import run_in_background
from app.core.personality_model import display_label, normalize_personalities_data
from app.core.station_data import (
    load_station_info,
    save_station_info,
    station_logos_dir,
)
from app.core.voice_model import normalize_voice_library_data
from app.pages.base_page import BasePage
from app.ui.theme import StudioTheme

TIMEZONES = (
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Los_Angeles",
    "America/Phoenix",
    "UTC",
)


class StationInformationPage(BasePage):
    page_id = "station_information"
    page_title = "Station Information"
    page_subtitle = "Station identity, contact details, and default voices"
    page_help = (
        "This information is stored in your platform StationData folder and is used across Studio screens."
    )

    def build(self) -> None:
        self._field_vars: dict[str, tk.Variable] = {}
        self._logo_image: ImageTk.PhotoImage | None = None
        self._busy = False

        toolbar = ttk.Frame(self._body, style="Studio.TFrame")
        toolbar.pack(fill="x", pady=(0, 12))
        ttk.Button(
            toolbar,
            text="Save Station Information",
            style="StudioAction.TButton",
            bootstyle="primary",
            command=self._save,
        ).pack(side="right")
        ttk.Button(
            toolbar,
            text="Back to Station Manager",
            bootstyle="secondary",
            command=lambda: self._open_page("station_manager"),
        ).pack(side="left")

        panes = ttk.Panedwindow(self._body, orient="horizontal", bootstyle="secondary")
        panes.pack(fill="both", expand=True)

        identity = ttk.Labelframe(panes, text="Station Identity", style="StudioCard.TLabelframe", padding=16)
        panes.add(identity, weight=2)

        logo_row = ttk.Frame(identity, style="StudioPanel.TFrame")
        logo_row.pack(fill="x", pady=(0, 12))
        self._logo_frame = ttk.Frame(logo_row, style="StudioPanel.TFrame", width=120, height=120)
        self._logo_frame.pack(side="left")
        self._logo_frame.pack_propagate(False)
        self._logo_label = ttk.Label(self._logo_frame, text="No Logo", style="StudioMuted.TLabel", anchor="center")
        self._logo_label.pack(fill="both", expand=True)
        logo_buttons = ttk.Frame(logo_row, style="StudioPanel.TFrame")
        logo_buttons.pack(side="left", padx=16)
        ttk.Label(logo_buttons, text="Station Logo", style="StudioCard.TLabel").pack(anchor="w")
        ttk.Button(logo_buttons, text="Upload Logo", bootstyle="secondary", command=self._upload_logo).pack(
            anchor="w", pady=(8, 4)
        )
        ttk.Button(logo_buttons, text="Remove Logo", bootstyle="secondary", command=self._remove_logo).pack(anchor="w")

        identity_fields = (
            ("station_name", "Station Name"),
            ("slogan", "Slogan"),
            ("website", "Website"),
            ("facebook", "Facebook"),
            ("instagram", "Instagram"),
            ("youtube", "YouTube"),
            ("email", "Email"),
            ("phone", "Phone"),
            ("address", "Address"),
        )
        for key, label in identity_fields:
            self._add_row(identity, key, label)

        timezone_row = ttk.Frame(identity, style="StudioPanel.TFrame")
        timezone_row.pack(fill="x", pady=4)
        ttk.Label(timezone_row, text="Default Time Zone", style="StudioMuted.TLabel", width=22).pack(side="left")
        self._timezone = tk.StringVar()
        ttk.Combobox(
            timezone_row,
            textvariable=self._timezone,
            values=TIMEZONES,
            state="readonly",
        ).pack(side="left", fill="x", expand=True)
        self._field_vars["timezone"] = self._timezone

        defaults = ttk.Labelframe(panes, text="Default Voices & Personality", style="StudioCard.TLabelframe", padding=16)
        panes.add(defaults, weight=2)
        default_fields = (
            ("default_station_voice", "Default Station Voice"),
            ("default_news_voice", "Default News Voice"),
            ("default_weather_voice", "Default Weather Voice"),
            ("default_request_voice", "Default Request Voice"),
            ("default_ai_personality", "Default AI Personality"),
        )
        for key, label in default_fields:
            row = ttk.Frame(defaults, style="StudioPanel.TFrame")
            row.pack(fill="x", pady=4)
            ttk.Label(row, text=label, style="StudioMuted.TLabel", width=24).pack(side="left")
            variable = tk.StringVar()
            combo = ttk.Combobox(row, textvariable=variable, state="readonly")
            combo.pack(side="left", fill="x", expand=True)
            self._field_vars[key] = variable
            setattr(self, f"_{key}_combo", combo)

    def on_show(self) -> None:
        self._load()

    def _add_row(self, parent: ttk.Labelframe, key: str, label: str) -> None:
        row = ttk.Frame(parent, style="StudioPanel.TFrame")
        row.pack(fill="x", pady=4)
        ttk.Label(row, text=label, style="StudioMuted.TLabel", width=22).pack(side="left")
        variable = tk.StringVar()
        ttk.Entry(row, textvariable=variable).pack(side="left", fill="x", expand=True)
        self._field_vars[key] = variable

    def _load(self) -> None:
        settings = self.config_manager.load("settings", {})
        data = load_station_info(self.config_manager, settings)
        for key, variable in self._field_vars.items():
            variable.set(data.get(key, ""))
        self._populate_choices()
        self._show_logo(data.get("logo_path", ""))

    def _populate_choices(self) -> None:
        voices_data = normalize_voice_library_data(self.config_manager.load("voice_library", {"voices": []}))
        personalities_data = normalize_personalities_data(
            self.config_manager.load("personalities", {"personalities": []})
        )
        voice_labels = [""] + [
            voice.get("display_name", voice.get("id", ""))
            for voice in voices_data.get("voices", [])
            if voice.get("active", True)
        ]
        personality_labels = [""] + [
            display_label(personality)
            for personality in personalities_data.get("personalities", [])
            if personality.get("active", True)
        ]
        for key in (
            "default_station_voice",
            "default_news_voice",
            "default_weather_voice",
            "default_request_voice",
        ):
            combo = getattr(self, f"_{key}_combo")
            combo.configure(values=voice_labels)
        self._default_ai_personality_combo.configure(values=personality_labels)

    def _collect(self) -> dict[str, str]:
        return {key: variable.get().strip() for key, variable in self._field_vars.items()}

    def _save(self) -> None:
        if self._busy:
            return
        self._busy = True
        settings = self.config_manager.load("settings", {})
        payload = self._collect()
        existing = load_station_info(self.config_manager, settings)
        payload["logo_path"] = existing.get("logo_path", "")

        def work() -> dict:
            saved = save_station_info(payload, self.config_manager, settings)
            settings["station_name"] = saved.get("station_name", settings.get("station_name", ""))
            settings["timezone"] = saved.get("timezone", settings.get("timezone", "America/New_York"))
            self.config_manager.save("settings", settings)
            return saved

        def complete(saved: dict) -> None:
            self._busy = False
            self.set_status("Station information saved.")

        def failed(error: Exception) -> None:
            self._busy = False
            self._show_error_dialog("Save Station Information", str(error))

        self.set_status("Saving station information…")
        run_in_background(self, work, complete, on_error=failed)

    def _upload_logo(self) -> None:
        selected = filedialog.askopenfilename(
            title="Select Station Logo",
            filetypes=(("Image files", "*.png;*.jpg;*.jpeg;*.gif;*.webp"), ("All files", "*.*")),
        )
        if not selected:
            return
        source = Path(selected)
        destination = station_logos_dir(self.config_manager) / source.name
        shutil.copy2(source, destination)
        data = load_station_info(self.config_manager)
        data["logo_path"] = str(destination)
        save_station_info(data, self.config_manager)
        self._show_logo(str(destination))
        self.set_status("Station logo uploaded.")

    def _remove_logo(self) -> None:
        data = load_station_info(self.config_manager)
        data["logo_path"] = ""
        save_station_info(data, self.config_manager)
        self._show_logo("")
        self.set_status("Station logo removed.")

    def _show_logo(self, path_value: str) -> None:
        self._logo_image = None
        if path_value and Path(path_value).exists():
            image = Image.open(path_value)
            image.thumbnail((110, 110), Image.Resampling.LANCZOS)
            self._logo_image = ImageTk.PhotoImage(image)
            self._logo_label.configure(image=self._logo_image, text="")
        else:
            self._logo_label.configure(image="", text="No Logo")

    def _open_page(self, page_id: str) -> None:
        if self.on_navigate:
            self.on_navigate(page_id)

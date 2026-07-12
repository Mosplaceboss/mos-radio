"""Application settings page."""

from __future__ import annotations

import tkinter as tk

import ttkbootstrap as ttk
from ttkbootstrap.constants import *

from app.core.background_tasks import run_in_background
from app.core.voice_library_loader import read_json_with_timeout
from app.pages.base_page import BasePage


class SettingsPage(BasePage):
    page_id = "settings"
    page_title = "Settings"
    page_subtitle = "Studio preferences, operation mode, and integration paths"

    def build(self) -> None:
        self._load_generation = 0
        self._load_in_progress = False

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
        self._operation_mode = ttk.StringVar(value="development")

        fields = (
            ("Station Name", self._station_name, None),
            ("Timezone", self._timezone, None),
            ("Operation Mode", self._operation_mode, ("development", "production")),
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

        integration = ttk.Labelframe(
            self._body,
            text="Integration",
            style="StudioCard.TLabelframe",
            padding=20,
        )
        integration.pack(fill="x", pady=(16, 0))
        self._radiodj_process = ttk.StringVar()
        self._voicebox_url = ttk.StringVar()
        self._livedj_personalities = ttk.StringVar()
        self._requests_config = ttk.StringVar()
        self._news_config = ttk.StringVar()

        integration_fields = (
            ("RadioDJ Process", self._radiodj_process),
            ("Voicebox API URL", self._voicebox_url),
            ("LiveDJ Personalities Path", self._livedj_personalities),
            ("Requests Config Path", self._requests_config),
            ("News Config Path", self._news_config),
        )
        for row, (label, variable) in enumerate(integration_fields):
            ttk.Label(integration, text=label, style="StudioCard.TLabel").grid(
                row=row, column=0, sticky="w", pady=8, padx=(0, 16)
            )
            ttk.Entry(integration, textvariable=variable, width=72).grid(row=row, column=1, sticky="ew", pady=8)
        integration.columnconfigure(1, weight=1)

        actions = ttk.Frame(self._body, style="Studio.TFrame")
        actions.pack(fill="x", pady=16)
        ttk.Button(actions, text="Reload", bootstyle="secondary", command=self._load).pack(side="left")
        ttk.Button(actions, text="Save Settings", bootstyle="primary", command=self._save).pack(side="left", padx=8)

    def on_show(self) -> None:
        self._begin_background_load()

    def on_hide(self) -> None:
        self._load_generation += 1
        self._load_in_progress = False
        self._show_busy_cursor(False)

    def _begin_background_load(self) -> None:
        self._load_generation += 1
        generation = self._load_generation
        self._load_in_progress = True
        path = self.config_manager.path_for("settings")

        def work():
            return read_json_with_timeout(path, {}, timeout=5.0)

        def complete(result: tuple[dict, str | None]) -> None:
            if generation != self._load_generation:
                return
            self._load_in_progress = False
            self._show_busy_cursor(False)
            data, error = result
            if error:
                self._show_error_dialog("Settings", error)
                return
            self.config_manager._cache["settings"] = data
            self._apply_settings(data)
            self.set_status("Application settings loaded")

        def failed(error: Exception) -> None:
            if generation != self._load_generation:
                return
            self._load_in_progress = False
            self._show_busy_cursor(False)
            self._show_error_dialog("Settings", str(error))

        self._show_busy_cursor(True)
        self.set_status("Loading settings…")
        run_in_background(self, work, complete, on_error=failed)

    def _apply_settings(self, data: dict) -> None:
        integration = data.get("integration", {})
        live_paths = integration.get("live_paths", {})
        livedj_paths = live_paths.get("livedj", {})
        requests_paths = live_paths.get("requests", {})
        news_paths = live_paths.get("news", {})

        self._station_name.set(data.get("station_name", "Mo's Place Radio"))
        self._timezone.set(data.get("timezone", "America/New_York"))
        self._operation_mode.set(data.get("operation_mode", "development"))
        self._log_level.set(data.get("log_level", "INFO"))
        self._auto_save.set(data.get("auto_save", True))
        self._theme.set(data.get("theme", "darkly"))
        self._radiodj_process.set(integration.get("radiodj_process", "RadioDJ.exe"))
        self._voicebox_url.set(integration.get("voicebox_api_url", "http://127.0.0.1:7860"))
        self._livedj_personalities.set(
            livedj_paths.get("personalities", "Automation/LiveDJ/personalities.json")
        )
        self._requests_config.set(requests_paths.get("config", "Automation/Requests/requests.json"))
        self._news_config.set(news_paths.get("config", "Automation/News/news.json"))

    def _load(self) -> None:
        self._begin_background_load()

    def _save(self) -> None:
        existing = self.config_manager._cache.get("settings") or self.config_manager.load("settings", {})
        integration = existing.get("integration", {})
        live_paths = integration.get("live_paths", {})
        livedj_paths = live_paths.get("livedj", {})
        requests_paths = live_paths.get("requests", {})
        news_paths = live_paths.get("news", {})

        integration.update(
            {
                "radiodj_process": self._radiodj_process.get().strip(),
                "voicebox_api_url": self._voicebox_url.get().strip(),
            }
        )
        livedj_paths["personalities"] = self._livedj_personalities.get().strip()
        requests_paths["config"] = self._requests_config.get().strip()
        news_paths["config"] = self._news_config.get().strip()
        live_paths["livedj"] = livedj_paths
        live_paths["requests"] = requests_paths
        live_paths["news"] = news_paths
        integration["live_paths"] = live_paths

        data = {
            "station_name": self._station_name.get().strip(),
            "timezone": self._timezone.get().strip(),
            "operation_mode": self._operation_mode.get().strip(),
            "log_level": self._log_level.get(),
            "auto_save": self._auto_save.get(),
            "theme": self._theme.get(),
            "integration": integration,
        }
        self._persist_config_async(
            "settings",
            data,
            status_message="Application settings saved — production mode requires extra publish confirmation",
            error_title="Save Settings",
        )

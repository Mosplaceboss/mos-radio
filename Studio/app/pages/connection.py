"""Connection Setup — configure and test live station connections."""

from __future__ import annotations

import tkinter as tk

import ttkbootstrap as ttk
from ttkbootstrap.dialogs import Messagebox

from app.core.background_tasks import run_in_background
from app.core.health_constants import HEALTH_ERROR, HEALTH_OK, HEALTH_WARN
from app.core.live_connector import (
    ConnectionResult,
    build_local_from_station,
    ensure_local_integration_template,
    import_livedj_personalities_readonly,
    import_livedj_schedule_readonly,
    import_news_status_readonly,
    import_request_settings_readonly,
    load_station_connection,
    save_local_integration,
    test_connection_setup,
)
from app.core.platform_manager import platform_path
from app.pages.base_page import BasePage
from app.ui.theme import StudioTheme

STATUS_STYLES = {
    HEALTH_OK: ("success", "Connected"),
    HEALTH_WARN: ("warning", "Warning"),
    HEALTH_ERROR: ("danger", "Not Connected"),
}


class ConnectionSetupPage(BasePage):
    page_id = "connection"
    page_title = "Connection Setup"
    page_subtitle = "Link Studio to your station computers and import live settings"
    page_help = "Advanced screen. Connect paths, test access, and bring in read-only copies of live data."

    def build(self) -> None:
        self._fields: dict[str, tk.StringVar] = {}
        self._status_rows: dict[str, tuple[ttk.Label, ttk.Label]] = {}
        self._busy = False

        toolbar = ttk.Frame(self._body, style="Studio.TFrame")
        toolbar.pack(fill="x", pady=(0, 12))
        ttk.Button(toolbar, text="Test Connections", bootstyle="info", command=self._test_connections).pack(side="left")
        ttk.Button(toolbar, text="Save Settings", bootstyle="primary", command=self._save_settings).pack(side="right")
        ttk.Button(
            toolbar,
            text="Use Local Automation Folders",
            bootstyle="secondary",
            command=self._use_local_defaults,
        ).pack(side="right", padx=8)

        form = ttk.Labelframe(self._body, text="Live Station Settings", style="StudioCard.TLabelframe", padding=16)
        form.pack(fill="x", pady=(0, 12))
        specs = (
            ("radio_pc", "Radio PC Name / IP"),
            ("livedj_folder", "LiveDJ Folder Path"),
            ("news_folder", "News Folder Path"),
            ("requests_folder", "Request Watcher Folder Path"),
            ("radiodj_executable", "RadioDJ Executable Path"),
            ("voicebox_api_url", "Voicebox API Address"),
        )
        for key, label in specs:
            row = ttk.Frame(form, style="StudioPanel.TFrame")
            row.pack(fill="x", pady=4)
            ttk.Label(row, text=label, style="StudioMuted.TLabel", width=30).pack(side="left")
            variable = tk.StringVar()
            ttk.Entry(row, textvariable=variable).pack(side="left", fill="x", expand=True)
            self._fields[key] = variable

        status = ttk.Labelframe(self._body, text="Connection Test Results", style="StudioCard.TLabelframe", padding=16)
        status.pack(fill="x", pady=(0, 12))
        for name in (
            "Radio PC",
            "LiveDJ",
            "News",
            "Request Watcher",
            "RadioDJ",
            "Voicebox API",
            "Internet",
        ):
            row = ttk.Frame(status, style="StudioPanel.TFrame")
            row.pack(fill="x", pady=3)
            ttk.Label(row, text=name, style="StudioCard.TLabel", width=18).pack(side="left")
            badge = ttk.Label(row, text="—", width=14)
            badge.pack(side="left", padx=8)
            message = ttk.Label(row, text="Not tested yet.", style="StudioMuted.TLabel", wraplength=520, justify="left")
            message.pack(side="left", fill="x", expand=True)
            self._status_rows[name] = (badge, message)

        imports = ttk.Labelframe(
            self._body,
            text="Read-Only Import (does not change live files)",
            style="StudioCard.TLabelframe",
            padding=16,
        )
        imports.pack(fill="x")
        ttk.Label(
            imports,
            text="Import live copies into Studio for viewing and editing. Live station files are not modified.",
            style="StudioMuted.TLabel",
            wraplength=760,
        ).pack(anchor="w", pady=(0, 8))
        buttons = ttk.Frame(imports, style="StudioPanel.TFrame")
        buttons.pack(fill="x")
        import_specs = (
            ("Import LiveDJ Personalities", self._import_personalities),
            ("Import LiveDJ Schedule", self._import_schedule),
            ("Import News Status", self._import_news),
            ("Import Request Settings", self._import_requests),
        )
        for index, (label, command) in enumerate(import_specs):
            ttk.Button(buttons, text=label, bootstyle="secondary", command=command).grid(
                row=index // 2, column=index % 2, sticky="ew", padx=8, pady=6
            )
            buttons.columnconfigure(index % 2, weight=1)

    def on_show(self) -> None:
        ensure_local_integration_template()
        self._load_settings()

    def _settings(self) -> dict:
        return self.config_manager.load("settings", {})

    def _collect_station(self) -> dict[str, str]:
        return {key: self._fields[key].get().strip() for key in self._fields}

    def _load_settings(self) -> None:
        station = load_station_connection()
        for key, variable in self._fields.items():
            variable.set(station.get(key, ""))
        self.set_status("Connection settings loaded")

    def _save_settings(self) -> None:
        station = self._collect_station()
        save_local_integration(build_local_from_station(station, enabled=True))
        self.set_status("Connection settings saved")

    def _use_local_defaults(self) -> None:
        self._fields["livedj_folder"].set(str(platform_path("automation_livedj")))
        self._fields["news_folder"].set(str(platform_path("automation_news")))
        self._fields["requests_folder"].set(str(platform_path("automation_requests")))
        self._fields["radiodj_executable"].set(str(platform_path("radiodj")))
        self._save_settings()

    def _apply_results(self, results: list[ConnectionResult]) -> None:
        for name, widgets in self._status_rows.items():
            widgets[0].configure(text="—", bootstyle="secondary")
            widgets[1].configure(text="Not tested yet.")
        for result in results:
            widgets = self._status_rows.get(result.name)
            if not widgets:
                continue
            badge, message = widgets
            bootstyle, label = STATUS_STYLES.get(result.status, ("secondary", "Unknown"))
            badge.configure(text=label, bootstyle=bootstyle)
            message.configure(text=result.message)

    def _test_connections(self) -> None:
        if self._busy:
            return
        self._busy = True
        save_local_integration(build_local_from_station(self._collect_station(), enabled=True))
        settings = self._settings()

        def work():
            return test_connection_setup(settings)

        def complete(results: list[ConnectionResult]) -> None:
            self._busy = False
            self._apply_results(results)
            ok_count = sum(1 for result in results if result.status == HEALTH_OK)
            self.set_status(f"Connection test complete · {ok_count}/{len(results)} connected")

        def failed(_error: Exception) -> None:
            self._busy = False
            self.set_status("Connection test failed")

        run_in_background(self, work, complete, on_error=failed)

    def _run_import(self, label: str, importer) -> None:
        if self._busy:
            return
        self._busy = True
        save_local_integration(build_local_from_station(self._collect_station(), enabled=True))
        settings = self._settings()

        def work():
            return importer(settings)

        def complete(result: tuple[bool, str]) -> None:
            self._busy = False
            ok, message = result
            for key in ("personalities", "schedule", "news", "requests"):
                self.config_manager._cache.pop(key, None)
            if ok:
                Messagebox.show_info(message, label)
            else:
                Messagebox.show_warning(message, label)
            self.set_status(message)

        def failed(_error: Exception) -> None:
            self._busy = False
            self.set_status(f"{label} failed")

        run_in_background(self, work, complete, on_error=failed)

    def _import_personalities(self) -> None:
        self._run_import("Import LiveDJ Personalities", import_livedj_personalities_readonly)

    def _import_schedule(self) -> None:
        self._run_import("Import LiveDJ Schedule", import_livedj_schedule_readonly)

    def _import_news(self) -> None:
        self._run_import("Import News Status", import_news_status_readonly)

    def _import_requests(self) -> None:
        self._run_import("Import Request Settings", import_request_settings_readonly)

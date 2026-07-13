"""First-Run Setup Wizard — configure Studio without editing code."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog

import ttkbootstrap as ttk
from ttkbootstrap.dialogs import Messagebox

from app.core.background_tasks import run_in_background
from app.core.health_constants import HEALTH_ERROR, HEALTH_OK, HEALTH_WARN
from app.core.setup_wizard_model import (
    SetupWizardData,
    SetupWizardSnapshot,
    apply_setup,
    copy_station_logo,
    load_setup_data,
    test_setup,
)
from app.pages.base_page import BasePage
from app.ui.theme import StudioTheme

STATUS_STYLES = {
    HEALTH_OK: ("success", "Ready"),
    HEALTH_WARN: ("warning", "Attention"),
    HEALTH_ERROR: ("danger", "Problem"),
}


class SetupWizardPage(BasePage):
    page_id = "setup_wizard"
    page_title = "First-Run Setup"
    page_subtitle = "Configure Mo's Place Studio in plain English"
    page_help = "Complete these steps once. You can reopen this wizard later from Settings."

    def build(self) -> None:
        self._busy = False
        self._fields: dict[str, tk.StringVar] = {}
        self._test_rows: dict[str, tuple[ttk.Label, ttk.Label]] = {}

        toolbar = ttk.Frame(self._body, style="Studio.TFrame")
        toolbar.pack(fill="x", pady=(0, 12))
        ttk.Button(toolbar, text="Test All Connections", bootstyle="info", command=self._test).pack(side="left")
        ttk.Button(toolbar, text="Save and Finish Setup", bootstyle="primary", command=self._finish).pack(side="right")
        ttk.Button(toolbar, text="Upload Logo", bootstyle="secondary", command=self._upload_logo).pack(side="right", padx=8)

        form = ttk.Labelframe(self._body, text="Station and Platform Paths", style="StudioCard.TLabelframe", padding=16)
        form.pack(fill="x", pady=(0, 12))
        specs = (
            ("station_name", "Station Name"),
            ("platform_root", "Platform Root"),
            ("radiodj_path", "RadioDJ Path"),
            ("music_library_path", "Music Library Path"),
            ("voicebox_api_url", "Voicebox API"),
            ("voice_output_path", "Shared Voice Output Folder"),
            ("livedj_folder", "LiveDJ Folder"),
            ("news_folder", "News Folder"),
            ("requests_folder", "Request Watcher Folder"),
            ("website_folder", "Website Folder"),
            ("radio_pc", "Radio PC Name / IP"),
        )
        for key, label in specs:
            row = ttk.Frame(form, style="StudioPanel.TFrame")
            row.pack(fill="x", pady=4)
            ttk.Label(row, text=label, style="StudioMuted.TLabel", width=30).pack(side="left")
            variable = tk.StringVar()
            ttk.Entry(row, textvariable=variable).pack(side="left", fill="x", expand=True)
            self._fields[key] = variable

        results = ttk.Labelframe(self._body, text="Connection Test Results", style="StudioCard.TLabelframe", padding=16)
        results.pack(fill="both", expand=True)
        self._results_frame = ttk.Frame(results, style="StudioPanel.TFrame")
        self._results_frame.pack(fill="both", expand=True)
        self._load_fields()

    def on_show(self) -> None:
        self._load_fields()

    def _load_fields(self) -> None:
        data = load_setup_data(self.config_manager)
        mapping = {
            "station_name": data.station_name,
            "platform_root": data.platform_root,
            "radiodj_path": data.radiodj_path,
            "music_library_path": data.music_library_path,
            "voicebox_api_url": data.voicebox_api_url,
            "voice_output_path": data.voice_output_path,
            "livedj_folder": data.livedj_folder,
            "news_folder": data.news_folder,
            "requests_folder": data.requests_folder,
            "website_folder": data.website_folder,
            "radio_pc": data.radio_pc,
        }
        for key, value in mapping.items():
            if key in self._fields:
                self._fields[key].set(value)

    def _collect_data(self) -> SetupWizardData:
        return SetupWizardData(
            station_name=self._fields["station_name"].get().strip() or "Mo's Place Radio",
            platform_root=self._fields["platform_root"].get().strip(),
            radiodj_path=self._fields["radiodj_path"].get().strip(),
            music_library_path=self._fields["music_library_path"].get().strip(),
            voicebox_api_url=self._fields["voicebox_api_url"].get().strip(),
            voice_output_path=self._fields["voice_output_path"].get().strip(),
            livedj_folder=self._fields["livedj_folder"].get().strip(),
            news_folder=self._fields["news_folder"].get().strip(),
            requests_folder=self._fields["requests_folder"].get().strip(),
            website_folder=self._fields["website_folder"].get().strip(),
            radio_pc=self._fields["radio_pc"].get().strip(),
        )

    def _upload_logo(self) -> None:
        path = filedialog.askopenfilename(
            title="Choose station logo",
            filetypes=(("Image files", "*.png;*.jpg;*.jpeg;*.webp"), ("All files", "*.*")),
        )
        if not path:
            return
        try:
            saved = copy_station_logo(Path(path))
            self.set_status(f"Logo saved to {saved}")
        except OSError as exc:
            self._show_error_dialog("Upload Logo", str(exc))

    def _test(self) -> None:
        if self._busy:
            return
        self._busy = True
        payload = self._collect_data()

        def work() -> SetupWizardSnapshot:
            return test_setup(payload, self.config_manager)

        def complete(snapshot: SetupWizardSnapshot) -> None:
            self._busy = False
            self._render_results(snapshot.path_results + snapshot.connection_results)
            self.set_status("Connection tests completed")

        def failed(error: Exception) -> None:
            self._busy = False
            self._show_error_dialog("Test Connections", str(error))

        run_in_background(self, work, complete, on_error=failed)

    def _render_results(self, results) -> None:
        for child in self._results_frame.winfo_children():
            child.destroy()
        self._test_rows.clear()
        for index, result in enumerate(results):
            row = ttk.Frame(self._results_frame, style="StudioPanel.TFrame")
            row.pack(fill="x", pady=3)
            ttk.Label(row, text=result.name, style="StudioCard.TLabel", width=22).pack(side="left")
            style, label = STATUS_STYLES.get(result.status, ("secondary", result.status.upper()))
            badge = ttk.Label(row, text=label, bootstyle=style, width=12)
            badge.pack(side="left", padx=8)
            message = ttk.Label(row, text=result.message, style="StudioMuted.TLabel", wraplength=560, justify="left")
            message.pack(side="left", fill="x", expand=True)
            self._test_rows[result.name] = (badge, message)

    def _finish(self) -> None:
        if self._busy:
            return
        if not Messagebox.yesno("Save these settings and mark setup complete?", title="Finish Setup"):
            return
        self._busy = True
        payload = self._collect_data()

        def work() -> None:
            apply_setup(payload, self.config_manager)

        def complete(_: None) -> None:
            self._busy = False
            self.set_status("Setup saved successfully")
            Messagebox.show_info(
                "Mo's Place Studio is ready.\n\nOpen Daily Operations to begin today's work.",
                "Setup Complete",
            )
            if self.on_navigate:
                self.on_navigate("daily_operations")

        def failed(error: Exception) -> None:
            self._busy = False
            self._show_error_dialog("Finish Setup", str(error))

        run_in_background(self, work, lambda _: complete(None), on_error=failed)

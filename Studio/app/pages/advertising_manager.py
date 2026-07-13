"""Advertising Manager."""

from __future__ import annotations

import tkinter as tk
from copy import deepcopy
from datetime import datetime

import ttkbootstrap as ttk
from ttkbootstrap.scrolled import ScrolledText

from app.core.advertising_model import build_overview_lines, normalize_bundle, validate_advertising
from app.core.advertising_storage import load_advertising_bundle, save_advertising_bundle
from app.core.background_tasks import run_in_background
from app.core.platform_manager import open_folder, platform_path
from app.pages.base_page import BasePage


class AdvertisingManagerPage(BasePage):
    page_id = "advertising_manager"
    page_title = "Advertising Manager"
    page_subtitle = "Manage sponsors, campaigns, and commercial planning"
    page_help = "Development advertising data is stored in StationData. Live automation is not modified."

    def build(self) -> None:
        self._bundle = normalize_bundle({})
        self._busy = False
        toolbar = ttk.Frame(self._body, style="Studio.TFrame")
        toolbar.pack(fill="x", pady=(0, 12))
        ttk.Button(
            toolbar, text="Save Advertising Data", style="StudioAction.TButton", bootstyle="primary", command=self._save
        ).pack(side="right")
        ttk.Button(toolbar, text="Open Advertising Folder", bootstyle="secondary", command=self._open_folder).pack(side="left")
        ttk.Button(toolbar, text="Reload", bootstyle="secondary", command=self._load).pack(side="left", padx=8)

        self._notebook = ttk.Notebook(self._body, bootstyle="primary")
        self._notebook.pack(fill="both", expand=True)
        overview = ttk.Frame(self._notebook, style="Studio.TFrame", padding=12)
        self._notebook.add(overview, text="Overview")
        self._overview_text = ScrolledText(overview, height=18, autohide=True, bootstyle="secondary", state="disabled", wrap="word")
        self._overview_text.pack(fill="both", expand=True)

        sponsors = ttk.Frame(self._notebook, style="Studio.TFrame", padding=12)
        self._notebook.add(sponsors, text="Sponsors")
        self._sponsors_tree = ttk.Treeview(sponsors, columns=("name", "enabled"), show="headings", bootstyle="info", height=12)
        self._sponsors_tree.heading("name", text="Sponsor")
        self._sponsors_tree.heading("enabled", text="Active")
        self._sponsors_tree.pack(fill="both", expand=True)

        validation = ttk.Frame(self._notebook, style="Studio.TFrame", padding=12)
        self._notebook.add(validation, text="Validation")
        self._validation_text = ScrolledText(
            validation, height=18, autohide=True, bootstyle="secondary", state="disabled", wrap="word"
        )
        self._validation_text.pack(fill="both", expand=True)

    def on_show(self) -> None:
        self._load()

    def _load(self) -> None:
        self._bundle = normalize_bundle(load_advertising_bundle(self.config_manager))
        self._refresh_views()
        self.set_status("Advertising data loaded")

    def _save(self) -> None:
        if self._busy:
            return
        self._busy = True
        payload = deepcopy(self._bundle)

        def work() -> None:
            save_advertising_bundle(payload, self.config_manager)

        def complete(_: None) -> None:
            self._busy = False
            self.set_status("Advertising data saved")

        run_in_background(self, work, lambda _: complete(None), on_error=lambda e: self._finish_error(e))

    def _finish_error(self, error: Exception) -> None:
        self._busy = False
        self._show_error_dialog("Advertising Manager", str(error))

    def _open_folder(self) -> None:
        try:
            open_folder(str(platform_path("automation_advertising", self.config_manager)))
            self.set_status("Opened advertising folder.")
        except OSError as exc:
            self._show_error_dialog("Open Advertising Folder", str(exc))

    def _refresh_views(self) -> None:
        self._set_text(self._overview_text, "\n".join(build_overview_lines(self._bundle, self.config_manager)))
        self._sponsors_tree.delete(*self._sponsors_tree.get_children())
        for sponsor in self._bundle["sponsors"]["sponsors"]:
            self._sponsors_tree.insert(
                "",
                "end",
                iid=sponsor["id"],
                values=(sponsor.get("name", ""), "Yes" if sponsor.get("enabled") else "No"),
            )
        warnings = validate_advertising(self._bundle, self.config_manager)
        self._bundle["state"]["last_validated"] = datetime.now().strftime("%Y-%m-%d %I:%M %p")
        text = "\n".join(f"• {w}" for w in warnings) if warnings else "No validation warnings."
        self._set_text(self._validation_text, text)

    @staticmethod
    def _set_text(widget: ScrolledText, content: str) -> None:
        widget.text.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("end", content)
        widget.text.configure(state="disabled")

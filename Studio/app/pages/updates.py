"""Updates — install approved packages with backup and rollback."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog

import ttkbootstrap as ttk
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.scrolled import ScrolledText

from app.core.background_tasks import run_in_background
from app.core.update_manager import (
    apply_update_package,
    installed_version_info,
    load_update_history,
    rollback_last_update,
)
from app.core.user_modes import is_advanced_mode
from app.pages.base_page import BasePage
from app.ui.confirm_dialog import confirm_action


class UpdatesPage(BasePage):
    page_id = "updates"
    page_title = "Updates"
    page_subtitle = "Install approved Studio updates with automatic backup and rollback"
    page_help = "Advanced screen. Import an approved update package ZIP. Your settings and data are preserved."

    def build(self) -> None:
        self._busy = False
        info = installed_version_info()
        header = ttk.Labelframe(self._body, text="Installed Version", style="StudioCard.TLabelframe", padding=16)
        header.pack(fill="x", pady=(0, 12))
        self._version_label = ttk.Label(
            header,
            text=f"{info['label']}  ·  version {info['version']}",
            style="StudioCard.TLabel",
        )
        self._version_label.pack(anchor="w")
        ttk.Label(header, text=f"Studio folder: {info['studio_root']}", style="StudioMuted.TLabel").pack(anchor="w", pady=(6, 0))

        toolbar = ttk.Frame(self._body, style="Studio.TFrame")
        toolbar.pack(fill="x", pady=(0, 12))
        ttk.Button(toolbar, text="Import Update Package", bootstyle="primary", command=self._import_update).pack(side="left")
        ttk.Button(toolbar, text="Roll Back Last Update", bootstyle="warning", command=self._rollback).pack(side="left", padx=8)
        ttk.Button(toolbar, text="Refresh History", bootstyle="secondary", command=self._refresh_history).pack(side="left")

        self._history_text = ScrolledText(self._body, height=18, autohide=True, bootstyle="secondary", state="disabled", wrap="word")
        self._history_text.pack(fill="both", expand=True)

    def on_show(self) -> None:
        settings = self.config_manager.load("settings", {})
        if not is_advanced_mode(settings):
            self._set_text(
                self._history_text,
                "Updates are available in Advanced Mode only.\n\nSwitch to Advanced Mode in Settings to manage updates.",
            )
            return
        self._refresh_history()

    def _refresh_history(self) -> None:
        records = load_update_history()
        lines = ["Update History", ""]
        if not records:
            lines.append("No updates have been applied yet.")
        else:
            for record in records:
                lines.append(f"• {record.get('label', record.get('version', 'Update'))}")
                lines.append(f"  Applied: {record.get('applied_at', 'Unknown')}")
                lines.append(f"  Backup: {record.get('backup_path', '—')}")
                lines.append("")
        self._set_text(self._history_text, "\n".join(lines))

    @staticmethod
    def _set_text(widget: ScrolledText, content: str) -> None:
        widget.text.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("end", content)
        widget.text.configure(state="disabled")

    def _import_update(self) -> None:
        settings = self.config_manager.load("settings", {})
        if not is_advanced_mode(settings):
            Messagebox.show_warning("Switch to Advanced Mode in Settings first.", "Updates")
            return
        if not confirm_action(
            "Import Update",
            "Import an approved update package?\n\nStudio will back up your current configuration first.",
            settings,
        ):
            return
        path = filedialog.askopenfilename(
            title="Choose update package",
            filetypes=(("ZIP files", "*.zip"), ("All files", "*.*")),
        )
        if not path:
            return
        if self._busy:
            return
        self._busy = True
        package = Path(path)

        def work() -> tuple[bool, str]:
            return apply_update_package(package)

        def complete(result: tuple[bool, str]) -> None:
            self._busy = False
            ok, message = result
            if ok:
                Messagebox.show_info(message, "Update Applied")
            else:
                self._show_error_dialog("Update Failed", message)
            self._refresh_history()
            self.set_status(message)

        run_in_background(self, work, complete, on_error=lambda e: self._finish_error(e))

    def _rollback(self) -> None:
        settings = self.config_manager.load("settings", {})
        if not confirm_action("Roll Back", "Restore the previous version from the last backup?", settings):
            return
        if self._busy:
            return
        self._busy = True

        def work() -> tuple[bool, str]:
            return rollback_last_update()

        def complete(result: tuple[bool, str]) -> None:
            self._busy = False
            ok, message = result
            if ok:
                Messagebox.show_info(message, "Rollback Complete")
            else:
                self._show_error_dialog("Rollback Failed", message)
            self._refresh_history()
            self.set_status(message)

        run_in_background(self, work, complete, on_error=lambda e: self._finish_error(e))

    def _finish_error(self, error: Exception) -> None:
        self._busy = False
        self._show_error_dialog("Updates", str(error))

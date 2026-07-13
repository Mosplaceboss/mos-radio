"""Inventory hub — open Mo's Place Inventory and view scan status."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import ttkbootstrap as ttk
from ttkbootstrap.scrolled import ScrolledText

from app.core.background_tasks import run_in_background
from app.core.hidden_process import popen_hidden
from app.core.integration_snapshot import _inventory_status
from app.core.paths import repo_root
from app.core.platform_manager import open_folder
from app.core.station_data import inventory_reports_dir
from app.pages.base_page import BasePage


class InventoryPage(BasePage):
    page_id = "inventory"
    page_title = "Inventory"
    page_subtitle = "Read-only station file inventory and scan reports"
    page_help = (
        "Mo's Place Inventory scans folders without changing them. "
        "Use this screen to open Inventory or review the latest scan report."
    )

    def build(self) -> None:
        toolbar = ttk.Frame(self._body, style="Studio.TFrame")
        toolbar.pack(fill="x", pady=(0, 12))
        ttk.Button(toolbar, text="Open Inventory App", style="StudioAction.TButton", bootstyle="primary", command=self._launch_inventory).pack(
            side="left"
        )
        ttk.Button(toolbar, text="Open Reports Folder", bootstyle="secondary", command=self._open_reports).pack(side="left", padx=8)
        ttk.Button(toolbar, text="Refresh", bootstyle="secondary", command=self._refresh).pack(side="left")

        self._status_text = ScrolledText(self._body, height=10, autohide=True, bootstyle="secondary", state="disabled", wrap="word")
        self._status_text.pack(fill="x", pady=(0, 12))

        self._detail_text = ScrolledText(self._body, height=16, autohide=True, bootstyle="secondary", state="disabled", wrap="word")
        self._detail_text.pack(fill="both", expand=True)

    def on_show(self) -> None:
        self._refresh()

    def _inventory_exe(self) -> Path | None:
        candidates = (
            repo_root() / "Inventory" / "dist" / "MoPlaceInventory" / "MoPlaceInventory.exe",
            repo_root() / "Inventory" / "dist" / "MoPlaceInventory.exe",
        )
        for path in candidates:
            if path.exists():
                return path
        return None

    def _launch_inventory(self) -> None:
        exe = self._inventory_exe()
        if exe:
            try:
                popen_hidden([str(exe)], cwd=exe.parent)
                self.set_status("Launched Mo's Place Inventory.")
                return
            except OSError as exc:
                self._show_error_dialog("Open Inventory", str(exc))
                return
        # Fall back to python module if dev environment.
        main_py = repo_root() / "Inventory" / "app" / "main.py"
        if main_py.exists():
            try:
                popen_hidden([sys.executable, str(main_py)], cwd=main_py.parent.parent)
                self.set_status("Launched Inventory in development mode.")
            except OSError as exc:
                self._show_error_dialog("Open Inventory", str(exc))
        else:
            self._show_error_dialog(
                "Open Inventory",
                "Inventory app not found. Build it with Tools\\Build_Inventory_EXE.bat.",
            )

    def _open_reports(self) -> None:
        try:
            open_folder(str(inventory_reports_dir(self.config_manager)))
            self.set_status("Opened inventory reports folder.")
        except OSError as exc:
            self._show_error_dialog("Open Reports", str(exc))

    def _refresh(self) -> None:
        def work() -> tuple[str, str]:
            status, message = _inventory_status(self.config_manager)
            return status, message

        def complete(result: tuple[str, str]) -> None:
            status, message = result
            self._set_text(self._status_text, f"Status: {status.upper()}\n{message}")
            detail_lines = [message, ""]
            report = inventory_reports_dir(self.config_manager) / "Inventory.json"
            if report.exists():
                try:
                    data = json.loads(report.read_text(encoding="utf-8"))
                    detail_lines.extend(
                        [
                            f"Scanned at: {data.get('scanned_at', '—')}",
                            f"Office PC: {data.get('office_pc', '—')}",
                            f"Components: {len(data.get('components', []))}",
                            f"Errors: {len(data.get('errors', []))}",
                        ]
                    )
                except (OSError, json.JSONDecodeError):
                    detail_lines.append("Could not read Inventory.json details.")
            else:
                detail_lines.append("Run Mo's Place Inventory to create your first scan report.")
            self._set_text(self._detail_text, "\n".join(detail_lines))
            self.set_status("Inventory status refreshed")

        run_in_background(self, work, complete, on_error=lambda e: self._show_error_dialog("Inventory", str(e)))

    @staticmethod
    def _set_text(widget: ScrolledText, content: str) -> None:
        widget.text.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("end", content)
        widget.text.configure(state="disabled")

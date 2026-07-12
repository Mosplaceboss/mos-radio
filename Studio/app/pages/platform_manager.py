"""Platform Manager — configure every production folder path."""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog

import ttkbootstrap as ttk
from ttkbootstrap.scrolled import ScrolledFrame

from app.core.background_tasks import run_in_background
from app.core.health_constants import HEALTH_ERROR, HEALTH_OK, HEALTH_WARN
from app.core.platform_manager import (
    PATH_DEFINITIONS,
    default_path_for_key,
    load_platform_config,
    managed_folder_count,
    normalize_platform_config,
    open_folder,
    save_platform_config,
    test_platform_path,
    validate_all_paths,
)
from app.pages.base_page import BasePage
from app.ui.theme import StudioTheme

STATUS_STYLES = {
    HEALTH_OK: ("success", "Ready"),
    HEALTH_WARN: ("warning", "Attention"),
    HEALTH_ERROR: ("danger", "Not Found"),
}


class PlatformManagerPage(BasePage):
    page_id = "platform_manager"
    page_title = "Platform Manager"
    page_subtitle = "Single source of truth for every production folder"
    page_help = (
        "Set and test every folder used by Mo's Place Studio. "
        "Green means the path is ready. Red means Studio cannot find it yet."
    )

    def build(self) -> None:
        self._path_vars: dict[str, tk.StringVar] = {}
        self._status_badges: dict[str, ttk.Label] = {}
        self._status_messages: dict[str, ttk.Label] = {}
        self._busy = False

        summary = ttk.Labelframe(self._body, text="Platform Overview", style="StudioCard.TLabelframe", padding=16)
        summary.pack(fill="x", pady=(0, 12))

        top = ttk.Frame(summary, style="StudioPanel.TFrame")
        top.pack(fill="x")
        ttk.Label(top, text="Platform Root", style="StudioMetricTitle.TLabel").pack(anchor="w")
        self._platform_root_label = ttk.Label(top, text="—", style="StudioHero.TLabel", wraplength=900, justify="left")
        self._platform_root_label.pack(anchor="w", pady=(4, 12))

        metrics = ttk.Frame(summary, style="StudioPanel.TFrame")
        metrics.pack(fill="x")
        self._folder_count_label = ttk.Label(
            metrics,
            text=f"Folders managed: {managed_folder_count()}",
            style="StudioMetric.TLabel",
        )
        self._folder_count_label.pack(side="left", padx=(0, 24))
        self._last_validated_label = ttk.Label(metrics, text="Last validation: Never", style="StudioCard.TLabel")
        self._last_validated_label.pack(side="left", padx=(0, 24))
        self._validation_status_badge = ttk.Label(metrics, text="Not validated", bootstyle="secondary", padding=(10, 4))
        self._validation_status_badge.pack(side="left")

        toolbar = ttk.Frame(self._body, style="Studio.TFrame")
        toolbar.pack(fill="x", pady=(0, 12))
        ttk.Button(
            toolbar,
            text="Validate All Paths",
            style="StudioAction.TButton",
            bootstyle="info",
            command=self._validate_all,
        ).pack(side="left")
        ttk.Button(
            toolbar,
            text="Save All Paths",
            style="StudioAction.TButton",
            bootstyle="primary",
            command=self._save_all,
        ).pack(side="right")

        scroll_host = ttk.Frame(self._body, style="Studio.TFrame")
        scroll_host.pack(fill="both", expand=True)
        self._scroll = ScrolledFrame(scroll_host, autohide=True, bootstyle="secondary")
        self._scroll.pack(fill="both", expand=True)
        container = self._scroll.container

        current_category = ""
        for key, definition in PATH_DEFINITIONS.items():
            category = definition["category"]
            if category != current_category:
                current_category = category
                ttk.Label(
                    container,
                    text=category,
                    style="StudioHeading.TLabel",
                ).pack(anchor="w", padx=8, pady=(16, 8))

            card = ttk.Labelframe(
                container,
                text=definition["label"],
                style="StudioCard.TLabelframe",
                padding=12,
            )
            card.pack(fill="x", padx=8, pady=6)

            ttk.Label(
                card,
                text=definition["description"],
                style="StudioMuted.TLabel",
                wraplength=820,
                justify="left",
            ).pack(anchor="w", pady=(0, 8))

            path_row = ttk.Frame(card, style="StudioPanel.TFrame")
            path_row.pack(fill="x", pady=(0, 8))
            variable = tk.StringVar()
            ttk.Entry(path_row, textvariable=variable).pack(side="left", fill="x", expand=True, padx=(0, 8))
            ttk.Button(
                path_row,
                text="Browse",
                bootstyle="secondary",
                command=lambda k=key, v=variable: self._browse_path(k, v),
            ).pack(side="left", padx=(0, 4))
            ttk.Button(
                path_row,
                text="Test",
                bootstyle="info",
                command=lambda k=key, v=variable: self._test_single(k, v),
            ).pack(side="left", padx=(0, 4))
            ttk.Button(
                path_row,
                text="Open Folder",
                bootstyle="secondary",
                command=lambda v=variable: self._open_path(v),
            ).pack(side="left", padx=(0, 4))
            ttk.Button(
                path_row,
                text="Reset to Default",
                bootstyle="secondary",
                command=lambda k=key, v=variable: self._reset_single(k, v),
            ).pack(side="left")
            self._path_vars[key] = variable

            status_row = ttk.Frame(card, style="StudioPanel.TFrame")
            status_row.pack(fill="x")
            badge = ttk.Label(status_row, text="Not tested", bootstyle="secondary", width=12)
            badge.pack(side="left", padx=(0, 8))
            message = ttk.Label(status_row, text="—", style="StudioMuted.TLabel", wraplength=700, justify="left")
            message.pack(side="left", fill="x", expand=True)
            self._status_badges[key] = badge
            self._status_messages[key] = message

    def on_show(self) -> None:
        self._load_config()

    def _current_paths(self) -> dict[str, str]:
        return {key: variable.get().strip() for key, variable in self._path_vars.items()}

    def _load_config(self) -> None:
        config = load_platform_config(self.config_manager)
        for key, variable in self._path_vars.items():
            variable.set(config["paths"].get(key, default_path_for_key(key)))
        self._apply_summary(config)

    def _apply_summary(self, config: dict) -> None:
        root_path = config["paths"].get("platform_root", "—")
        self._platform_root_label.configure(text=root_path)
        self._folder_count_label.configure(text=f"Folders managed: {managed_folder_count()}")
        last_validated = config.get("last_validated") or "Never"
        self._last_validated_label.configure(text=f"Last validation: {last_validated}")
        self._set_overall_status(config.get("validation_status", HEALTH_WARN), config.get("validation_results", {}))

    def _set_overall_status(self, status: str, results: dict[str, dict[str, str]]) -> None:
        style, label = STATUS_STYLES.get(status, ("secondary", "Unknown"))
        self._validation_status_badge.configure(text=label, bootstyle=style)
        for key, result in results.items():
            self._apply_row_status(key, result.get("status", HEALTH_WARN), result.get("message", "—"))

    def _apply_row_status(self, key: str, status: str, message: str) -> None:
        badge = self._status_badges.get(key)
        message_label = self._status_messages.get(key)
        if not badge or not message_label:
            return
        style, label = STATUS_STYLES.get(status, ("secondary", "Unknown"))
        badge.configure(text=label, bootstyle=style)
        message_label.configure(text=message)

    def _browse_path(self, key: str, variable: tk.StringVar) -> None:
        initial = variable.get().strip()
        initial_dir = initial if initial and os.path.isdir(initial) else None
        selected = filedialog.askdirectory(title=f"Select {PATH_DEFINITIONS[key]['label']}", initialdir=initial_dir)
        if selected:
            variable.set(selected)

    def _test_single(self, key: str, variable: tk.StringVar) -> None:
        result = test_platform_path(key, variable.get())
        self._apply_row_status(key, result["status"], result["message"])
        self.set_status(f"{PATH_DEFINITIONS[key]['label']}: {result['message']}")

    def _open_path(self, variable: tk.StringVar) -> None:
        try:
            open_folder(variable.get())
            self.set_status("Opened folder in File Explorer.")
        except OSError as exc:
            self._show_error_dialog("Open Folder", str(exc))

    def _reset_single(self, key: str, variable: tk.StringVar) -> None:
        platform_root = self._path_vars["platform_root"].get().strip() or None
        variable.set(default_path_for_key(key, platform_root))
        self.set_status(f"Reset {PATH_DEFINITIONS[key]['label']} to default.")

    def _save_all(self) -> None:
        if self._busy:
            return
        self._busy = True
        payload = normalize_platform_config(
            {
                "paths": self._current_paths(),
                "last_validated": load_platform_config(self.config_manager).get("last_validated", ""),
                "validation_status": load_platform_config(self.config_manager).get("validation_status", HEALTH_WARN),
                "validation_results": load_platform_config(self.config_manager).get("validation_results", {}),
            }
        )

        def work() -> dict:
            return save_platform_config(payload, self.config_manager)

        def complete(saved: dict) -> None:
            self._busy = False
            self._apply_summary(saved)
            self.set_status("Platform paths saved.")

        def failed(error: Exception) -> None:
            self._busy = False
            self._show_error_dialog("Save Platform Paths", str(error))

        self.set_status("Saving platform paths…")
        run_in_background(self, work, complete, on_error=failed)

    def _validate_all(self) -> None:
        if self._busy:
            return
        self._busy = True
        payload = normalize_platform_config({"paths": self._current_paths()})

        def work() -> dict:
            validated = validate_all_paths(payload)
            return save_platform_config(validated, self.config_manager)

        def complete(saved: dict) -> None:
            self._busy = False
            self._apply_summary(saved)
            self.set_status("Platform paths validated.")

        def failed(error: Exception) -> None:
            self._busy = False
            self._show_error_dialog("Validate Platform Paths", str(error))

        self.set_status("Validating platform paths…")
        run_in_background(self, work, complete, on_error=failed)

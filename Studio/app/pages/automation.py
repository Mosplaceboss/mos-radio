"""Automation manager control center."""

from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path

import ttkbootstrap as ttk
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.scrolled import ScrolledFrame

from app.core.operations import (
    refresh_all_statuses,
    restart_livedj_watcher,
    restart_request_watcher,
    run_news_now,
    start_livedj_watcher,
    start_request_watcher,
)
from app.core.publish_manager import integration_bundle
from app.core.system_status import build_live_system_status
from app.core.automation_model import (
    AutomationModuleStatus,
    AutomationSnapshot,
    append_automation_log,
    build_automation_snapshot,
)
from app.core.background_tasks import run_in_background
from app.core.health_constants import HEALTH_ERROR, HEALTH_OK, HEALTH_WARN
from app.pages.base_page import BasePage
from app.ui.confirm_dialog import confirm_action
from app.ui.theme import StudioTheme

REFRESH_INTERVAL_MS = 5000


class AutomationPage(BasePage):
    page_id = "automation"
    page_title = "Automation Manager"
    page_subtitle = "Control center for automation engines, live status, and confirmed operations"

    def build(self) -> None:
        self._refresh_job: str | None = None
        self._selected_module_id: str | None = None
        self._snapshot: AutomationSnapshot | None = None
        self._detail_labels: dict[str, ttk.Label] = {}
        self._refresh_in_progress = False
        self._refresh_cancelled = False
        self._suppress_tree_events = False
        self._refresh_generation = 0

        ops = ttk.Labelframe(self._body, text="Operations", style="StudioCard.TLabelframe", padding=12)
        ops.pack(fill="x", pady=(0, 12))
        ops_specs = (
            ("Start Request Watcher", self._op_start_requests),
            ("Restart Request Watcher", self._op_restart_requests),
            ("Start LiveDJ Watcher", self._op_start_livedj),
            ("Restart LiveDJ Watcher", self._op_restart_livedj),
            ("Run News Now", self._op_run_news),
            ("Refresh All Statuses", self._op_refresh_status),
        )
        for index, (label, command) in enumerate(ops_specs):
            ttk.Button(ops, text=label, bootstyle="primary", command=command).grid(
                row=index // 3, column=index % 3, sticky="ew", padx=6, pady=4
            )
            ops.columnconfigure(index % 3, weight=1)

        header = ttk.Frame(self._body, style="Studio.TFrame")
        header.pack(fill="x", pady=(0, 12))

        summary_card = ttk.Labelframe(header, text="Automation Health", style="StudioCard.TLabelframe", padding=16)
        summary_card.pack(side="left", fill="y")
        self._summary_label = ttk.Label(
            summary_card,
            text="—",
            style="StudioCard.TLabel",
            font=("Segoe UI", 20, "bold"),
        )
        self._summary_label.pack(anchor="w")
        self._summary_detail = ttk.Label(summary_card, text="", style="StudioMuted.TLabel")
        self._summary_detail.pack(anchor="w", pady=(6, 0))

        health_card = ttk.Labelframe(header, text="System Health", style="StudioCard.TLabelframe", padding=16)
        health_card.pack(side="left", fill="both", expand=True, padx=(12, 0))
        self._system_health_frame = ttk.Frame(health_card, style="StudioPanel.TFrame")
        self._system_health_frame.pack(fill="both", expand=True)

        body = ttk.Panedwindow(self._body, orient="horizontal", bootstyle="secondary")
        body.pack(fill="both", expand=True, pady=(0, 12))

        modules_panel = ttk.Labelframe(body, text="Automation Modules", style="StudioCard.TLabelframe", padding=12)
        body.add(modules_panel, weight=2)

        columns = ("name", "enabled", "running", "status")
        self._tree = ttk.Treeview(
            modules_panel,
            columns=columns,
            show="headings",
            bootstyle="info",
            height=14,
            selectmode="browse",
        )
        self._tree.heading("name", text="Module")
        self._tree.heading("enabled", text="Enabled")
        self._tree.heading("running", text="Running")
        self._tree.heading("status", text="Status")
        self._tree.column("name", width=160)
        self._tree.column("enabled", width=80, anchor="center")
        self._tree.column("running", width=90, anchor="center")
        self._tree.column("status", width=90, anchor="center")
        self._tree.pack(fill="both", expand=True)
        self._tree.bind("<<TreeviewSelect>>", self._on_module_select)

        detail_panel = ttk.Labelframe(body, text="Module Details", style="StudioCard.TLabelframe", padding=12)
        body.add(detail_panel, weight=3)

        detail_scroll = ScrolledFrame(detail_panel, autohide=True, bootstyle="secondary")
        detail_scroll.pack(fill="both", expand=True)
        detail_form = detail_scroll.container

        for key, label in (
            ("enabled", "Enabled / Disabled"),
            ("running", "Running / Stopped"),
            ("last_run", "Last Run"),
            ("next_run", "Next Run"),
            ("schedule_source", "Schedule Source"),
            ("configuration_file", "Configuration File"),
            ("log_file", "Log File"),
            ("status", "Status Indicator"),
            ("version", "Version"),
            ("detail", "Details"),
        ):
            row = ttk.Frame(detail_form, style="StudioPanel.TFrame")
            row.pack(fill="x", pady=4)
            ttk.Label(row, text=label, style="StudioMuted.TLabel", width=20).pack(side="left", anchor="nw")
            value = ttk.Label(row, text="—", style="StudioCard.TLabel", wraplength=420, justify="left")
            value.pack(side="left", fill="x", expand=True)
            self._detail_labels[key] = value

        actions = ttk.Frame(detail_panel, style="Studio.TFrame")
        actions.pack(fill="x", pady=(12, 0))
        action_specs = (
            ("Start", "success", self._action_start),
            ("Stop", "danger", self._action_stop),
            ("Restart", "warning", self._action_restart),
            ("Open Configuration", "info", self._action_open_config),
            ("Open Log", "secondary", self._action_open_log),
            ("Test Run", "primary", self._action_test_run),
            ("Health Check", "info", self._action_health_check),
        )
        for index, (label, style, command) in enumerate(action_specs):
            ttk.Button(actions, text=label, bootstyle=style, command=command).grid(
                row=index // 4, column=index % 4, sticky="ew", padx=4, pady=4
            )
            actions.columnconfigure(index % 4, weight=1)

        activity = ttk.Labelframe(
            self._body,
            text="Automation Logs",
            style="StudioCard.TLabelframe",
            padding=12,
        )
        activity.pack(fill="both", expand=True)
        activity_scroll = ScrolledFrame(activity, autohide=True, bootstyle="secondary", height=160)
        activity_scroll.pack(fill="both", expand=True)
        self._activity_container = activity_scroll.container

        footer = ttk.Frame(self._body, style="Studio.TFrame")
        footer.pack(fill="x", pady=(8, 0))
        ttk.Label(footer, text="Auto-refresh every 5 seconds", style="StudioMuted.TLabel").pack(side="right")

    def on_show(self) -> None:
        self._refresh_cancelled = False
        self.refresh()
        self._start_auto_refresh()

    def on_hide(self) -> None:
        self._refresh_cancelled = True
        self._refresh_generation += 1
        self._refresh_in_progress = False
        self._reset_busy_cursor()
        if self._refresh_job:
            self.after_cancel(self._refresh_job)
            self._refresh_job = None

    def _start_auto_refresh(self) -> None:
        if self._refresh_job:
            self.after_cancel(self._refresh_job)
        self._schedule_refresh()

    def _schedule_refresh(self) -> None:
        self._refresh_job = self.after(REFRESH_INTERVAL_MS, self._auto_refresh)

    def _auto_refresh(self) -> None:
        self._refresh_job = None
        if self.winfo_ismapped():
            self.refresh(quiet=True)
            self._schedule_refresh()

    def refresh(self, *, quiet: bool = False) -> None:
        if self._refresh_in_progress:
            return
        self._refresh_in_progress = True
        generation = self._refresh_generation
        if not quiet:
            self._show_busy_cursor(True)
            self.set_status("Refreshing automation manager…")

        def work() -> AutomationSnapshot:
            return build_automation_snapshot(self.config_manager)

        def complete(snapshot: AutomationSnapshot) -> None:
            if not quiet:
                self._show_busy_cursor(False)
            if generation != self._refresh_generation:
                return
            self._refresh_in_progress = False
            if self._refresh_cancelled:
                return
            self._snapshot = snapshot
            self._apply_snapshot(snapshot)
            if not quiet:
                self.set_status("Automation manager refreshed")

        def failed(error: Exception) -> None:
            if not quiet:
                self._show_busy_cursor(False)
            if generation != self._refresh_generation:
                return
            self._refresh_in_progress = False
            if not quiet:
                self._show_error_dialog("Automation Refresh", str(error))
            elif not self._refresh_cancelled:
                self.set_status("Automation refresh failed")

        run_in_background(self, work, complete, on_error=failed)

    def _apply_snapshot(self, snapshot: AutomationSnapshot) -> None:
        self._summary_label.configure(text=snapshot.summary)
        self._summary_detail.configure(
            text=f"{snapshot.healthy_count} healthy · {snapshot.warning_count} warning(s) · {snapshot.stopped_count} stopped"
        )

        for child in self._system_health_frame.winfo_children():
            child.destroy()
        for index, item in enumerate(snapshot.system_health):
            ttk.Label(
                self._system_health_frame,
                text=item.name,
                style="StudioMuted.TLabel",
            ).grid(row=0, column=index, padx=8, pady=2, sticky="s")
            bootstyle = {
                HEALTH_OK: "success",
                HEALTH_WARN: "warning",
                HEALTH_ERROR: "danger",
            }.get(item.status, "secondary")
            ttk.Label(
                self._system_health_frame,
                text=item.status.upper(),
                bootstyle=bootstyle,
                width=8,
            ).grid(row=1, column=index, padx=8, pady=2)

        selected = self._selected_module_id
        self._suppress_tree_events = True
        try:
            self._tree.delete(*self._tree.get_children())
            for module in snapshot.modules:
                self._tree.insert(
                    "",
                    "end",
                    iid=module.module_id,
                    values=(
                        module.name,
                        "Yes" if module.enabled else "No",
                        "Running" if module.running else "Stopped",
                        module.status.upper(),
                    ),
                )
            if selected and self._tree.exists(selected):
                self._tree.selection_set(selected)
                self._tree.focus(selected)
                self._show_module_details(self._module_by_id(selected))
            elif snapshot.modules:
                first_id = snapshot.modules[0].module_id
                self._tree.selection_set(first_id)
                self._show_module_details(snapshot.modules[0])
        finally:
            self._suppress_tree_events = False

        for child in self._activity_container.winfo_children():
            child.destroy()
        for line in snapshot.activity_log:
            ttk.Label(
                self._activity_container,
                text=line,
                style="StudioMuted.TLabel",
                wraplength=900,
                justify="left",
            ).pack(anchor="w", pady=1)

    def _module_by_id(self, module_id: str) -> AutomationModuleStatus | None:
        if not self._snapshot:
            return None
        for module in self._snapshot.modules:
            if module.module_id == module_id:
                return module
        return None

    def _on_module_select(self, _event=None) -> None:
        if self._suppress_tree_events:
            return
        selection = self._tree.selection()
        if not selection:
            return
        self._selected_module_id = selection[0]
        module = self._module_by_id(selection[0])
        if module:
            self._show_module_details(module)

    def _show_module_details(self, module: AutomationModuleStatus) -> None:
        self._detail_labels["enabled"].configure(text="Enabled" if module.enabled else "Disabled")
        self._detail_labels["running"].configure(text="Running" if module.running else "Stopped")
        self._detail_labels["last_run"].configure(text=module.last_run)
        self._detail_labels["next_run"].configure(text=module.next_run)
        self._detail_labels["schedule_source"].configure(text=module.schedule_source)
        self._detail_labels["configuration_file"].configure(text=module.configuration_file)
        self._detail_labels["log_file"].configure(text=module.log_file)
        self._detail_labels["status"].configure(text=module.status.upper())
        self._detail_labels["version"].configure(text=module.version)
        self._detail_labels["detail"].configure(text=module.detail)

    def _selected_module(self) -> AutomationModuleStatus | None:
        if not self._selected_module_id:
            return None
        return self._module_by_id(self._selected_module_id)

    def _settings(self) -> dict:
        return self.config_manager.load("settings", {})

    def _integration(self) -> dict:
        return integration_bundle(self._settings())

    def _run_operation(self, title: str, message: str, callback) -> None:
        if not confirm_action(title, message, self._settings()):
            return
        self._show_busy_cursor(True)
        self.set_status(f"{title}…")

        def work():
            return callback()

        def complete(result: tuple[bool, str]) -> None:
            self._show_busy_cursor(False)
            ok, result_message = result
            if ok:
                Messagebox.show_info(result_message, title)
            else:
                Messagebox.show_warning(result_message, title)
            self.set_status(result_message)
            self.refresh(quiet=True)

        def failed(error: Exception) -> None:
            self._show_busy_cursor(False)
            self._show_error_dialog(title, str(error))

        run_in_background(self, work, complete, on_error=failed)

    def _op_start_requests(self) -> None:
        self._run_operation(
            "Start Request Watcher",
            "Start the Request Watcher using the configured launcher script?",
            lambda: start_request_watcher(self._integration()),
        )

    def _op_restart_requests(self) -> None:
        self._run_operation(
            "Restart Request Watcher",
            "Restart the Request Watcher using the configured launcher script?",
            lambda: restart_request_watcher(self._integration()),
        )

    def _op_start_livedj(self) -> None:
        self._run_operation(
            "Start LiveDJ Watcher",
            "Start the LiveDJ Watcher using the configured launcher script?",
            lambda: start_livedj_watcher(self._integration()),
        )

    def _op_restart_livedj(self) -> None:
        self._run_operation(
            "Restart LiveDJ Watcher",
            "Restart the LiveDJ Watcher using the configured launcher script?",
            lambda: restart_livedj_watcher(self._integration()),
        )

    def _op_run_news(self) -> None:
        self._run_operation(
            "Run News Now",
            "Trigger an immediate news run using the configured launcher script?",
            lambda: run_news_now(self._integration()),
        )

    def _op_refresh_status(self) -> None:
        if not confirm_action(
            "Refresh All Statuses",
            "Refresh live system status for Dashboard and Automation monitoring?",
            self._settings(),
        ):
            return

        def work():
            return refresh_all_statuses(self._settings())

        def complete(result: tuple[bool, str]) -> None:
            self._show_busy_cursor(False)
            ok, message = result
            if ok:
                Messagebox.show_info(message, "Refresh All Statuses")
            else:
                Messagebox.show_warning(message, "Refresh All Statuses")
            self.set_status(message)
            self.refresh(quiet=True)

        def failed(error: Exception) -> None:
            self._show_busy_cursor(False)
            self._show_error_dialog("Refresh All Statuses", str(error))

        self._show_busy_cursor(True)
        self.set_status("Refreshing all statuses…")
        run_in_background(self, work, complete, on_error=failed)

    def _action_start(self) -> None:
        module = self._selected_module()
        if not module:
            Messagebox.show_info("Select an automation module first.", "Automation")
            return
        if module.module_id == "requests":
            self._op_start_requests()
        elif module.module_id == "livedj":
            self._op_start_livedj()
        else:
            append_automation_log(f"Start {module.name} requested — no launcher configured")
            Messagebox.show_info(f"No start launcher configured for {module.name}.", "Start")

    def _action_stop(self) -> None:
        module = self._selected_module()
        if not module:
            Messagebox.show_info("Select an automation module first.", "Automation")
            return
        if not confirm_action("Stop", f"Stop {module.name}?\nStudio does not stop engines directly.", self._settings()):
            return
        append_automation_log(f"Stop {module.name} requested — use engine launcher")
        Messagebox.show_info(
            f"Studio does not stop {module.name} directly.\nUse the engine's own stop script or task manager.",
            "Stop",
        )

    def _action_restart(self) -> None:
        module = self._selected_module()
        if not module:
            Messagebox.show_info("Select an automation module first.", "Automation")
            return
        if module.module_id == "requests":
            self._op_restart_requests()
        elif module.module_id == "livedj":
            self._op_restart_livedj()
        else:
            append_automation_log(f"Restart {module.name} requested — no launcher configured")
            Messagebox.show_info(f"No restart launcher configured for {module.name}.", "Restart")

    def _action_test_run(self) -> None:
        module = self._selected_module()
        if not module:
            Messagebox.show_info("Select an automation module first.", "Automation")
            return
        if module.module_id == "news":
            self._op_run_news()
        else:
            append_automation_log(f"Test run requested for {module.name}")
            Messagebox.show_info(f"Test run is not configured for {module.name}.", "Test Run")

    def _open_path(self, path: Path) -> None:
        try:
            if path.exists():
                if sys.platform.startswith("win"):
                    os.startfile(path)  # noqa: S606
                elif sys.platform == "darwin":
                    subprocess.run(["open", str(path)], check=False)
                else:
                    subprocess.run(["xdg-open", str(path)], check=False)
            else:
                parent = path.parent
                if parent.exists():
                    if sys.platform.startswith("win"):
                        os.startfile(parent)  # noqa: S606
                    Messagebox.show_warning(f"File not found:\n{path}", "Open Path")
                else:
                    Messagebox.show_warning(f"Path not found:\n{path}", "Open Path")
        except OSError as exc:
            Messagebox.show_error(f"Unable to open path:\n{exc}", "Open Path")

    def _action_open_config(self) -> None:
        module = self._selected_module()
        if not module:
            Messagebox.show_info("Select an automation module first.", "Automation")
            return
        if module.config_paths:
            self._open_path(Path(module.config_paths[0]))
        append_automation_log(f"Opened configuration for {module.name}")

    def _action_open_log(self) -> None:
        module = self._selected_module()
        if not module:
            Messagebox.show_info("Select an automation module first.", "Automation")
            return
        self._open_path(Path(module.log_file))
        append_automation_log(f"Opened log for {module.name}")

    def _action_health_check(self) -> None:
        module = self._selected_module()
        if not module:
            Messagebox.show_info("Select an automation module first.", "Automation")
            return
        lines = [
            f"Health Check — {module.name}",
            "",
            f"Enabled: {'Yes' if module.enabled else 'No'}",
            f"Running: {'Yes' if module.running else 'No'}",
            f"Status: {module.status.upper()}",
            f"Version: {module.version}",
            f"Last Run: {module.last_run}",
            f"Next Run: {module.next_run}",
            "",
            module.detail,
            "",
            "Studio controls launchers and configuration publish only — engines are not rewritten.",
        ]
        append_automation_log(f"Health check run for {module.name}: {module.status}")
        if module.status == HEALTH_ERROR:
            Messagebox.show_error("\n".join(lines), "Health Check")
        elif module.status == HEALTH_WARN:
            Messagebox.show_warning("\n".join(lines), "Health Check")
        else:
            Messagebox.show_info("\n".join(lines), "Health Check")

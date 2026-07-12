"""Operations, Backup & Deployment Manager."""

from __future__ import annotations

import tkinter as tk
from copy import deepcopy
from datetime import datetime
from pathlib import Path

import ttkbootstrap as ttk
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.scrolled import ScrolledText

from app.core.background_tasks import run_in_background
from app.core.health_constants import HEALTH_ERROR, HEALTH_OK, HEALTH_WARN
from app.core.operations import (
    refresh_all_statuses,
    restart_livedj_watcher,
    restart_request_watcher,
    run_news_now,
    start_livedj_watcher,
    start_request_watcher,
)
from app.core.operations_manager_model import (
    BACKUP_TYPES,
    MIGRATION_STATUSES,
    OPERATION_MODULES,
    StatusCard,
    append_log,
    build_production_map,
    build_system_status_cards,
    collect_recent_logs,
    copy_migration_module,
    create_deployment_package,
    get_module_operation_info,
    list_backup_history,
    normalize_bundle,
    rollback_deployment,
    run_backup,
    safety_summary,
    validate_deployment,
    verify_migration_copy,
)
from app.core.operations_manager_storage import load_operations_bundle, save_operations_bundle
from app.core.platform_manager import open_folder
from app.core.publish_manager import integration_bundle
from app.pages.base_page import BasePage
from app.ui.confirm_dialog import confirm_action
from app.ui.theme import StudioTheme

LIGHT_COLORS = {
    HEALTH_OK: StudioTheme.SUCCESS,
    HEALTH_WARN: StudioTheme.WARNING,
    HEALTH_ERROR: StudioTheme.DANGER,
}

STATUS_LABELS = {
    "not_started": "Not Started",
    "copied": "Copied",
    "testing": "Testing",
    "ready": "Ready",
    "production": "Production",
    "archived": "Archived",
}


class OperationsManagerPage(BasePage):
    page_id = "operations_manager"
    page_title = "Operations Manager"
    page_subtitle = "System status, backups, deployment, migration, and safety controls"
    page_help = (
        "Manage station operations from Studio without modifying the live station yet. "
        "All production actions require confirmation. Backups are stored under the platform Backups folder."
    )

    def build(self) -> None:
        self._bundle = normalize_bundle({})
        self._busy = False
        self._refresh_in_progress = False
        self._selected_module = OPERATION_MODULES[0]
        self._selected_migration_id: str | None = None
        self._selected_backup_label = BACKUP_TYPES[0][1]
        self._status_widgets: dict[str, tuple[tk.Canvas, ttk.Label, ttk.Label]] = {}

        toolbar = ttk.Frame(self._body, style="Studio.TFrame")
        toolbar.pack(fill="x", pady=(0, 12))
        ttk.Button(
            toolbar,
            text="Refresh Status",
            style="StudioAction.TButton",
            bootstyle="info",
            command=self._refresh_status,
        ).pack(side="left")
        ttk.Button(
            toolbar,
            text="Save Operations Data",
            style="StudioAction.TButton",
            bootstyle="primary",
            command=self._save,
        ).pack(side="right")

        self._notebook = ttk.Notebook(self._body, bootstyle="primary")
        self._notebook.pack(fill="both", expand=True)
        self._build_status_tab()
        self._build_controls_tab()
        self._build_backup_tab()
        self._build_deployment_tab()
        self._build_migration_tab()
        self._build_production_map_tab()
        self._build_logs_tab()
        self._build_safety_tab()

    def on_show(self) -> None:
        self._load()
        self._refresh_status()

    def _settings(self) -> dict:
        return self.config_manager.load("settings", {})

    def _integration(self) -> dict:
        return integration_bundle(self._settings())

    def _load(self) -> None:
        self._bundle = normalize_bundle(load_operations_bundle(self.config_manager), self.config_manager)
        self._refresh_all_views()
        self.set_status("Operations data loaded")

    def _save(self) -> None:
        if self._busy:
            return
        self._busy = True
        payload = deepcopy(self._bundle)

        def work() -> None:
            save_operations_bundle(payload, self.config_manager)

        def complete(_: None) -> None:
            self._busy = False
            self.set_status("Operations data saved")

        def failed(error: Exception) -> None:
            self._busy = False
            self._show_error_dialog("Save Operations Data", str(error))

        run_in_background(self, work, lambda _: complete(None), on_error=failed)

    def _refresh_all_views(self) -> None:
        self._refresh_backup_history()
        self._refresh_deployment()
        self._refresh_migration()
        self._refresh_production_map()
        self._refresh_logs()
        self._refresh_safety()

    @staticmethod
    def _set_scroll_text(widget: ScrolledText, content: str) -> None:
        widget.text.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("end", content)
        widget.text.configure(state="disabled")

    def _confirmed(self, title: str, message: str) -> bool:
        return confirm_action(title, message, self._settings())

    def _build_status_tab(self) -> None:
        tab = ttk.Frame(self._notebook, style="Studio.TFrame", padding=12)
        self._notebook.add(tab, text="System Status")
        grid = ttk.Frame(tab, style="Studio.TFrame")
        grid.pack(fill="x")
        self._status_grid = grid
        self._status_messages = ScrolledText(
            tab, height=10, autohide=True, bootstyle="secondary", state="disabled", wrap="word"
        )
        self._status_messages.pack(fill="both", expand=True, pady=(12, 0))

    def _refresh_status(self) -> None:
        if self._refresh_in_progress:
            return
        self._refresh_in_progress = True

        def work() -> list[StatusCard]:
            return build_system_status_cards(self.config_manager)

        def complete(cards: list[StatusCard]) -> None:
            self._refresh_in_progress = False
            self._apply_status_cards(cards)
            self.set_status("System status refreshed")

        def failed(error: Exception) -> None:
            self._refresh_in_progress = False
            self._show_error_dialog("Refresh Status", str(error))

        run_in_background(self, work, complete, on_error=failed)

    def _apply_status_cards(self, cards: list[StatusCard]) -> None:
        for child in self._status_grid.winfo_children():
            child.destroy()
        self._status_widgets.clear()
        for index, card in enumerate(cards):
            cell = ttk.Frame(self._status_grid, style="StudioPanel.TFrame")
            cell.grid(row=index // 5, column=index % 5, sticky="nsew", padx=8, pady=8)
            canvas = tk.Canvas(cell, width=48, height=48, bg=StudioTheme.BG_PANEL, highlightthickness=0)
            canvas.pack()
            color = LIGHT_COLORS.get(card.status, StudioTheme.TEXT_MUTED)
            canvas.create_oval(6, 6, 42, 42, fill=color, outline=StudioTheme.BORDER, width=2)
            ttk.Label(cell, text=card.name, style="StudioCard.TLabel", anchor="center").pack(pady=(4, 0))
            badge = ttk.Label(cell, text=card.status.upper(), style="StudioMuted.TLabel", anchor="center")
            badge.pack()
            detail = ttk.Label(cell, text=card.detail[:40], style="StudioMuted.TLabel", anchor="center", wraplength=100)
            detail.pack()
            self._status_widgets[card.name] = (canvas, badge, detail)
            self._status_grid.columnconfigure(index % 5, weight=1)

        lines = [f"{card.name}: {card.plain_message}" for card in cards if card.status != HEALTH_OK]
        if not lines:
            lines = ["All monitored systems look healthy."]
        self._set_scroll_text(self._status_messages, "\n".join(lines))

    def _build_controls_tab(self) -> None:
        tab = ttk.Frame(self._notebook, style="Studio.TFrame", padding=12)
        self._notebook.add(tab, text="Operations Controls")
        row = ttk.Frame(tab, style="Studio.TFrame")
        row.pack(fill="x", pady=(0, 8))
        ttk.Label(row, text="Module", style="StudioMuted.TLabel").pack(side="left")
        self._control_module = tk.StringVar(value=OPERATION_MODULES[0])
        ttk.Combobox(
            row,
            textvariable=self._control_module,
            values=list(OPERATION_MODULES),
            state="readonly",
            width=24,
        ).pack(side="left", padx=8)

        buttons = ttk.Frame(tab, style="Studio.TFrame")
        buttons.pack(fill="x", pady=(0, 12))
        for index, (label, command) in enumerate(
            (
                ("Start", self._op_start),
                ("Stop", self._op_stop),
                ("Restart", self._op_restart),
                ("Test", self._op_test),
                ("Open Folder", self._op_open_folder),
                ("Open Log", self._op_open_log),
            )
        ):
            ttk.Button(buttons, text=label, bootstyle="primary", command=command).grid(
                row=index // 3, column=index % 3, sticky="ew", padx=6, pady=4
            )
            buttons.columnconfigure(index % 3, weight=1)

        self._control_result = ScrolledText(
            tab, height=12, autohide=True, bootstyle="secondary", state="disabled", wrap="word"
        )
        self._control_result.pack(fill="both", expand=True)

    def _show_control_result(self, message: str) -> None:
        self._set_scroll_text(self._control_result, message)
        append_log(self._bundle, "operations", message)

    def _op_start(self) -> None:
        module = self._control_module.get()
        if not self._confirmed("Start", f"Start {module}?"):
            return
        integration = self._integration()
        if module == "Request Watcher":
            ok, msg = start_request_watcher(integration)
        elif module == "LiveDJ":
            ok, msg = start_livedj_watcher(integration)
        else:
            ok, msg = False, f"Start is not automated for {module} in development mode."
        self._show_control_result(msg)
        self.set_status(msg)

    def _op_stop(self) -> None:
        module = self._control_module.get()
        if not self._confirmed("Stop", f"Stop {module}?"):
            return
        msg = (
            f"Stop requested for {module}. "
            "Automatic stop is disabled in Version 1 to protect the live station."
        )
        self._show_control_result(msg)
        self.set_status(msg)

    def _op_restart(self) -> None:
        module = self._control_module.get()
        if not self._confirmed("Restart", f"Restart {module}?"):
            return
        integration = self._integration()
        if module == "Request Watcher":
            ok, msg = restart_request_watcher(integration)
        elif module == "LiveDJ":
            ok, msg = restart_livedj_watcher(integration)
        elif module == "News":
            ok, msg = run_news_now(integration)
        else:
            ok, msg = False, f"Restart is not automated for {module} in development mode."
        self._show_control_result(msg)
        self.set_status(msg)

    def _op_test(self) -> None:
        module = self._control_module.get()
        if not self._confirmed("Test", f"Run test for {module}?"):
            return
        if module in {"Voicebox", "RadioDJ", "Website Scheduler"}:
            ok, msg = refresh_all_statuses(self._settings())
        else:
            ok, msg = True, f"Test queued for {module} (development mode)."
        self._show_control_result(msg)
        self.set_status(msg)

    def _op_open_folder(self) -> None:
        module = self._control_module.get()
        info = get_module_operation_info(module, self.config_manager)
        folder = info.get("folder", "")
        if not folder:
            Messagebox.show_warning("No folder configured for this module.", "Open Folder")
            return
        try:
            open_folder(folder)
            self.set_status(f"Opened folder for {module}")
        except OSError as exc:
            self._show_error_dialog("Open Folder", str(exc))

    def _op_open_log(self) -> None:
        module = self._control_module.get()
        info = get_module_operation_info(module, self.config_manager)
        log_path = info.get("log", "")
        if not log_path or not Path(log_path).exists():
            Messagebox.show_warning("No log file found for this module.", "Open Log")
            return
        try:
            open_folder(str(Path(log_path).parent))
            self.set_status(f"Opened log folder for {module}")
        except OSError as exc:
            self._show_error_dialog("Open Log", str(exc))

    def _build_backup_tab(self) -> None:
        tab = ttk.Frame(self._notebook, style="Studio.TFrame", padding=12)
        self._notebook.add(tab, text="Backup Manager")
        toolbar = ttk.Frame(tab, style="Studio.TFrame")
        toolbar.pack(fill="x", pady=(0, 8))
        self._backup_type = tk.StringVar(value=BACKUP_TYPES[0][1])
        ttk.Combobox(
            toolbar,
            textvariable=self._backup_type,
            values=[label for _key, label in BACKUP_TYPES],
            state="readonly",
            width=28,
        ).pack(side="left")
        self._backup_labels = {label: key for key, label in BACKUP_TYPES}
        ttk.Button(toolbar, text="Create Backup", bootstyle="success", command=self._create_backup).pack(
            side="left", padx=8
        )
        ttk.Button(toolbar, text="Restore Last Backup", bootstyle="warning", command=self._restore_backup).pack(
            side="left"
        )
        self._backup_history = ScrolledText(
            tab, height=18, autohide=True, bootstyle="secondary", state="disabled", wrap="word"
        )
        self._backup_history.pack(fill="both", expand=True)

    def _refresh_backup_history(self) -> None:
        lines = list_backup_history(self.config_manager)
        self._set_scroll_text(self._backup_history, "\n".join(lines))

    def _create_backup(self) -> None:
        backup_type = self._backup_labels.get(self._backup_type.get(), BACKUP_TYPES[0][0])
        if not self._confirmed("Create Backup", f"Create backup for {self._backup_type.get()}?"):
            return

        def work() -> tuple[bool, str]:
            return run_backup(backup_type, self.config_manager, self._bundle)[:2]

        def complete(result: tuple[bool, str]) -> None:
            ok, msg = result
            if ok:
                Messagebox.show_info(msg, "Backup Created")
            else:
                Messagebox.show_warning(msg, "Backup Failed")
            self._refresh_backup_history()
            self._refresh_logs()
            self.set_status(msg)

        run_in_background(self, work, complete, on_error=lambda e: self._show_error_dialog("Create Backup", str(e)))

    def _restore_backup(self) -> None:
        backup_type = self._backup_labels.get(self._backup_type.get(), BACKUP_TYPES[0][0])
        if not self._confirmed(
            "Restore Backup",
            f"Restore the most recent {self._backup_type.get()} backup?\n"
            "This updates Studio development files only.",
        ):
            return
        from app.core.operations_manager_model import backup_sources_for_type, restore_backup_folder
        from app.core.platform_manager import platform_backups_dir

        backup_root = platform_backups_dir(self.config_manager) / backup_type
        if not backup_root.exists():
            Messagebox.show_warning("No backups found for this type.", "Restore Backup")
            return
        latest = sorted((p for p in backup_root.iterdir() if p.is_dir()), reverse=True)[0]
        destinations = backup_sources_for_type(backup_type, self.config_manager)
        ok, msg = restore_backup_folder(latest, destinations)
        if ok:
            append_log(self._bundle, "backups", f"Restored {backup_type} from {latest.name}")
            Messagebox.show_info(msg, "Restore Backup")
        else:
            Messagebox.show_warning(msg, "Restore Backup")
        self._refresh_backup_history()
        self._refresh_logs()
        self.set_status(msg)

    def _build_deployment_tab(self) -> None:
        tab = ttk.Frame(self._notebook, style="Studio.TFrame", padding=12)
        self._notebook.add(tab, text="Deployment Manager")
        form = ttk.Labelframe(tab, text="Version Information", style="StudioCard.TLabelframe", padding=16)
        form.pack(fill="x", pady=(0, 12))
        self._deploy_fields: dict[str, tk.Variable] = {}
        for key, label in (
            ("development_version", "Development Version"),
            ("production_version", "Production Version"),
            ("build_date", "Build Date"),
        ):
            row = ttk.Frame(form, style="StudioPanel.TFrame")
            row.pack(fill="x", pady=4)
            ttk.Label(row, text=label, style="StudioMuted.TLabel", width=20).pack(side="left")
            var = tk.StringVar()
            ttk.Entry(row, textvariable=var).pack(side="left", fill="x", expand=True)
            self._deploy_fields[key] = var
        row = ttk.Frame(form, style="StudioPanel.TFrame")
        row.pack(fill="x", pady=4)
        ttk.Label(row, text="Release Notes", style="StudioMuted.TLabel", width=20).pack(side="left", anchor="n")
        self._release_notes = ScrolledText(row, height=4, autohide=True, bootstyle="secondary", wrap="word")
        self._release_notes.pack(side="left", fill="x", expand=True)

        buttons = ttk.Frame(tab, style="Studio.TFrame")
        buttons.pack(fill="x", pady=(0, 12))
        ttk.Button(buttons, text="Validate Deployment", bootstyle="info", command=self._validate_deploy).pack(
            side="left"
        )
        ttk.Button(buttons, text="Create Deployment Package", bootstyle="success", command=self._deploy).pack(
            side="left", padx=8
        )
        ttk.Button(buttons, text="Roll Back", bootstyle="warning", command=self._rollback).pack(side="left")
        self._deploy_status = ScrolledText(
            tab, height=10, autohide=True, bootstyle="secondary", state="disabled", wrap="word"
        )
        self._deploy_status.pack(fill="both", expand=True)

    def _refresh_deployment(self) -> None:
        deployment = self._bundle["deployment"]
        for key, var in self._deploy_fields.items():
            var.set(str(deployment.get(key, "")))
        self._release_notes.text.configure(state="normal")
        self._release_notes.delete("1.0", "end")
        self._release_notes.insert("end", deployment.get("release_notes", ""))
        self._release_notes.text.configure(state="normal")
        status_lines = [
            f"Last deployed: {deployment.get('last_deployed') or '—'}",
            f"Last rollback: {deployment.get('last_rollback') or '—'}",
            "",
            "Deployment packages are stored under Backups/Deployments.",
            "Live station is not modified until a future production cutover.",
        ]
        self._set_scroll_text(self._deploy_status, "\n".join(status_lines))

    def _collect_deployment(self) -> None:
        for key, var in self._deploy_fields.items():
            self._bundle["deployment"][key] = var.get().strip()
        self._bundle["deployment"]["release_notes"] = self._release_notes.get("1.0", "end").strip()

    def _validate_deploy(self) -> None:
        self._collect_deployment()
        warnings = validate_deployment(self._bundle, self.config_manager)
        if warnings:
            self._set_scroll_text(self._deploy_status, "Validation issues:\n" + "\n".join(f"• {w}" for w in warnings))
        else:
            self._set_scroll_text(self._deploy_status, "Deployment validation passed.")
        self.set_status("Deployment validation complete")

    def _deploy(self) -> None:
        self._collect_deployment()
        warnings = validate_deployment(self._bundle, self.config_manager)
        if warnings:
            Messagebox.show_error("\n".join(warnings), "Cannot Deploy")
            return
        if not self._confirmed(
            "Deploy",
            "Create a deployment package with automatic backup?\n"
            "The live station will NOT be modified.",
        ):
            return

        def work() -> tuple[bool, str]:
            return create_deployment_package(self.config_manager, self._bundle)[:2]

        def complete(result: tuple[bool, str]) -> None:
            ok, msg = result
            if ok:
                Messagebox.show_info(msg, "Deployment Package")
            else:
                Messagebox.show_warning(msg, "Deployment Failed")
            self._refresh_deployment()
            self._refresh_logs()
            self.set_status(msg)

        run_in_background(self, work, complete, on_error=lambda e: self._show_error_dialog("Deploy", str(e)))

    def _rollback(self) -> None:
        if not self._confirmed("Roll Back", "Roll back Studio config to the previous deployment package?"):
            return

        def work() -> tuple[bool, str]:
            return rollback_deployment(self.config_manager, self._bundle)

        def complete(result: tuple[bool, str]) -> None:
            ok, msg = result
            if ok:
                Messagebox.show_info(msg, "Roll Back")
            else:
                Messagebox.show_warning(msg, "Roll Back")
            self._refresh_deployment()
            self._refresh_logs()
            self.set_status(msg)

        run_in_background(self, work, complete, on_error=lambda e: self._show_error_dialog("Roll Back", str(e)))

    def _build_migration_tab(self) -> None:
        tab = ttk.Frame(self._notebook, style="Studio.TFrame", padding=12)
        self._notebook.add(tab, text="Migration Manager")
        panes = ttk.Panedwindow(tab, orient="horizontal", bootstyle="secondary")
        panes.pack(fill="both", expand=True)
        list_panel = ttk.Labelframe(panes, text="Modules", style="StudioCard.TLabelframe", padding=8)
        panes.add(list_panel, weight=1)
        self._migration_tree = ttk.Treeview(
            list_panel,
            columns=("name", "status", "files"),
            show="headings",
            bootstyle="info",
            height=12,
        )
        for col, heading in (("name", "Module"), ("status", "Status"), ("files", "Files")):
            self._migration_tree.heading(col, text=heading)
        self._migration_tree.pack(fill="both", expand=True)
        self._migration_tree.bind("<<TreeviewSelect>>", self._on_migration_select)

        detail = ttk.Labelframe(panes, text="Migration Details", style="StudioCard.TLabelframe", padding=12)
        panes.add(detail, weight=2)
        self._migration_detail = ScrolledText(
            detail, height=14, autohide=True, bootstyle="secondary", state="disabled", wrap="word"
        )
        self._migration_detail.pack(fill="both", expand=True)
        buttons = ttk.Frame(detail, style="Studio.TFrame")
        buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(buttons, text="Copy Module", bootstyle="success", command=self._copy_module).pack(side="left")
        ttk.Button(buttons, text="Verify Copy", bootstyle="info", command=self._verify_module).pack(side="left", padx=8)
        ttk.Button(buttons, text="Mark Testing", bootstyle="secondary", command=lambda: self._set_migration_status("testing")).pack(
            side="left", padx=8
        )
        ttk.Button(buttons, text="Mark Ready", bootstyle="secondary", command=lambda: self._set_migration_status("ready")).pack(
            side="left"
        )

    def _refresh_migration(self) -> None:
        self._migration_tree.delete(*self._migration_tree.get_children())
        for module in self._bundle["migration"]["modules"]:
            self._migration_tree.insert(
                "",
                "end",
                iid=module["id"],
                values=(
                    module.get("name", ""),
                    STATUS_LABELS.get(module.get("status", ""), module.get("status", "")),
                    module.get("files_copied", 0),
                ),
            )

    def _on_migration_select(self, _event=None) -> None:
        selection = self._migration_tree.selection()
        if not selection:
            return
        self._selected_migration_id = selection[0]
        module = next(item for item in self._bundle["migration"]["modules"] if item["id"] == self._selected_migration_id)
        lines = [
            f"Module: {module.get('name', '')}",
            f"Status: {STATUS_LABELS.get(module.get('status', ''), module.get('status', ''))}",
            f"Source: {module.get('source_path', '')}",
            f"Destination: {module.get('destination_path', '')}",
            f"Files copied: {module.get('files_copied', 0)}",
            f"Verified: {'Yes' if module.get('verified') else 'No'}",
            f"Last action: {module.get('last_action', '')}",
            f"Notes: {module.get('notes', '')}",
        ]
        self._set_scroll_text(self._migration_detail, "\n".join(lines))

    def _copy_module(self) -> None:
        if not self._selected_migration_id:
            return
        module = next(item for item in self._bundle["migration"]["modules"] if item["id"] == self._selected_migration_id)
        if not self._confirmed("Copy Module", f"Copy {module.get('name', '')} without moving originals?"):
            return
        ok, msg = copy_migration_module(module, self.config_manager, self._bundle)
        if ok:
            Messagebox.show_info(msg, "Copy Module")
        else:
            Messagebox.show_warning(msg, "Copy Module")
        self._refresh_migration()
        self._on_migration_select()
        self._refresh_logs()
        self.set_status(msg)

    def _verify_module(self) -> None:
        if not self._selected_migration_id:
            return
        module = next(item for item in self._bundle["migration"]["modules"] if item["id"] == self._selected_migration_id)
        ok, label, detail = verify_migration_copy(module)
        Messagebox.show_info(f"{label}\n{detail}", "Verify Copy")
        self._on_migration_select()
        self.set_status(detail)

    def _set_migration_status(self, status: str) -> None:
        if not self._selected_migration_id:
            return
        for module in self._bundle["migration"]["modules"]:
            if module["id"] == self._selected_migration_id:
                module["status"] = status
                module["last_action"] = datetime.now().strftime("%Y-%m-%d %I:%M %p")
                break
        self._refresh_migration()
        self.set_status(f"Module marked {STATUS_LABELS.get(status, status)}")

    def _build_production_map_tab(self) -> None:
        tab = ttk.Frame(self._notebook, style="Studio.TFrame", padding=12)
        self._notebook.add(tab, text="Production Map")
        self._production_map_text = ScrolledText(
            tab, height=22, autohide=True, bootstyle="secondary", state="disabled", wrap="word"
        )
        self._production_map_text.pack(fill="both", expand=True)

    def _refresh_production_map(self) -> None:
        lines = build_production_map(self.config_manager)
        self._set_scroll_text(self._production_map_text, "\n".join(lines))

    def _build_logs_tab(self) -> None:
        tab = ttk.Frame(self._notebook, style="Studio.TFrame", padding=12)
        self._notebook.add(tab, text="Logs")
        self._logs_notebook = ttk.Notebook(tab, bootstyle="secondary")
        self._logs_notebook.pack(fill="both", expand=True)
        self._log_widgets: dict[str, ScrolledText] = {}
        for key, title in (
            ("operations", "Recent Operations"),
            ("backups", "Backup History"),
            ("deployments", "Deployment History"),
            ("migrations", "Migration History"),
            ("errors", "Errors"),
            ("warnings", "Warnings"),
        ):
            frame = ttk.Frame(self._logs_notebook, style="Studio.TFrame", padding=8)
            self._logs_notebook.add(frame, text=title)
            widget = ScrolledText(frame, height=12, autohide=True, bootstyle="secondary", state="disabled", wrap="word")
            widget.pack(fill="both", expand=True)
            self._log_widgets[key] = widget

    def _refresh_logs(self) -> None:
        logs = collect_recent_logs(self._bundle)
        for key, widget in self._log_widgets.items():
            lines = logs.get(key, [])
            self._set_scroll_text(widget, "\n".join(lines) if lines else "No entries yet.")

    def _build_safety_tab(self) -> None:
        tab = ttk.Frame(self._notebook, style="Studio.TFrame", padding=12)
        self._notebook.add(tab, text="Safety")
        self._safety_text = ScrolledText(
            tab, height=20, autohide=True, bootstyle="secondary", state="disabled", wrap="word"
        )
        self._safety_text.pack(fill="both", expand=True)

    def _refresh_safety(self) -> None:
        summary = safety_summary(self._settings())
        lines = [
            f"Current Mode: {summary['mode']}",
            "",
            "Safety Rules (Version 1):",
            f"• Production actions require confirmation: {'Yes' if summary['production_actions_require_confirmation'] else 'No'}",
            f"• Delete operations allowed: {'Yes' if summary['delete_operations_allowed'] else 'No'}",
            f"• Automatic cutover allowed: {'Yes' if summary['automatic_cutover_allowed'] else 'No'}",
            f"• RadioDJ database changes: {'Yes' if summary['radiodj_database_changes'] else 'No'}",
            f"• Task Scheduler job changes: {'Yes' if summary['task_scheduler_changes'] else 'No'}",
            "",
            "Development Mode keeps the live station protected.",
            "Deployment packages and backups are created before any Studio-side changes.",
        ]
        self._set_scroll_text(self._safety_text, "\n".join(lines))

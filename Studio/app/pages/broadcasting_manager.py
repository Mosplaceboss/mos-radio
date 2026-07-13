"""Broadcasting Software Manager — monitor and control on-air systems."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path

import ttkbootstrap as ttk
from ttkbootstrap.scrolled import ScrolledText

from app.core.background_tasks import run_in_background
from app.core.broadcasting_manager_model import (
    BroadcastingSnapshot,
    build_broadcasting_snapshot,
    resolve_radiodj_executable,
)
from app.core.health_constants import HEALTH_ERROR, HEALTH_OK, HEALTH_WARN
from app.core.hidden_process import popen_hidden
from app.core.operations import (
    refresh_all_statuses,
    restart_livedj_watcher,
    restart_request_watcher,
    run_news_now,
    start_livedj_watcher,
    start_request_watcher,
)
from app.core.operations_manager_model import get_module_operation_info
from app.core.platform_manager import open_folder
from app.core.publish_manager import integration_bundle
from app.pages.base_page import BasePage
from app.ui.confirm_dialog import confirm_action
from app.ui.theme import StudioTheme

REFRESH_INTERVAL_MS = 10_000

LIGHT_COLORS = {
    HEALTH_OK: StudioTheme.SUCCESS,
    HEALTH_WARN: StudioTheme.WARNING,
    HEALTH_ERROR: StudioTheme.DANGER,
}


class BroadcastingManagerPage(BasePage):
    page_id = "broadcasting_manager"
    page_title = "Broadcasting"
    page_subtitle = "Monitor RadioDJ, Voicebox, automation, audio output, and today's schedule"
    page_help = (
        "Read-only RadioDJ monitoring in this version. Automation actions require confirmation. "
        "Development Mode prevents production database changes and live publishing."
    )

    def build(self) -> None:
        self._refresh_job: str | None = None
        self._refresh_in_progress = False
        self._refresh_cancelled = False
        self._refresh_generation = 0
        self._metric_labels: dict[str, ttk.Label] = {}
        self._health_widgets: dict[str, tuple[tk.Canvas, ttk.Label]] = {}
        self._snapshot: BroadcastingSnapshot | None = None

        toolbar = ttk.Frame(self._body, style="Studio.TFrame")
        toolbar.pack(fill="x", pady=(0, 12))
        ttk.Button(
            toolbar,
            text="Refresh Now",
            style="StudioAction.TButton",
            bootstyle="info",
            command=lambda: self.refresh(quiet=False),
        ).pack(side="left")
        self._last_refresh_label = ttk.Label(toolbar, text="", style="StudioMuted.TLabel")
        self._last_refresh_label.pack(side="right")

        self._notebook = ttk.Notebook(self._body, bootstyle="primary")
        self._notebook.pack(fill="both", expand=True)
        self._build_dashboard_tab()
        self._build_radiodj_tab()
        self._build_audio_tab()
        self._build_automation_tab()
        self._build_schedule_tab()
        self._build_alerts_tab()

    def _settings(self) -> dict:
        return self.config_manager.load("settings", {})

    def _integration(self) -> dict:
        return integration_bundle(self._settings())

    def _confirmed(self, title: str, message: str) -> bool:
        return confirm_action(title, message, self._settings())

    @staticmethod
    def _set_text(widget: ScrolledText, content: str) -> None:
        widget.text.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("end", content)
        widget.text.configure(state="disabled")

    def _build_dashboard_tab(self) -> None:
        tab = ttk.Frame(self._notebook, style="Studio.TFrame", padding=12)
        self._notebook.add(tab, text="Broadcast Dashboard")

        status_row = ttk.Frame(tab, style="Studio.TFrame")
        status_row.pack(fill="x", pady=(0, 12))
        self._on_air_label = ttk.Label(status_row, text="—", style="StudioHero.TLabel")
        self._on_air_label.pack(side="left")

        metrics = ttk.Labelframe(tab, text="On Air Overview", style="StudioCard.TLabelframe", padding=16)
        metrics.pack(fill="x", pady=(0, 12))
        for index, (key, title) in enumerate(
            (
                ("current_song", "Current Song"),
                ("current_artist", "Current Artist"),
                ("current_host", "Current Host"),
                ("current_show", "Current Show"),
                ("current_format", "Current Format"),
                ("next_event", "Next Scheduled Event"),
            )
        ):
            cell = ttk.Frame(metrics, style="StudioPanel.TFrame")
            cell.grid(row=index // 3, column=index % 3, sticky="nsew", padx=8, pady=8)
            ttk.Label(cell, text=title, style="StudioMetricTitle.TLabel").pack(anchor="w")
            label = ttk.Label(cell, text="—", style="StudioMetric.TLabel", wraplength=260, justify="left")
            label.pack(anchor="w", pady=(4, 0))
            self._metric_labels[key] = label
            metrics.columnconfigure(index % 3, weight=1)

        lights = ttk.Labelframe(tab, text="Service Health", style="StudioCard.TLabelframe", padding=16)
        lights.pack(fill="x", pady=(0, 12))
        self._lights_row = ttk.Frame(lights, style="StudioPanel.TFrame")
        self._lights_row.pack(fill="x")

        lower = ttk.Frame(tab, style="Studio.TFrame")
        lower.pack(fill="both", expand=True)
        queue = ttk.Labelframe(lower, text="Queue Overview", style="StudioCard.TLabelframe", padding=12)
        queue.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self._queue_text = ScrolledText(queue, height=10, autohide=True, bootstyle="secondary", state="disabled", wrap="word")
        self._queue_text.pack(fill="both", expand=True)

        activity = ttk.Labelframe(lower, text="Recent Automation Activity", style="StudioCard.TLabelframe", padding=12)
        activity.pack(side="left", fill="both", expand=True, padx=(8, 0))
        self._activity_text = ScrolledText(
            activity, height=10, autohide=True, bootstyle="secondary", state="disabled", wrap="word"
        )
        self._activity_text.pack(fill="both", expand=True)

    def _build_radiodj_tab(self) -> None:
        tab = ttk.Frame(self._notebook, style="Studio.TFrame", padding=12)
        self._notebook.add(tab, text="RadioDJ")

        toolbar = ttk.Frame(tab, style="Studio.TFrame")
        toolbar.pack(fill="x", pady=(0, 12))
        ttk.Button(toolbar, text="Open RadioDJ", bootstyle="primary", command=self._open_radiodj).pack(side="left")
        ttk.Button(toolbar, text="Open RadioDJ Folder", bootstyle="secondary", command=self._open_radiodj_folder).pack(
            side="left", padx=8
        )
        ttk.Label(
            tab,
            text="Read-only in Version 1 — Studio does not edit the RadioDJ database.",
            style="StudioMuted.TLabel",
            wraplength=760,
            justify="left",
        ).pack(anchor="w", pady=(0, 8))

        self._radiodj_status = ttk.Label(tab, text="RadioDJ status: checking…", style="StudioCard.TLabel")
        self._radiodj_status.pack(anchor="w", pady=(0, 12))

        columns = ttk.Frame(tab, style="Studio.TFrame")
        columns.pack(fill="both", expand=True)
        queue = ttk.Labelframe(columns, text="Current Queue", style="StudioCard.TLabelframe", padding=12)
        queue.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self._radiodj_queue = ScrolledText(queue, height=12, autohide=True, bootstyle="secondary", state="disabled", wrap="word")
        self._radiodj_queue.pack(fill="both", expand=True)

        upcoming = ttk.Labelframe(columns, text="Upcoming Events", style="StudioCard.TLabelframe", padding=12)
        upcoming.pack(side="left", fill="both", expand=True, padx=(8, 0))
        self._radiodj_upcoming = ScrolledText(
            upcoming, height=12, autohide=True, bootstyle="secondary", state="disabled", wrap="word"
        )
        self._radiodj_upcoming.pack(fill="both", expand=True)

        history = ttk.Labelframe(tab, text="Recent History", style="StudioCard.TLabelframe", padding=12)
        history.pack(fill="both", expand=True, pady=(12, 0))
        self._radiodj_history = ScrolledText(
            history, height=8, autohide=True, bootstyle="secondary", state="disabled", wrap="word"
        )
        self._radiodj_history.pack(fill="both", expand=True)

    def _build_audio_tab(self) -> None:
        tab = ttk.Frame(self._notebook, style="Studio.TFrame", padding=12)
        self._notebook.add(tab, text="Audio Monitoring")
        ttk.Label(
            tab,
            text="Checks voice, news, and output folders for missing, blank, or stale audio files.",
            style="StudioMuted.TLabel",
            wraplength=760,
            justify="left",
        ).pack(anchor="w", pady=(0, 8))
        self._audio_text = ScrolledText(tab, height=24, autohide=True, bootstyle="secondary", state="disabled", wrap="word")
        self._audio_text.pack(fill="both", expand=True)

    def _build_automation_tab(self) -> None:
        tab = ttk.Frame(self._notebook, style="Studio.TFrame", padding=12)
        self._notebook.add(tab, text="Automation Controls")

        buttons = ttk.Frame(tab, style="Studio.TFrame")
        buttons.pack(fill="x", pady=(0, 12))
        specs = (
            ("Start LiveDJ Watcher", self._start_livedj),
            ("Restart LiveDJ Watcher", self._restart_livedj),
            ("Start Request Watcher", self._start_requests),
            ("Restart Request Watcher", self._restart_requests),
            ("Run News Now", self._run_news),
            ("Refresh All Statuses", self._refresh_statuses),
            ("Open LiveDJ Log", lambda: self._open_module_log("LiveDJ")),
            ("Open News Log", lambda: self._open_module_log("News")),
            ("Open Request Log", lambda: self._open_module_log("Request Watcher")),
            ("Open LiveDJ Folder", lambda: self._open_module_folder("LiveDJ")),
            ("Open News Folder", lambda: self._open_module_folder("News")),
            ("Open Website Folder", lambda: self._open_module_folder("Website Scheduler")),
        )
        for index, (label, command) in enumerate(specs):
            ttk.Button(buttons, text=label, bootstyle="primary", command=command).grid(
                row=index // 3, column=index % 3, sticky="ew", padx=6, pady=4
            )
            buttons.columnconfigure(index % 3, weight=1)

        self._automation_result = ScrolledText(
            tab, height=14, autohide=True, bootstyle="secondary", state="disabled", wrap="word"
        )
        self._automation_result.pack(fill="both", expand=True)

    def _build_schedule_tab(self) -> None:
        tab = ttk.Frame(self._notebook, style="Studio.TFrame", padding=12)
        self._notebook.add(tab, text="Broadcast Schedule")
        self._schedule_text = ScrolledText(tab, height=24, autohide=True, bootstyle="secondary", state="disabled", wrap="word")
        self._schedule_text.pack(fill="both", expand=True)

    def _build_alerts_tab(self) -> None:
        tab = ttk.Frame(self._notebook, style="Studio.TFrame", padding=12)
        self._notebook.add(tab, text="Alerts & Safety")
        self._alerts_text = ScrolledText(tab, height=14, autohide=True, bootstyle="secondary", state="disabled", wrap="word")
        self._alerts_text.pack(fill="both", expand=True, pady=(0, 12))
        self._safety_text = ScrolledText(tab, height=8, autohide=True, bootstyle="secondary", state="disabled", wrap="word")
        self._safety_text.pack(fill="both", expand=True)

    def on_show(self) -> None:
        self._refresh_cancelled = False
        self.refresh()
        self._schedule_refresh()

    def on_hide(self) -> None:
        self._refresh_cancelled = True
        self._refresh_generation += 1
        self._refresh_in_progress = False
        self._reset_busy_cursor()
        if self._refresh_job:
            self.after_cancel(self._refresh_job)
            self._refresh_job = None

    def _schedule_refresh(self) -> None:
        if self._refresh_job:
            self.after_cancel(self._refresh_job)
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
            self.set_status("Updating broadcast status…")

        def work() -> BroadcastingSnapshot:
            return build_broadcasting_snapshot(self.config_manager)

        def complete(snapshot: BroadcastingSnapshot) -> None:
            if not quiet:
                self._show_busy_cursor(False)
            if generation != self._refresh_generation:
                return
            self._refresh_in_progress = False
            if self._refresh_cancelled:
                return
            self._apply_snapshot(snapshot)
            if not quiet:
                self.set_status("Broadcast status updated")

        def failed(error: Exception) -> None:
            if not quiet:
                self._show_busy_cursor(False)
            if generation != self._refresh_generation:
                return
            self._refresh_in_progress = False
            if not quiet:
                self._show_error_dialog("Broadcast Update", str(error))

        run_in_background(self, work, complete, on_error=failed)

    def _apply_snapshot(self, snapshot: BroadcastingSnapshot) -> None:
        self._snapshot = snapshot
        self._on_air_label.configure(text=f"{snapshot.on_air_status} · {snapshot.last_refreshed}")
        mapping = {
            "current_song": snapshot.current_song,
            "current_artist": snapshot.current_artist,
            "current_host": snapshot.current_host,
            "current_show": snapshot.current_show,
            "current_format": snapshot.current_format,
            "next_event": snapshot.next_event,
        }
        for key, value in mapping.items():
            if key in self._metric_labels:
                self._metric_labels[key].configure(text=value)

        self._render_health_lights(snapshot.health_lights)
        self._set_text(self._queue_text, "\n".join(f"• {line}" for line in snapshot.queue_overview))
        self._set_text(
            self._activity_text,
            "\n".join(snapshot.recent_activity) if snapshot.recent_activity else "No recent automation activity.",
        )

        radiodj = snapshot.radiodj
        self._radiodj_status.configure(
            text=(
                f"RadioDJ: {radiodj.status.upper()} · {'Running' if radiodj.running else 'Not running'} · "
                f"{radiodj.detail}\nExecutable: {radiodj.executable}\nFolder: {radiodj.folder}"
            )
        )
        self._set_text(self._radiodj_queue, "\n".join(radiodj.queue_lines) or "No queue data available.")
        self._set_text(self._radiodj_upcoming, "\n".join(radiodj.upcoming_lines) or "No upcoming events scheduled.")
        self._set_text(self._radiodj_history, "\n".join(radiodj.history_lines) or "No history available.")

        audio_lines: list[str] = ["Audio Output Monitoring", ""]
        for folder in snapshot.audio_folders:
            audio_lines.append(f"{folder.label} — {folder.status.upper()} ({folder.file_count} files)")
            audio_lines.append(f"  Path: {folder.path}")
            if folder.issues:
                audio_lines.extend(f"  • {issue}" for issue in folder.issues)
            if folder.newest_files:
                audio_lines.append("  Newest files:")
                audio_lines.extend(f"    · {line}" for line in folder.newest_files)
            audio_lines.append("")
        self._set_text(self._audio_text, "\n".join(audio_lines))

        schedule_lines = ["Today's Programming", ""]
        if snapshot.today_schedule:
            for line in snapshot.today_schedule:
                schedule_lines.append(f"[{line.category.upper()}] {line.time} · {line.label}")
        else:
            schedule_lines.append("No programming scheduled for today.")
        schedule_lines.extend(
            [
                "",
                f"Website Scheduler: {snapshot.website_scheduler_status.upper()} — {snapshot.website_scheduler_detail}",
            ]
        )
        self._set_text(self._schedule_text, "\n".join(schedule_lines))

        self._set_text(self._alerts_text, "\n".join(f"• {alert}" for alert in snapshot.alerts))
        self._set_text(self._safety_text, "\n".join(snapshot.safety_lines))
        self._last_refresh_label.configure(text=f"Last refreshed: {snapshot.last_refreshed}")

    def _render_health_lights(self, lights) -> None:
        for child in self._lights_row.winfo_children():
            child.destroy()
        self._health_widgets.clear()
        for index, light in enumerate(lights):
            cell = ttk.Frame(self._lights_row, style="StudioPanel.TFrame")
            cell.pack(side="left", expand=True, fill="x", padx=6)
            canvas = tk.Canvas(cell, width=56, height=56, bg=StudioTheme.BG_PANEL, highlightthickness=0)
            canvas.pack()
            color = LIGHT_COLORS.get(light.status, StudioTheme.TEXT_MUTED)
            canvas.create_oval(8, 8, 48, 48, fill=color, outline=StudioTheme.BORDER, width=2)
            ttk.Label(cell, text=light.name, style="StudioCard.TLabel", anchor="center").pack(pady=(6, 0))
            detail = ttk.Label(
                cell, text=light.detail[:70], style="StudioMuted.TLabel", anchor="center", wraplength=110, justify="center"
            )
            detail.pack(pady=(2, 0))
            self._health_widgets[light.name] = (canvas, detail)
            self._lights_row.columnconfigure(index, weight=1)

    def _show_automation_result(self, message: str) -> None:
        self._set_text(self._automation_result, message)
        self.set_status(message)

    def _open_radiodj(self) -> None:
        if not self._confirmed("Open RadioDJ", "Open RadioDJ on this computer?"):
            return
        exe = resolve_radiodj_executable(self._settings(), self.config_manager)
        if not exe:
            self._show_error_dialog("Open RadioDJ", "RadioDJ executable was not found. Check Platform Manager paths.")
            return
        try:
            popen_hidden([str(exe)], cwd=exe.parent)
            self._show_automation_result(f"Launched RadioDJ from {exe}")
        except OSError as exc:
            self._show_error_dialog("Open RadioDJ", str(exc))

    def _open_radiodj_folder(self) -> None:
        folder = self._snapshot.radiodj.folder if self._snapshot else ""
        if not folder:
            info = get_module_operation_info("RadioDJ", self.config_manager)
            folder = info.get("folder", "")
        if not folder:
            self._show_error_dialog("Open Folder", "RadioDJ folder is not configured.")
            return
        try:
            open_folder(folder)
            self.set_status("Opened RadioDJ folder.")
        except OSError as exc:
            self._show_error_dialog("Open Folder", str(exc))

    def _start_livedj(self) -> None:
        if not self._confirmed("Start LiveDJ Watcher", "Start the LiveDJ watcher?"):
            return
        _ok, msg = start_livedj_watcher(self._integration())
        self._show_automation_result(msg)

    def _restart_livedj(self) -> None:
        if not self._confirmed("Restart LiveDJ Watcher", "Restart the LiveDJ watcher?"):
            return
        _ok, msg = restart_livedj_watcher(self._integration())
        self._show_automation_result(msg)

    def _start_requests(self) -> None:
        if not self._confirmed("Start Request Watcher", "Start the Request watcher?"):
            return
        _ok, msg = start_request_watcher(self._integration())
        self._show_automation_result(msg)

    def _restart_requests(self) -> None:
        if not self._confirmed("Restart Request Watcher", "Restart the Request watcher?"):
            return
        _ok, msg = restart_request_watcher(self._integration())
        self._show_automation_result(msg)

    def _run_news(self) -> None:
        if not self._confirmed("Run News Now", "Run the news automation now?"):
            return
        _ok, msg = run_news_now(self._integration())
        self._show_automation_result(msg)

    def _refresh_statuses(self) -> None:
        if not self._confirmed("Refresh Statuses", "Refresh all broadcast service statuses?"):
            return
        _ok, msg = refresh_all_statuses(self._settings())
        self._show_automation_result(msg)
        self.refresh(quiet=True)

    def _open_module_folder(self, module: str) -> None:
        if not self._confirmed("Open Folder", f"Open the {module} production folder?"):
            return
        info = get_module_operation_info(module, self.config_manager)
        folder = info.get("folder", "")
        if not folder:
            self._show_error_dialog("Open Folder", f"No folder configured for {module}.")
            return
        try:
            open_folder(folder)
            self.set_status(f"Opened folder for {module}.")
        except OSError as exc:
            self._show_error_dialog("Open Folder", str(exc))

    def _open_module_log(self, module: str) -> None:
        if not self._confirmed("Open Log", f"Open the log folder for {module}?"):
            return
        info = get_module_operation_info(module, self.config_manager)
        log_path = info.get("log", "")
        if not log_path or not Path(log_path).exists():
            self._show_error_dialog("Open Log", f"No log file found for {module}.")
            return
        try:
            open_folder(str(Path(log_path).parent))
            self.set_status(f"Opened log folder for {module}.")
        except OSError as exc:
            self._show_error_dialog("Open Log", str(exc))

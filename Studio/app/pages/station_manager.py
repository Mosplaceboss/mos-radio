"""Station Manager — main station control center."""

from __future__ import annotations

import tkinter as tk

import ttkbootstrap as ttk
from ttkbootstrap.scrolled import ScrolledText

from app.core.background_tasks import run_in_background
from app.core.health_constants import HEALTH_ERROR, HEALTH_OK, HEALTH_WARN
from app.core.platform_manager import open_folder, platform_path
from app.core.station_data import inventory_reports_dir
from app.core.station_manager_model import StationManagerSnapshot, build_station_manager_snapshot
from app.pages.base_page import BasePage
from app.ui.theme import StudioTheme

REFRESH_INTERVAL_MS = 15_000

LIGHT_COLORS = {
    HEALTH_OK: StudioTheme.SUCCESS,
    HEALTH_WARN: StudioTheme.WARNING,
    HEALTH_ERROR: StudioTheme.DANGER,
}

STATUS_LABELS = {
    HEALTH_OK: "Healthy",
    HEALTH_WARN: "Attention",
    HEALTH_ERROR: "Needs Help",
}

QUICK_ACTIONS = (
    ("programming", "Programming"),
    ("advertising", "Advertising"),
    ("news_content_manager", "News"),
    ("requests", "Requests"),
    ("_website", "Website"),
    ("personalities", "Personalities"),
    ("voice_library", "Voice Library"),
    ("platform_manager", "Platform Manager"),
    ("_inventory", "Inventory"),
    ("reports", "Reports"),
    ("settings", "Settings"),
    ("operations_manager", "Operations"),
)


class StationManagerPage(BasePage):
    page_id = "station_manager"
    page_title = "Station Manager"
    page_subtitle = "Main control center for Mo's Place Radio"
    page_help = (
        "Monitor on-air status, service health, alerts, and station operations. "
        "Health information refreshes automatically every 15 seconds."
    )

    def build(self) -> None:
        self._refresh_job: str | None = None
        self._refresh_in_progress = False
        self._refresh_cancelled = False
        self._refresh_generation = 0
        self._metric_labels: dict[str, ttk.Label] = {}
        self._service_widgets: dict[str, tuple[tk.Canvas, ttk.Label, ttk.Label]] = {}
        self._alerts_text: ScrolledText | None = None
        self._errors_text: ScrolledText | None = None
        self._success_text: ScrolledText | None = None
        self._last_refresh_label: ttk.Label | None = None

        toolbar = ttk.Frame(self._body, style="Studio.TFrame")
        toolbar.pack(fill="x", pady=(0, 12))
        ttk.Button(
            toolbar,
            text="Refresh Now",
            style="StudioAction.TButton",
            bootstyle="info",
            command=lambda: self.refresh(quiet=False),
        ).pack(side="left")
        ttk.Button(
            toolbar,
            text="Station Information",
            style="StudioAction.TButton",
            bootstyle="secondary",
            command=lambda: self._open_page("station_information"),
        ).pack(side="left", padx=8)
        self._last_refresh_label = ttk.Label(toolbar, text="", style="StudioMuted.TLabel")
        self._last_refresh_label.pack(side="right")

        metrics = ttk.Labelframe(self._body, text="On Air Overview", style="StudioCard.TLabelframe", padding=16)
        metrics.pack(fill="x", pady=(0, 12))
        metric_specs = (
            ("on_air_status", "On Air Status"),
            ("current_host", "Current Host"),
            ("current_format", "Current Format"),
            ("now_playing", "Now Playing"),
            ("next_event", "Next Scheduled Event"),
            ("last_inventory_scan", "Last Inventory Scan"),
        )
        for index, (key, title) in enumerate(metric_specs):
            cell = ttk.Frame(metrics, style="StudioPanel.TFrame")
            cell.grid(row=index // 3, column=index % 3, sticky="nsew", padx=8, pady=8)
            ttk.Label(cell, text=title, style="StudioMetricTitle.TLabel").pack(anchor="w")
            label = ttk.Label(cell, text="—", style="StudioMetric.TLabel", wraplength=260, justify="left")
            label.pack(anchor="w", pady=(4, 0))
            self._metric_labels[key] = label
            metrics.columnconfigure(index % 3, weight=1)

        services = ttk.Labelframe(self._body, text="Service Health", style="StudioCard.TLabelframe", padding=16)
        services.pack(fill="x", pady=(0, 12))
        service_row = ttk.Frame(services, style="StudioPanel.TFrame")
        service_row.pack(fill="x")
        for index, name in enumerate(
            ("RadioDJ", "Voicebox", "LiveDJ", "News", "Requests", "Website", "Internet")
        ):
            cell = ttk.Frame(service_row, style="StudioPanel.TFrame")
            cell.pack(side="left", expand=True, fill="x", padx=6)
            canvas = tk.Canvas(cell, width=56, height=56, bg=StudioTheme.BG_PANEL, highlightthickness=0)
            canvas.pack()
            canvas.create_oval(8, 8, 48, 48, fill=StudioTheme.TEXT_MUTED, outline=StudioTheme.BORDER, width=2)
            ttk.Label(cell, text=name, style="StudioCard.TLabel", anchor="center").pack(pady=(6, 0))
            badge = ttk.Label(cell, text="Checking…", style="StudioMuted.TLabel", anchor="center", wraplength=110)
            badge.pack(pady=(2, 0))
            detail = ttk.Label(cell, text="—", style="StudioMuted.TLabel", anchor="center", wraplength=110, justify="center")
            detail.pack(pady=(2, 0))
            self._service_widgets[name] = (canvas, badge, detail)
            service_row.columnconfigure(index, weight=1)

        middle = ttk.Frame(self._body, style="Studio.TFrame")
        middle.pack(fill="both", expand=True, pady=(0, 12))

        alerts = ttk.Labelframe(middle, text="Alerts", style="StudioCard.TLabelframe", padding=12)
        alerts.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self._alerts_text = ScrolledText(
            alerts,
            height=8,
            autohide=True,
            bootstyle="secondary",
            font=(StudioTheme.FONT_FAMILY, 10),
            state="disabled",
            wrap="word",
        )
        self._alerts_text.pack(fill="both", expand=True)

        health = ttk.Labelframe(middle, text="Health Monitor", style="StudioCard.TLabelframe", padding=12)
        health.pack(side="left", fill="both", expand=True, padx=(8, 0))
        ttk.Label(
            health,
            text="Green means healthy, yellow means attention needed, red means help is required.",
            style="StudioMuted.TLabel",
            wraplength=360,
            justify="left",
        ).pack(anchor="w", pady=(0, 8))

        logs = ttk.Frame(health, style="StudioPanel.TFrame")
        logs.pack(fill="both", expand=True)
        errors = ttk.Labelframe(logs, text="Recent Errors", style="StudioCard.TLabelframe", padding=8)
        errors.pack(side="left", fill="both", expand=True, padx=(0, 6))
        self._errors_text = ScrolledText(
            errors,
            height=6,
            autohide=True,
            bootstyle="danger",
            font=(StudioTheme.FONT_FAMILY, 9),
            state="disabled",
            wrap="word",
        )
        self._errors_text.pack(fill="both", expand=True)

        success = ttk.Labelframe(logs, text="Recent Successful Jobs", style="StudioCard.TLabelframe", padding=8)
        success.pack(side="left", fill="both", expand=True, padx=(6, 0))
        self._success_text = ScrolledText(
            success,
            height=6,
            autohide=True,
            bootstyle="success",
            font=(StudioTheme.FONT_FAMILY, 9),
            state="disabled",
            wrap="word",
        )
        self._success_text.pack(fill="both", expand=True)

        actions = ttk.Labelframe(self._body, text="Quick Actions", style="StudioCard.TLabelframe", padding=16)
        actions.pack(fill="x")
        for index, (page_id, label) in enumerate(QUICK_ACTIONS):
            ttk.Button(
                actions,
                text=label,
                style="StudioAction.TButton",
                bootstyle="primary",
                command=lambda pid=page_id: self._quick_action(pid),
            ).grid(row=index // 4, column=index % 4, sticky="ew", padx=8, pady=8)
            actions.columnconfigure(index % 4, weight=1)

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

    def _open_page(self, page_id: str) -> None:
        if self.on_navigate:
            self.on_navigate(page_id)

    def _quick_action(self, page_id: str) -> None:
        if page_id == "_inventory":
            try:
                open_folder(str(inventory_reports_dir(self.config_manager)))
                self.set_status("Opened inventory reports folder.")
            except OSError as exc:
                self._show_error_dialog("Inventory", str(exc))
            return
        if page_id == "_website":
            try:
                open_folder(str(platform_path("website", self.config_manager)))
                self.set_status("Opened website folder.")
            except OSError as exc:
                self._show_error_dialog("Website", str(exc))
            return
        self._open_page(page_id)

    def refresh(self, *, quiet: bool = False) -> None:
        if self._refresh_in_progress:
            return
        self._refresh_in_progress = True
        generation = self._refresh_generation
        if not quiet:
            self._show_busy_cursor(True)
            self.set_status("Refreshing station status…")

        def work() -> StationManagerSnapshot:
            return build_station_manager_snapshot(self.config_manager)

        def complete(snapshot: StationManagerSnapshot) -> None:
            if not quiet:
                self._show_busy_cursor(False)
            if generation != self._refresh_generation:
                return
            self._refresh_in_progress = False
            if self._refresh_cancelled:
                return
            self._apply_snapshot(snapshot)
            if not quiet:
                self.set_status("Station status updated")

        def failed(error: Exception) -> None:
            if not quiet:
                self._show_busy_cursor(False)
            if generation != self._refresh_generation:
                return
            self._refresh_in_progress = False
            if not quiet:
                self._show_error_dialog("Station Manager Refresh", str(error))

        run_in_background(self, work, complete, on_error=failed)

    def _apply_snapshot(self, snapshot: StationManagerSnapshot) -> None:
        mapping = {
            "on_air_status": snapshot.on_air_status,
            "current_host": snapshot.current_host,
            "current_format": snapshot.current_format,
            "now_playing": snapshot.now_playing,
            "next_event": snapshot.next_event,
            "last_inventory_scan": snapshot.last_inventory_scan,
        }
        for key, value in mapping.items():
            if key in self._metric_labels:
                self._metric_labels[key].configure(text=value)

        for light in snapshot.service_cards:
            widgets = self._service_widgets.get(light.name)
            if not widgets:
                continue
            canvas, badge, detail = widgets
            color = LIGHT_COLORS.get(light.status, StudioTheme.TEXT_MUTED)
            canvas.delete("all")
            canvas.create_oval(8, 8, 48, 48, fill=color, outline=StudioTheme.BORDER, width=2)
            badge.configure(text=STATUS_LABELS.get(light.status, "Unknown"))
            detail.configure(text=light.detail[:80])

        self._set_text(self._alerts_text, "\n".join(f"• {line}" for line in snapshot.alerts))
        self._set_text(self._errors_text, "\n".join(snapshot.recent_errors))
        self._set_text(self._success_text, "\n".join(snapshot.recent_successes))
        if self._last_refresh_label:
            self._last_refresh_label.configure(
                text=f"Last refreshed: {snapshot.last_refreshed} · {snapshot.clock_date}"
            )

    def _set_text(self, widget: ScrolledText | None, content: str) -> None:
        if not widget:
            return
        widget.text.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("end", content)
        widget.text.configure(state="disabled")

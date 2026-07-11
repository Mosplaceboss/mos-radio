"""Station operations dashboard."""

from __future__ import annotations

import tkinter as tk

import ttkbootstrap as ttk
from ttkbootstrap.scrolled import ScrolledFrame

from app.core.dashboard_model import (
    HEALTH_ERROR,
    HEALTH_OK,
    HEALTH_WARN,
    DashboardSnapshot,
    build_dashboard_snapshot,
)
from app.pages.base_page import BasePage
from app.ui.theme import StudioTheme

REFRESH_INTERVAL_MS = 5000


class DashboardPage(BasePage):
    page_id = "dashboard"
    page_title = "Dashboard"
    page_subtitle = "Live station overview — read-only monitoring and quick navigation"

    def build(self) -> None:
        self._refresh_job: str | None = None
        self._value_labels: dict[str, ttk.Label] = {}
        self._health_rows: dict[str, tuple[ttk.Label, ttk.Label]] = {}
        self._activity_list = None

        top = ttk.Frame(self._body, style="Studio.TFrame")
        top.pack(fill="x", pady=(0, 16))

        clock_panel = tk.Frame(top, bg=StudioTheme.BG_PANEL, padx=24, pady=16)
        clock_panel.pack(side="left", fill="y")
        self._clock_label = tk.Label(
            clock_panel,
            text="00:00:00",
            font=("Consolas", 42, "bold"),
            fg=StudioTheme.ACCENT,
            bg=StudioTheme.BG_PANEL,
        )
        self._clock_label.pack(anchor="w")
        self._clock_date_label = tk.Label(
            clock_panel,
            text="",
            font=("Segoe UI", 12),
            fg=StudioTheme.TEXT_MUTED,
            bg=StudioTheme.BG_PANEL,
        )
        self._clock_date_label.pack(anchor="w", pady=(4, 0))

        quick_panel = ttk.Labelframe(
            top,
            text="Quick Actions",
            style="StudioCard.TLabelframe",
            padding=16,
        )
        quick_panel.pack(side="left", fill="both", expand=True, padx=(16, 0))
        quick_specs = (
            ("requests", "Open Requests"),
            ("schedule", "Open Schedule"),
            ("personalities", "Open Personalities"),
            ("voice_library", "Open Voice Library"),
            ("settings", "Open Settings"),
        )
        for index, (page_id, label) in enumerate(quick_specs):
            ttk.Button(
                quick_panel,
                text=label,
                bootstyle="primary",
                command=lambda pid=page_id: self._open_page(pid),
            ).grid(row=index // 3, column=index % 3, sticky="ew", padx=8, pady=6)
            quick_panel.columnconfigure(index % 3, weight=1)

        body = ttk.Frame(self._body, style="Studio.TFrame")
        body.pack(fill="both", expand=True)

        left = ttk.Frame(body, style="Studio.TFrame")
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))

        on_air = ttk.Labelframe(left, text="On Air Now", style="StudioCard.TLabelframe", padding=16)
        on_air.pack(fill="x", pady=(0, 12))
        self._add_metric_row(on_air, "personality", "Current Personality")
        self._add_metric_row(on_air, "format", "Current Music Format")
        self._add_metric_row(on_air, "current_show", "Current Scheduled Event")
        self._add_metric_row(on_air, "next_show", "Next Scheduled Event")
        self._add_metric_row(on_air, "request_mode", "Current Request Mode")

        systems = ttk.Labelframe(left, text="System Status", style="StudioCard.TLabelframe", padding=16)
        systems.pack(fill="x", pady=(0, 12))
        self._add_metric_row(systems, "queue", "Queue Status")
        self._add_metric_row(systems, "news", "News Status")
        self._add_metric_row(systems, "livedj", "LiveDJ Status")
        self._add_metric_row(systems, "voicebox", "Voicebox Status")
        self._add_metric_row(systems, "last_livedj", "Last LiveDJ Run")
        self._add_metric_row(systems, "last_news", "Last News Run")
        self._add_metric_row(systems, "last_requests", "Last Requests Run")
        self._add_metric_row(systems, "last_studio", "Last Studio Activity")

        right = ttk.Frame(body, style="Studio.TFrame")
        right.pack(side="left", fill="both", expand=True, padx=(8, 0))

        health = ttk.Labelframe(right, text="Health Indicators", style="StudioCard.TLabelframe", padding=16)
        health.pack(fill="x", pady=(0, 12))
        self._health_frame = ttk.Frame(health, style="StudioPanel.TFrame")
        self._health_frame.pack(fill="x")

        activity = ttk.Labelframe(right, text="Recent Activity Log", style="StudioCard.TLabelframe", padding=16)
        activity.pack(fill="both", expand=True)
        scroll = ScrolledFrame(activity, autohide=True, bootstyle="secondary", height=220)
        scroll.pack(fill="both", expand=True)
        self._activity_container = scroll.container

        footer = ttk.Frame(self._body, style="Studio.TFrame")
        footer.pack(fill="x", pady=(12, 0))
        self._last_refresh_label = ttk.Label(footer, text="", style="StudioMuted.TLabel")
        self._last_refresh_label.pack(side="left")
        ttk.Label(
            footer,
            text="Auto-refresh every 5 seconds",
            style="StudioMuted.TLabel",
        ).pack(side="right")

    def _add_metric_row(self, parent: ttk.Labelframe, key: str, title: str) -> None:
        row = ttk.Frame(parent, style="StudioPanel.TFrame")
        row.pack(fill="x", pady=4)
        ttk.Label(row, text=title, style="StudioMuted.TLabel", width=24).pack(side="left")
        value = ttk.Label(row, text="—", style="StudioCard.TLabel", wraplength=420, justify="left")
        value.pack(side="left", fill="x", expand=True)
        self._value_labels[key] = value

    def on_show(self) -> None:
        self.refresh()
        self._start_auto_refresh()

    def on_hide(self) -> None:
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

    def _open_page(self, page_id: str) -> None:
        if self.on_navigate:
            self.on_navigate(page_id)

    def refresh(self, *, quiet: bool = False) -> None:
        snapshot = build_dashboard_snapshot(self.config_manager)
        self._apply_snapshot(snapshot)
        if not quiet:
            self.set_status("Dashboard refreshed")

    def _apply_snapshot(self, snapshot: DashboardSnapshot) -> None:
        self._clock_label.configure(text=snapshot.clock)
        self._clock_date_label.configure(text=snapshot.clock_date)

        current = snapshot.current_event
        next_event = snapshot.next_event
        current_text = (
            f"{current.show_name} · {current.day} {current.start_time}–{current.end_time}"
            if current.show_name != "—"
            else "No scheduled event airing"
        )
        next_text = (
            f"{next_event.show_name} · {next_event.day} {next_event.start_time}–{next_event.end_time}"
            if next_event.show_name != "—"
            else "No upcoming scheduled event"
        )

        self._value_labels["personality"].configure(text=snapshot.on_air_personality)
        self._value_labels["format"].configure(text=snapshot.music_format)
        self._value_labels["current_show"].configure(text=current_text)
        self._value_labels["next_show"].configure(text=next_text)
        self._value_labels["request_mode"].configure(text=snapshot.request_mode)
        self._value_labels["queue"].configure(text=snapshot.queue_status)
        self._value_labels["news"].configure(text=snapshot.news_status)
        self._value_labels["livedj"].configure(text=snapshot.livedj_status)
        self._value_labels["voicebox"].configure(text=snapshot.voicebox_status)
        self._value_labels["last_livedj"].configure(text=snapshot.last_livedj_run)
        self._value_labels["last_news"].configure(text=snapshot.last_news_run)
        self._value_labels["last_requests"].configure(text=snapshot.last_requests_run)
        self._value_labels["last_studio"].configure(text=snapshot.last_studio_run)

        for child in self._health_frame.winfo_children():
            child.destroy()
        self._health_rows.clear()
        for indicator in snapshot.health_indicators:
            self._add_health_row(indicator.name, indicator.status, indicator.detail)

        for child in self._activity_container.winfo_children():
            child.destroy()
        for line in snapshot.activity_log:
            ttk.Label(
                self._activity_container,
                text=line,
                style="StudioMuted.TLabel",
                wraplength=500,
                justify="left",
            ).pack(anchor="w", pady=2)

        self._last_refresh_label.configure(text=f"Last refreshed: {snapshot.clock}")

    def _add_health_row(self, name: str, status: str, detail: str) -> None:
        row = ttk.Frame(self._health_frame, style="StudioPanel.TFrame")
        row.pack(fill="x", pady=3)
        ttk.Label(row, text=name, style="StudioCard.TLabel", width=18).pack(side="left")
        bootstyle = {
            HEALTH_OK: "success",
            HEALTH_WARN: "warning",
            HEALTH_ERROR: "danger",
        }.get(status, "secondary")
        ttk.Label(row, text=status.upper(), bootstyle=bootstyle, width=10).pack(side="left", padx=8)
        ttk.Label(row, text=detail, style="StudioMuted.TLabel", wraplength=360).pack(side="left")

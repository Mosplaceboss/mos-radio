"""Station operations dashboard — Mo's Place Studio home screen."""

from __future__ import annotations

import tkinter as tk

import ttkbootstrap as ttk
from PIL import Image, ImageTk
from ttkbootstrap.scrolled import ScrolledText

from app.core.background_tasks import run_in_background
from app.core.dashboard_model import DashboardSnapshot, StatusLight, build_dashboard_snapshot
from app.core.health_constants import HEALTH_ERROR, HEALTH_OK, HEALTH_WARN
from app.core.integration_snapshot import IntegrationSnapshot, build_integration_snapshot
from app.core.paths import assets_dir
from app.pages.base_page import BasePage
from app.ui.theme import StudioTheme

REFRESH_INTERVAL_MS = 5000

LIGHT_COLORS = {
    HEALTH_OK: StudioTheme.SUCCESS,
    HEALTH_WARN: StudioTheme.WARNING,
    HEALTH_ERROR: StudioTheme.DANGER,
}

SERVICE_LIGHTS = ("RadioDJ", "Voicebox", "LiveDJ", "News", "Requests", "Internet")


class DashboardPage(BasePage):
    page_id = "dashboard"
    page_title = "Dashboard"
    page_subtitle = "Your station command center"
    page_help = (
        "Green means a service is healthy, yellow means it needs attention, "
        "and red means it needs help. This screen updates automatically every few seconds."
    )

    def build(self) -> None:
        self._refresh_job: str | None = None
        self._value_labels: dict[str, ttk.Label] = {}
        self._up_next_labels: list[ttk.Label] = []
        self._status_lights: dict[str, tuple[tk.Canvas, ttk.Label]] = {}
        self._health_labels: dict[str, ttk.Label] = {}
        self._integration_labels: dict[str, ttk.Label] = {}
        self._alerts_text: ScrolledText | None = None
        self._module_overview_text: ScrolledText | None = None
        self._activity_text: ScrolledText | None = None
        self._last_activity_signature: tuple[str, ...] = ()
        self._refresh_in_progress = False
        self._refresh_cancelled = False
        self._refresh_generation = 0

        hero = ttk.Frame(self._body, style="Studio.TFrame")
        hero.pack(fill="x", pady=(0, 16))

        logo_path = assets_dir() / "logo.png"
        if logo_path.exists():
            image = Image.open(logo_path)
            image.thumbnail((72, 72), Image.Resampling.LANCZOS)
            self._logo_image = ImageTk.PhotoImage(image)
            ttk.Label(hero, image=self._logo_image, style="StudioHero.TLabel").pack(side="left", padx=(0, 16))

        hero_text = ttk.Frame(hero, style="Studio.TFrame")
        hero_text.pack(side="left", fill="x", expand=True)
        ttk.Label(hero_text, text="Mo's Place Radio", style="StudioHero.TLabel").pack(anchor="w")
        self._station_status_label = ttk.Label(
            hero_text,
            text="Checking station status…",
            style="StudioSubheading.TLabel",
        )
        self._station_status_label.pack(anchor="w", pady=(4, 0))

        station = ttk.Labelframe(
            self._body,
            text="Service Status",
            style="StudioCard.TLabelframe",
            padding=16,
        )
        station.pack(fill="x", pady=(0, 12))
        lights_row = ttk.Frame(station, style="StudioPanel.TFrame")
        lights_row.pack(fill="x")
        for index, name in enumerate(SERVICE_LIGHTS):
            cell = ttk.Frame(lights_row, style="StudioPanel.TFrame")
            cell.pack(side="left", expand=True, fill="x", padx=6)
            canvas = tk.Canvas(
                cell,
                width=64,
                height=64,
                bg=StudioTheme.BG_PANEL,
                highlightthickness=0,
            )
            canvas.pack()
            canvas.create_oval(10, 10, 54, 54, fill=StudioTheme.TEXT_MUTED, outline=StudioTheme.BORDER, width=2)
            ttk.Label(cell, text=name, style="StudioCard.TLabel", anchor="center").pack(pady=(8, 0))
            detail = ttk.Label(
                cell,
                text="Checking…",
                style="StudioMuted.TLabel",
                anchor="center",
                wraplength=130,
                justify="center",
            )
            detail.pack(pady=(4, 0))
            self._status_lights[name] = (canvas, detail)
            lights_row.columnconfigure(index, weight=1)

        integration = ttk.Labelframe(
            self._body,
            text="Alerts & Module Status",
            style="StudioCard.TLabelframe",
            padding=16,
        )
        integration.pack(fill="x", pady=(0, 12))

        alerts_row = ttk.Frame(integration, style="StudioPanel.TFrame")
        alerts_row.pack(fill="x", pady=(0, 12))
        ttk.Label(alerts_row, text="Current Alerts", style="StudioMuted.TLabel").pack(anchor="w", pady=(0, 4))
        self._alerts_text = ScrolledText(
            alerts_row,
            height=4,
            autohide=True,
            bootstyle="secondary",
            font=(StudioTheme.FONT_FAMILY, 10),
            state="disabled",
            wrap="word",
        )
        self._alerts_text.pack(fill="x")

        status_grid = ttk.Frame(integration, style="StudioPanel.TFrame")
        status_grid.pack(fill="x")
        for index, (key, title) in enumerate(
            (
                ("platform", "Platform"),
                ("inventory", "Inventory"),
                ("advertising", "Advertising"),
                ("schedule", "Schedule"),
                ("backup", "Backup"),
            )
        ):
            cell = ttk.Frame(status_grid, style="StudioPanel.TFrame")
            cell.grid(row=index // 3, column=index % 3, sticky="nsew", padx=8, pady=6)
            ttk.Label(cell, text=title, style="StudioMetricTitle.TLabel").pack(anchor="w")
            label = ttk.Label(cell, text="—", style="StudioCard.TLabel", wraplength=260, justify="left")
            label.pack(anchor="w", pady=(4, 0))
            self._integration_labels[key] = label
            status_grid.columnconfigure(index % 3, weight=1)

        overview = ttk.Labelframe(
            self._body,
            text="Module Overview",
            style="StudioCard.TLabelframe",
            padding=16,
        )
        overview.pack(fill="x", pady=(0, 12))
        self._module_overview_text = ScrolledText(
            overview,
            height=6,
            autohide=True,
            bootstyle="secondary",
            font=(StudioTheme.FONT_FAMILY, 10),
            state="disabled",
            wrap="word",
        )
        self._module_overview_text.pack(fill="x")

        middle = ttk.Frame(self._body, style="Studio.TFrame")
        middle.pack(fill="both", expand=True)

        on_air = ttk.Labelframe(
            middle,
            text="On Air Now",
            style="StudioCard.TLabelframe",
            padding=16,
        )
        on_air.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self._add_metric_row(on_air, "personality", "Current Host")
        self._add_metric_row(on_air, "format", "Current Format")
        self._add_metric_row(on_air, "now_playing", "Now Playing")
        self._add_metric_row(on_air, "current_show", "Current Show")
        self._add_metric_row(on_air, "request_mode", "Request Mode")

        up_next = ttk.Labelframe(
            middle,
            text="Next Events",
            style="StudioCard.TLabelframe",
            padding=16,
        )
        up_next.pack(side="left", fill="both", expand=True, padx=(8, 0))
        self._next_event_label = ttk.Label(
            up_next,
            text="Next event: —",
            style="StudioMetric.TLabel",
            wraplength=420,
            justify="left",
        )
        self._next_event_label.pack(anchor="w", pady=(0, 12))
        ttk.Label(
            up_next,
            text="Upcoming schedule",
            style="StudioMuted.TLabel",
        ).pack(anchor="w", pady=(0, 8))
        for index in range(5):
            label = ttk.Label(
                up_next,
                text=f"{index + 1}. —",
                style="StudioCard.TLabel",
                wraplength=420,
                justify="left",
            )
            label.pack(anchor="w", pady=4)
            self._up_next_labels.append(label)

        lower = ttk.Frame(self._body, style="Studio.TFrame")
        lower.pack(fill="both", expand=True, pady=(12, 0))

        health = ttk.Labelframe(
            lower,
            text="Recent Activity",
            style="StudioCard.TLabelframe",
            padding=16,
        )
        health.pack(side="left", fill="both", expand=True, padx=(0, 8))
        for key, title in (
            ("last_news", "Last News"),
            ("last_livedj", "Last Live Show Update"),
            ("last_request", "Last Listener Request"),
            ("last_voice", "Last Voice Announcement"),
            ("last_rss", "Last News Feed Update"),
        ):
            row = ttk.Frame(health, style="StudioPanel.TFrame")
            row.pack(fill="x", pady=4)
            ttk.Label(row, text=title, style="StudioMuted.TLabel", width=24).pack(side="left")
            value = ttk.Label(row, text="—", style="StudioCard.TLabel", wraplength=360, justify="left")
            value.pack(side="left", fill="x", expand=True)
            self._health_labels[key] = value

        activity = ttk.Labelframe(
            lower,
            text="Station Log",
            style="StudioCard.TLabelframe",
            padding=16,
        )
        activity.pack(side="left", fill="both", expand=True, padx=(8, 0))
        self._activity_text = ScrolledText(
            activity,
            height=10,
            autohide=True,
            bootstyle="secondary",
            font=(StudioTheme.FONT_FAMILY, 10),
            state="disabled",
            wrap="word",
        )
        self._activity_text.pack(fill="both", expand=True)

        quick = ttk.Labelframe(
            self._body,
            text="Quick Actions",
            style="StudioCard.TLabelframe",
            padding=16,
        )
        quick.pack(fill="x", pady=(12, 0))
        quick_specs = (
            ("help", "Help"),
            ("programming", "Programming"),
            ("music_manager", "Music"),
            ("schedule", "Schedule"),
            ("personalities", "Personalities"),
            ("requests", "Requests"),
            ("voice_library", "Voice Library"),
            ("news_content_manager", "News"),
            ("advertising_manager", "Advertising"),
            ("website_audience_manager", "Website"),
            ("inventory", "Inventory"),
            ("operations_manager", "Operations"),
        )
        for index, (page_id, label) in enumerate(quick_specs):
            ttk.Button(
                quick,
                text=label,
                style="StudioAction.TButton",
                bootstyle="primary",
                command=lambda pid=page_id: self._open_page(pid),
            ).grid(row=index // 4, column=index % 4, sticky="ew", padx=8, pady=8)
            quick.columnconfigure(index % 4, weight=1)

        footer = ttk.Frame(self._body, style="Studio.TFrame")
        footer.pack(fill="x", pady=(12, 0))
        self._last_refresh_label = ttk.Label(footer, text="", style="StudioMuted.TLabel")
        self._last_refresh_label.pack(side="left")
        ttk.Label(
            footer,
            text="Updates automatically every 5 seconds",
            style="StudioMuted.TLabel",
        ).pack(side="right")

    def _add_metric_row(self, parent: ttk.Labelframe, key: str, title: str) -> None:
        row = ttk.Frame(parent, style="StudioPanel.TFrame")
        row.pack(fill="x", pady=6)
        ttk.Label(row, text=title, style="StudioMetricTitle.TLabel", width=18).pack(side="left")
        value = ttk.Label(row, text="—", style="StudioMetric.TLabel", wraplength=420, justify="left")
        value.pack(side="left", fill="x", expand=True)
        self._value_labels[key] = value

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

    def _open_page(self, page_id: str) -> None:
        if self.on_navigate:
            self.on_navigate(page_id)

    def refresh(self, *, quiet: bool = False) -> None:
        if self._refresh_in_progress:
            return
        self._refresh_in_progress = True
        generation = self._refresh_generation
        if not quiet:
            self._show_busy_cursor(True)
            self.set_status("Updating dashboard…")

        def work() -> tuple[DashboardSnapshot, IntegrationSnapshot]:
            return (
                build_dashboard_snapshot(self.config_manager),
                build_integration_snapshot(self.config_manager),
            )

        def complete(result: tuple[DashboardSnapshot, IntegrationSnapshot]) -> None:
            snapshot, integration = result
            if not quiet:
                self._show_busy_cursor(False)
            if generation != self._refresh_generation:
                return
            self._refresh_in_progress = False
            if self._refresh_cancelled:
                return
            self._apply_snapshot(snapshot)
            self._apply_integration(integration)
            if not quiet:
                self.set_status("Dashboard updated")

        def failed(error: Exception) -> None:
            if not quiet:
                self._show_busy_cursor(False)
            if generation != self._refresh_generation:
                return
            self._refresh_in_progress = False
            if not quiet:
                self._show_error_dialog("Dashboard Update", str(error))
            elif not self._refresh_cancelled:
                self.set_status("Dashboard update failed")

        run_in_background(self, work, complete, on_error=failed)

    def _apply_snapshot(self, snapshot: DashboardSnapshot) -> None:
        for light in snapshot.station_lights:
            if light.name in self._status_lights:
                self._set_status_light(light)

        current = snapshot.current_event
        current_text = (
            f"{current.show_name} · {current.day} {current.start_time}–{current.end_time}"
            if current.show_name != "—"
            else "No show scheduled right now"
        )

        self._value_labels["personality"].configure(text=snapshot.on_air_personality)
        self._value_labels["format"].configure(text=snapshot.music_format)
        self._value_labels["current_show"].configure(text=current_text)
        self._value_labels["request_mode"].configure(text=snapshot.request_mode)
        self._value_labels["now_playing"].configure(text=snapshot.now_playing)

        if snapshot.upcoming_events:
            next_event = snapshot.upcoming_events[0]
            self._next_event_label.configure(
                text=(
                    f"Next event: {next_event.show_name} with {next_event.personality} · "
                    f"{next_event.day} {next_event.start_time}–{next_event.end_time}"
                )
            )
        else:
            self._next_event_label.configure(text="Next event: Nothing scheduled ahead")

        for index, label in enumerate(self._up_next_labels):
            if index < len(snapshot.upcoming_events):
                event = snapshot.upcoming_events[index]
                label.configure(
                    text=(
                        f"{index + 1}. {event.show_name} · {event.personality} · "
                        f"{event.day} {event.start_time}–{event.end_time}"
                    )
                )
            else:
                label.configure(text=f"{index + 1}. —")

        self._health_labels["last_news"].configure(text=snapshot.last_news_run)
        self._health_labels["last_livedj"].configure(text=snapshot.last_livedj_run)
        self._health_labels["last_request"].configure(text=snapshot.last_request_run)
        self._health_labels["last_voice"].configure(text=snapshot.last_voice_generation)
        self._health_labels["last_rss"].configure(text=snapshot.last_rss_update)

        self._update_activity_log(snapshot.activity_log)
        self._last_refresh_label.configure(text=f"Last updated: {snapshot.clock} · {snapshot.clock_date}")
        self._station_status_label.configure(text=self._station_summary(snapshot))

    def _apply_integration(self, integration: IntegrationSnapshot) -> None:
        if self._alerts_text:
            alert_text = "\n".join(f"• {line}" for line in integration.alerts)
            self._alerts_text.text.configure(state="normal")
            self._alerts_text.delete("1.0", "end")
            self._alerts_text.insert("end", alert_text)
            self._alerts_text.text.configure(state="disabled")

        mapping = {
            "platform": f"{integration.platform_status.upper()} — {integration.platform_message}",
            "inventory": f"{integration.inventory_status.upper()} — {integration.inventory_message}",
            "advertising": integration.advertising_summary,
            "schedule": integration.schedule_summary,
            "backup": integration.backup_summary,
        }
        for key, value in mapping.items():
            if key in self._integration_labels:
                self._integration_labels[key].configure(text=value)

        if self._module_overview_text:
            self._module_overview_text.text.configure(state="normal")
            self._module_overview_text.delete("1.0", "end")
            self._module_overview_text.insert("end", "\n".join(integration.module_lines))
            self._module_overview_text.text.configure(state="disabled")

    def _station_summary(self, snapshot: DashboardSnapshot) -> str:
        service_lights = [light for light in snapshot.station_lights if light.name in SERVICE_LIGHTS]
        if any(light.status == HEALTH_ERROR for light in service_lights):
            return "Station status: One or more services need attention"
        if any(light.status == HEALTH_WARN for light in service_lights):
            return "Station status: All services running with minor warnings"
        if service_lights:
            return "Station status: All services healthy"
        return "Station status: Checking services…"

    def _set_status_light(self, light: StatusLight) -> None:
        widgets = self._status_lights.get(light.name)
        if not widgets:
            return
        canvas, detail_label = widgets
        color = LIGHT_COLORS.get(light.status, StudioTheme.TEXT_MUTED)
        canvas.delete("all")
        canvas.create_oval(10, 10, 54, 54, fill=color, outline=StudioTheme.BORDER, width=2)
        detail_label.configure(text=light.detail[:80])

    def _update_activity_log(self, lines: list[str]) -> None:
        if not self._activity_text:
            return
        signature = tuple(lines)
        if signature == self._last_activity_signature:
            return
        self._last_activity_signature = signature

        self._activity_text.text.configure(state="normal")
        self._activity_text.delete("1.0", "end")
        if lines:
            self._activity_text.insert("end", "\n".join(lines))
        else:
            self._activity_text.insert("end", "No recent station activity yet.")
        self._activity_text.text.configure(state="disabled")
        self._activity_text.text.yview_moveto(1.0)

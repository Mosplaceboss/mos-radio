"""Station operations dashboard — Mo's Place Studio home screen."""

from __future__ import annotations

import tkinter as tk

import ttkbootstrap as ttk
from ttkbootstrap.scrolled import ScrolledText

from app.core.dashboard_model import DashboardSnapshot, StatusLight, build_dashboard_snapshot
from app.core.health_constants import HEALTH_ERROR, HEALTH_OK, HEALTH_WARN
from app.pages.base_page import BasePage
from app.ui.theme import StudioTheme

REFRESH_INTERVAL_MS = 5000

LIGHT_COLORS = {
    HEALTH_OK: StudioTheme.SUCCESS,
    HEALTH_WARN: StudioTheme.WARNING,
    HEALTH_ERROR: StudioTheme.DANGER,
}


class DashboardPage(BasePage):
    page_id = "dashboard"
    page_title = "Dashboard"
    page_subtitle = "Station home screen — read-only monitoring, health, and quick navigation"

    def build(self) -> None:
        self._refresh_job: str | None = None
        self._value_labels: dict[str, ttk.Label] = {}
        self._up_next_labels: list[ttk.Label] = []
        self._status_lights: dict[str, tuple[tk.Canvas, ttk.Label]] = {}
        self._health_labels: dict[str, ttk.Label] = {}
        self._activity_text: ScrolledText | None = None
        self._last_activity_signature: tuple[str, ...] = ()

        station = ttk.Labelframe(
            self._body,
            text="Station Status",
            style="StudioCard.TLabelframe",
            padding=16,
        )
        station.pack(fill="x", pady=(0, 12))
        lights_row = ttk.Frame(station, style="StudioPanel.TFrame")
        lights_row.pack(fill="x")
        for index, name in enumerate(
            ("LiveDJ", "News", "Requests", "Voicebox", "RadioDJ", "Internet", "Now Playing")
        ):
            cell = ttk.Frame(lights_row, style="StudioPanel.TFrame")
            cell.pack(side="left", expand=True, fill="x", padx=6)
            canvas = tk.Canvas(
                cell,
                width=56,
                height=56,
                bg=StudioTheme.BG_PANEL,
                highlightthickness=0,
            )
            canvas.pack()
            canvas.create_oval(8, 8, 48, 48, fill=StudioTheme.TEXT_MUTED, outline=StudioTheme.BORDER, width=2)
            title = ttk.Label(cell, text=name, style="StudioCard.TLabel", anchor="center")
            title.pack(pady=(6, 0))
            detail = ttk.Label(
                cell,
                text="—",
                style="StudioMuted.TLabel",
                anchor="center",
                wraplength=120,
                justify="center",
            )
            detail.pack(pady=(2, 0))
            self._status_lights[name] = (canvas, detail)
            lights_row.columnconfigure(index, weight=1)

        middle = ttk.Frame(self._body, style="Studio.TFrame")
        middle.pack(fill="both", expand=True)

        on_air = ttk.Labelframe(
            middle,
            text="On Air Now",
            style="StudioCard.TLabelframe",
            padding=16,
        )
        on_air.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self._add_metric_row(on_air, "personality", "Current Personality")
        self._add_metric_row(on_air, "format", "Current Format")
        self._add_metric_row(on_air, "current_show", "Current Scheduled Event")
        self._add_metric_row(on_air, "request_mode", "Current Request Mode")
        self._add_metric_row(on_air, "now_playing", "Now Playing")

        up_next = ttk.Labelframe(
            middle,
            text="Up Next",
            style="StudioCard.TLabelframe",
            padding=16,
        )
        up_next.pack(side="left", fill="both", expand=True, padx=(8, 0))
        ttk.Label(
            up_next,
            text="Next 5 scheduled events",
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
            text="Today's Health",
            style="StudioCard.TLabelframe",
            padding=16,
        )
        health.pack(side="left", fill="both", expand=True, padx=(0, 8))
        for key, title in (
            ("last_news", "Last News Run"),
            ("last_livedj", "Last LiveDJ Run"),
            ("last_request", "Last Request"),
            ("last_voice", "Last Voice Generation"),
            ("last_rss", "Last RSS Update"),
        ):
            row = ttk.Frame(health, style="StudioPanel.TFrame")
            row.pack(fill="x", pady=4)
            ttk.Label(row, text=title, style="StudioMuted.TLabel", width=22).pack(side="left")
            value = ttk.Label(row, text="—", style="StudioCard.TLabel", wraplength=360, justify="left")
            value.pack(side="left", fill="x", expand=True)
            self._health_labels[key] = value

        activity = ttk.Labelframe(
            lower,
            text="Recent Activity",
            style="StudioCard.TLabelframe",
            padding=16,
        )
        activity.pack(side="left", fill="both", expand=True, padx=(8, 0))
        self._activity_text = ScrolledText(
            activity,
            height=10,
            autohide=True,
            bootstyle="secondary",
            font=("Consolas", 9),
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
            ("personalities", "Personalities"),
            ("schedule", "Schedule"),
            ("requests", "Requests"),
            ("voice_library", "Voice Library"),
            ("news", "News"),
            ("livedj", "LiveDJ"),
        )
        for index, (page_id, label) in enumerate(quick_specs):
            ttk.Button(
                quick,
                text=label,
                bootstyle="primary",
                command=lambda pid=page_id: self._open_page(pid),
            ).grid(row=index // 3, column=index % 3, sticky="ew", padx=8, pady=6)
            quick.columnconfigure(index % 3, weight=1)

        footer = ttk.Frame(self._body, style="Studio.TFrame")
        footer.pack(fill="x", pady=(12, 0))
        self._last_refresh_label = ttk.Label(footer, text="", style="StudioMuted.TLabel")
        self._last_refresh_label.pack(side="left")
        ttk.Label(
            footer,
            text="Auto-refresh every 5 seconds · read-only",
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
        for light in snapshot.station_lights:
            self._set_status_light(light)

        current = snapshot.current_event
        current_text = (
            f"{current.show_name} · {current.day} {current.start_time}–{current.end_time}"
            if current.show_name != "—"
            else "No scheduled event airing"
        )

        self._value_labels["personality"].configure(text=snapshot.on_air_personality)
        self._value_labels["format"].configure(text=snapshot.music_format)
        self._value_labels["current_show"].configure(text=current_text)
        self._value_labels["request_mode"].configure(text=snapshot.request_mode)
        self._value_labels["now_playing"].configure(text=snapshot.now_playing)

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
        self._last_refresh_label.configure(text=f"Last refreshed: {snapshot.clock} · {snapshot.clock_date}")

    def _set_status_light(self, light: StatusLight) -> None:
        widgets = self._status_lights.get(light.name)
        if not widgets:
            return
        canvas, detail_label = widgets
        color = LIGHT_COLORS.get(light.status, StudioTheme.TEXT_MUTED)
        canvas.delete("all")
        canvas.create_oval(8, 8, 48, 48, fill=color, outline=StudioTheme.BORDER, width=2)
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
            self._activity_text.insert("end", "No recent activity logged yet.")
        self._activity_text.text.configure(state="disabled")
        self._activity_text.text.yview_moveto(1.0)

"""Daily Operations — one simple screen for everyday station work."""

from __future__ import annotations

import tkinter as tk

import ttkbootstrap as ttk
from ttkbootstrap.scrolled import ScrolledText

from app.core.advertising_model import normalize_bundle as normalize_advertising
from app.core.advertising_storage import load_advertising_bundle
from app.core.background_tasks import run_in_background
from app.core.broadcasting_manager_model import BroadcastingSnapshot, build_broadcasting_snapshot, resolve_radiodj_executable
from app.core.health_constants import HEALTH_ERROR, HEALTH_OK, HEALTH_WARN
from app.core.hidden_process import popen_hidden
from app.core.operations import restart_livedj_watcher, restart_request_watcher, run_news_now
from app.core.publish_manager import integration_bundle
from app.pages.base_page import BasePage
from app.ui.confirm_dialog import confirm_action
from app.ui.theme import StudioTheme

REFRESH_INTERVAL_MS = 15_000

LIGHT_COLORS = {
    HEALTH_OK: StudioTheme.SUCCESS,
    HEALTH_WARN: StudioTheme.WARNING,
    HEALTH_ERROR: StudioTheme.DANGER,
}


class DailyOperationsPage(BasePage):
    page_id = "daily_operations"
    page_title = "Daily Operations"
    page_subtitle = "Everything you need for today's broadcast in one place"
    page_help = "Refresh status, review alerts, and run approved daily actions with confirmation."

    def build(self) -> None:
        self._refresh_job: str | None = None
        self._refresh_in_progress = False
        self._refresh_cancelled = False
        self._refresh_generation = 0
        self._status_labels: dict[str, ttk.Label] = {}
        self._service_widgets: dict[str, tuple[tk.Canvas, ttk.Label]] = {}

        toolbar = ttk.Frame(self._body, style="Studio.TFrame")
        toolbar.pack(fill="x", pady=(0, 12))
        ttk.Button(toolbar, text="Refresh", bootstyle="info", command=lambda: self.refresh(quiet=False)).pack(side="left")
        ttk.Button(toolbar, text="Open RadioDJ", bootstyle="primary", command=self._open_radiodj).pack(side="left", padx=8)
        ttk.Button(toolbar, text="Run News Now", bootstyle="secondary", command=self._run_news).pack(side="left", padx=8)
        ttk.Button(toolbar, text="Restart LiveDJ Watcher", bootstyle="secondary", command=self._restart_livedj).pack(
            side="left", padx=8
        )
        ttk.Button(toolbar, text="Restart Request Watcher", bootstyle="secondary", command=self._restart_requests).pack(
            side="left", padx=8
        )
        self._last_refresh = ttk.Label(toolbar, text="", style="StudioMuted.TLabel")
        self._last_refresh.pack(side="right")

        header = ttk.Labelframe(self._body, text="Station On Air", style="StudioCard.TLabelframe", padding=16)
        header.pack(fill="x", pady=(0, 12))
        self._on_air_label = ttk.Label(header, text="Checking…", style="StudioHero.TLabel")
        self._on_air_label.pack(anchor="w", pady=(0, 8))
        metrics = ttk.Frame(header, style="StudioPanel.TFrame")
        metrics.pack(fill="x")
        for index, (key, title) in enumerate(
            (
                ("current_host", "Current Host"),
                ("current_format", "Current Format"),
                ("now_playing", "Now Playing"),
                ("next_event", "Next Scheduled Event"),
            )
        ):
            cell = ttk.Frame(metrics, style="StudioPanel.TFrame")
            cell.grid(row=index // 2, column=index % 2, sticky="nsew", padx=8, pady=6)
            ttk.Label(cell, text=title, style="StudioMetricTitle.TLabel").pack(anchor="w")
            label = ttk.Label(cell, text="—", style="StudioMetric.TLabel", wraplength=360, justify="left")
            label.pack(anchor="w", pady=(4, 0))
            self._status_labels[key] = label
            metrics.columnconfigure(index % 2, weight=1)

        services = ttk.Labelframe(self._body, text="Service Status", style="StudioCard.TLabelframe", padding=16)
        services.pack(fill="x", pady=(0, 12))
        self._services_row = ttk.Frame(services, style="StudioPanel.TFrame")
        self._services_row.pack(fill="x")
        for name in ("RadioDJ", "Voicebox", "LiveDJ", "News", "Requests", "Website Scheduler"):
            cell = ttk.Frame(self._services_row, style="StudioPanel.TFrame")
            cell.pack(side="left", expand=True, fill="x", padx=6)
            canvas = tk.Canvas(cell, width=52, height=52, bg=StudioTheme.BG_PANEL, highlightthickness=0)
            canvas.pack()
            canvas.create_oval(8, 8, 44, 44, fill=StudioTheme.TEXT_MUTED, outline=StudioTheme.BORDER, width=2)
            ttk.Label(cell, text=name, style="StudioCard.TLabel", anchor="center").pack(pady=(4, 0))
            detail = ttk.Label(cell, text="—", style="StudioMuted.TLabel", anchor="center", wraplength=110, justify="center")
            detail.pack(pady=(2, 0))
            self._service_widgets[name] = (canvas, detail)

        lower = ttk.Frame(self._body, style="Studio.TFrame")
        lower.pack(fill="both", expand=True)
        ads = ttk.Labelframe(lower, text="Today's Advertising", style="StudioCard.TLabelframe", padding=12)
        ads.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self._ads_text = ScrolledText(ads, height=8, autohide=True, bootstyle="secondary", state="disabled", wrap="word")
        self._ads_text.pack(fill="both", expand=True)

        alerts = ttk.Labelframe(lower, text="Alerts", style="StudioCard.TLabelframe", padding=12)
        alerts.pack(side="left", fill="both", expand=True, padx=(8, 0))
        self._alerts_text = ScrolledText(
            alerts, height=8, autohide=True, bootstyle="secondary", state="disabled", wrap="word"
        )
        self._alerts_text.pack(fill="both", expand=True)

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

        def work() -> tuple[BroadcastingSnapshot, list[str]]:
            snapshot = build_broadcasting_snapshot(self.config_manager)
            advertising = normalize_advertising(load_advertising_bundle(self.config_manager))
            ad_lines = [
                f"• {sponsor.get('name', 'Sponsor')}"
                for sponsor in advertising.get("sponsors", {}).get("sponsors", [])
                if sponsor.get("enabled")
            ]
            for campaign in advertising.get("campaigns", {}).get("campaigns", []):
                if campaign.get("enabled"):
                    ad_lines.append(f"• {campaign.get('name', 'Campaign')}")
            if not ad_lines:
                ad_lines = ["No active advertising configured for today."]
            return snapshot, ad_lines

        def complete(result: tuple[BroadcastingSnapshot, list[str]]) -> None:
            snapshot, ad_lines = result
            if not quiet:
                self._show_busy_cursor(False)
            if generation != self._refresh_generation:
                return
            self._refresh_in_progress = False
            if self._refresh_cancelled:
                return
            self._apply_snapshot(snapshot, ad_lines)
            if not quiet:
                self.set_status("Daily operations updated")

        def failed(error: Exception) -> None:
            if not quiet:
                self._show_busy_cursor(False)
            if generation != self._refresh_generation:
                return
            self._refresh_in_progress = False
            if not quiet:
                self._show_error_dialog("Daily Operations", str(error))

        run_in_background(self, work, complete, on_error=failed)

    def _apply_snapshot(self, snapshot: BroadcastingSnapshot, ad_lines: list[str]) -> None:
        self._on_air_label.configure(text=f"{snapshot.on_air_status} · Updated {snapshot.last_refreshed}")
        mapping = {
            "current_host": snapshot.current_host,
            "current_format": snapshot.current_format,
            "now_playing": snapshot.radiodj.now_playing,
            "next_event": snapshot.next_event,
        }
        for key, value in mapping.items():
            if key in self._status_labels:
                self._status_labels[key].configure(text=value)

        lookup = {light.name: light for light in snapshot.health_lights}
        aliases = {
            "LiveDJ": "LiveDJ",
            "News": "News",
            "Requests": "Requests",
        }
        for name, widgets in self._service_widgets.items():
            canvas, detail = widgets
            light = lookup.get(name)
            if not light and name in aliases:
                light = lookup.get(aliases[name])
            if name == "Website Scheduler":
                color = LIGHT_COLORS.get(snapshot.website_scheduler_status, StudioTheme.TEXT_MUTED)
                canvas.delete("all")
                canvas.create_oval(8, 8, 44, 44, fill=color, outline=StudioTheme.BORDER, width=2)
                detail.configure(text=snapshot.website_scheduler_detail[:70])
                continue
            if not light:
                detail.configure(text="Not monitored")
                continue
            color = LIGHT_COLORS.get(light.status, StudioTheme.TEXT_MUTED)
            canvas.delete("all")
            canvas.create_oval(8, 8, 44, 44, fill=color, outline=StudioTheme.BORDER, width=2)
            detail.configure(text=light.detail[:70])

        self._set_text(self._ads_text, "\n".join(ad_lines))
        self._set_text(self._alerts_text, "\n".join(f"• {line}" for line in snapshot.alerts))
        self._last_refresh.configure(text=f"Last refreshed: {snapshot.last_refreshed}")

    @staticmethod
    def _set_text(widget: ScrolledText, content: str) -> None:
        widget.text.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("end", content)
        widget.text.configure(state="disabled")

    def _settings(self) -> dict:
        return self.config_manager.load("settings", {})

    def _integration(self) -> dict:
        return integration_bundle(self._settings())

    def _confirmed(self, title: str, message: str) -> bool:
        return confirm_action(title, message, self._settings())

    def _open_radiodj(self) -> None:
        if not self._confirmed("Open RadioDJ", "Open RadioDJ on this computer?"):
            return
        exe = resolve_radiodj_executable(self._settings(), self.config_manager)
        if not exe:
            self._show_error_dialog("Open RadioDJ", "RadioDJ executable was not found.")
            return
        try:
            popen_hidden([str(exe)], cwd=exe.parent)
            self.set_status("RadioDJ launched.")
        except OSError as exc:
            self._show_error_dialog("Open RadioDJ", str(exc))

    def _run_news(self) -> None:
        if not self._confirmed("Run News Now", "Run the news automation now?"):
            return
        _ok, msg = run_news_now(self._integration())
        self.set_status(msg)

    def _restart_livedj(self) -> None:
        if not self._confirmed("Restart LiveDJ Watcher", "Restart the LiveDJ watcher?"):
            return
        _ok, msg = restart_livedj_watcher(self._integration())
        self.set_status(msg)

    def _restart_requests(self) -> None:
        if not self._confirmed("Restart Request Watcher", "Restart the Request watcher?"):
            return
        _ok, msg = restart_request_watcher(self._integration())
        self.set_status(msg)

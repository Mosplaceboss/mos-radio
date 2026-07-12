"""Live systems integration setup and connection testing."""

from __future__ import annotations

import tkinter as tk

import ttkbootstrap as ttk
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.scrolled import ScrolledText

from app.core.live_connector import (
    ensure_local_integration_template,
    import_all_from_live,
    load_local_integration,
    save_local_integration,
    test_all_connections,
)
from app.core.studio_info import environment_mode
from app.pages.base_page import BasePage
from app.ui.confirm_dialog import confirm_action


class IntegrationPage(BasePage):
    page_id = "integration"
    page_title = "Live Integration"
    page_subtitle = "Connect Studio to your live RadioDJ, Voicebox, LiveDJ, News, and Request systems"

    def build(self) -> None:
        toolbar = ttk.Frame(self._body, style="Studio.TFrame")
        toolbar.pack(fill="x", pady=(0, 12))
        ttk.Button(toolbar, text="Test All Connections", bootstyle="info", command=self._test_connections).pack(
            side="left"
        )
        ttk.Button(toolbar, text="Import All from Live", bootstyle="secondary", command=self._import_all).pack(
            side="left", padx=8
        )
        ttk.Button(toolbar, text="Save Live Paths", bootstyle="primary", command=self._save_local).pack(side="right")
        ttk.Button(toolbar, text="Use Repo Automation Paths", bootstyle="secondary", command=self._use_repo_paths).pack(
            side="right", padx=8
        )

        status = ttk.Labelframe(self._body, text="Connection Status", style="StudioCard.TLabelframe", padding=16)
        status.pack(fill="both", expand=True, pady=(0, 12))
        self._status_box = ScrolledText(status, height=12, autohide=True, bootstyle="secondary", font=("Consolas", 9))
        self._status_box.pack(fill="both", expand=True)

        paths = ttk.Labelframe(self._body, text="Live System Paths", style="StudioCard.TLabelframe", padding=16)
        paths.pack(fill="x", pady=(0, 12))
        self._enabled = tk.BooleanVar(value=False)
        ttk.Checkbutton(paths, text="Live integration enabled", variable=self._enabled).pack(anchor="w", pady=(0, 8))

        self._fields: dict[str, tk.StringVar] = {}
        specs = (
            ("now_playing_file", "Now Playing File"),
            ("livedj_personalities", "LiveDJ Personalities"),
            ("livedj_schedule", "LiveDJ Schedule"),
            ("livedj_voice_library", "LiveDJ Voice Library"),
            ("requests_config", "Request Settings"),
            ("news_config", "News Configuration"),
            ("livedj_start", "LiveDJ Start Script"),
            ("livedj_restart", "LiveDJ Restart Script"),
            ("requests_start", "Request Watcher Start Script"),
            ("requests_restart", "Request Watcher Restart Script"),
            ("news_run_now", "News Run Now Script"),
            ("voicebox_api_url", "Voicebox API URL"),
            ("radiodj_process", "RadioDJ Process Name"),
        )
        for key, label in specs:
            row = ttk.Frame(paths, style="StudioPanel.TFrame")
            row.pack(fill="x", pady=3)
            ttk.Label(row, text=label, style="StudioMuted.TLabel", width=30).pack(side="left")
            variable = tk.StringVar()
            ttk.Entry(row, textvariable=variable).pack(side="left", fill="x", expand=True)
            self._fields[key] = variable

        help_panel = ttk.Labelframe(self._body, text="Setup", style="StudioCard.TLabelframe", padding=16)
        help_panel.pack(fill="x")
        ttk.Label(
            help_panel,
            text=(
                "Point each path at your existing live utility files and launcher scripts. "
                "Studio reads and publishes configuration only — it does not rewrite your engines. "
                "Edit Automation/*/engine.local.cmd on the station PC to call your real watcher scripts."
            ),
            style="StudioCard.TLabel",
            wraplength=760,
            justify="left",
        ).pack(anchor="w")

    def on_show(self) -> None:
        ensure_local_integration_template()
        self._load_local()
        self._test_connections(quiet=True)

    def _settings(self) -> dict:
        return self.config_manager.load("settings", {})

    def _load_local(self) -> None:
        local = load_local_integration()
        settings = self._settings()
        integration = settings.get("integration", {})
        livedj = local.get("live_paths", {}).get("livedj", {})
        requests = local.get("live_paths", {}).get("requests", {})
        news = local.get("live_paths", {}).get("news", {})
        scripts = local.get("engine_scripts", {})

        self._enabled.set(bool(local.get("enabled")))
        self._fields["now_playing_file"].set(local.get("now_playing_file", ""))
        self._fields["livedj_personalities"].set(
            livedj.get("personalities", "Automation/LiveDJ/personalities.json")
        )
        self._fields["livedj_schedule"].set(livedj.get("schedule", "Automation/LiveDJ/schedule.json"))
        self._fields["livedj_voice_library"].set(
            livedj.get("voice_library", "Automation/LiveDJ/voice_library.json")
        )
        self._fields["requests_config"].set(requests.get("config", "Automation/Requests/requests.json"))
        self._fields["news_config"].set(news.get("config", "Automation/News/news.json"))
        self._fields["livedj_start"].set(scripts.get("livedj_start", "Automation/LiveDJ/start_watcher.bat"))
        self._fields["livedj_restart"].set(scripts.get("livedj_restart", "Automation/LiveDJ/restart_watcher.bat"))
        self._fields["requests_start"].set(scripts.get("requests_start", "Automation/Requests/start_watcher.bat"))
        self._fields["requests_restart"].set(
            scripts.get("requests_restart", "Automation/Requests/restart_watcher.bat")
        )
        self._fields["news_run_now"].set(scripts.get("news_run_now", "Automation/News/run_news_now.bat"))
        self._fields["voicebox_api_url"].set(local.get("voicebox_api_url", integration.get("voicebox_api_url", "")))
        self._fields["radiodj_process"].set(local.get("radiodj_process", integration.get("radiodj_process", "")))
        self.set_status(f"Live integration · {environment_mode(settings)} mode")

    def _collect_local(self) -> dict:
        return {
            "enabled": self._enabled.get(),
            "now_playing_file": self._fields["now_playing_file"].get().strip(),
            "radiodj_process": self._fields["radiodj_process"].get().strip(),
            "voicebox_api_url": self._fields["voicebox_api_url"].get().strip(),
            "live_paths": {
                "livedj": {
                    "personalities": self._fields["livedj_personalities"].get().strip(),
                    "schedule": self._fields["livedj_schedule"].get().strip(),
                    "voice_library": self._fields["livedj_voice_library"].get().strip(),
                },
                "requests": {"config": self._fields["requests_config"].get().strip()},
                "news": {"config": self._fields["news_config"].get().strip()},
            },
            "engine_scripts": {
                "livedj_start": self._fields["livedj_start"].get().strip(),
                "livedj_restart": self._fields["livedj_restart"].get().strip(),
                "requests_start": self._fields["requests_start"].get().strip(),
                "requests_restart": self._fields["requests_restart"].get().strip(),
                "news_run_now": self._fields["news_run_now"].get().strip(),
            },
        }

    def _save_local(self) -> None:
        save_local_integration(self._collect_local())
        self.set_status("Live integration paths saved")
        self._test_connections(quiet=True)

    def _use_repo_paths(self) -> None:
        self._enabled.set(True)
        defaults = {
            "now_playing_file": "",
            "livedj_personalities": "Automation/LiveDJ/personalities.json",
            "livedj_schedule": "Automation/LiveDJ/schedule.json",
            "livedj_voice_library": "Automation/LiveDJ/voice_library.json",
            "requests_config": "Automation/Requests/requests.json",
            "news_config": "Automation/News/news.json",
            "livedj_start": "Automation/LiveDJ/start_watcher.bat",
            "livedj_restart": "Automation/LiveDJ/restart_watcher.bat",
            "requests_start": "Automation/Requests/start_watcher.bat",
            "requests_restart": "Automation/Requests/restart_watcher.bat",
            "news_run_now": "Automation/News/run_news_now.bat",
        }
        for key, value in defaults.items():
            self._fields[key].set(value)
        self._save_local()

    def _test_connections(self, *, quiet: bool = False) -> None:
        save_local_integration(self._collect_local())
        results = test_all_connections(self._settings())
        lines = [f"{'OK' if result.ok else 'FAIL'} · {result.name}: {result.detail}" for result in results]
        self._status_box.delete("1.0", "end")
        self._status_box.insert("end", "\n".join(lines))
        ok_count = sum(1 for result in results if result.ok)
        message = f"{ok_count}/{len(results)} checks passed"
        if not quiet:
            Messagebox.show_info("\n".join(lines[:20]), "Live Integration Test")
        self.set_status(message)

    def _import_all(self) -> None:
        if not confirm_action(
            "Import All from Live",
            "Import live LiveDJ, Request, and News configuration into Studio development config?",
            self._settings(),
        ):
            return
        save_local_integration(self._collect_local())
        ok, message = import_all_from_live(self._settings())
        for key in ("personalities", "schedule", "voice_library", "requests", "news"):
            self.config_manager._cache.pop(key, None)
        if ok:
            Messagebox.show_info(message, "Import All")
        else:
            Messagebox.show_warning(message, "Import All")
        self.set_status("Live import completed" if ok else "Live import found no files")

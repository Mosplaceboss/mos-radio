"""News integration — RSS feeds, task status, publish, and restore."""

from __future__ import annotations

import tkinter as tk

import ttkbootstrap as ttk
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.scrolled import ScrolledFrame

from app.core.background_tasks import run_in_background
from app.core.integration_settings import news_live_paths
from app.core.news_loader import NewsLoadResult, load_news_page_data
from app.core.news_model import validate_news_data
from app.core.publish_manager import import_news_from_live, integration_bundle, publish_news, restore_news_backup
from app.core.studio_info import environment_mode
from app.pages.base_page import BasePage
from app.ui.confirm_dialog import confirm_action


class NewsPage(BasePage):
    page_id = "news"
    page_title = "News"
    page_subtitle = "Read and edit news configuration — publish safely without rewriting the news engine"

    def build(self) -> None:
        self._data: dict = {}
        self._autosave_job: str | None = None
        self._loading = False
        self._load_in_progress = False
        self._load_generation = 0
        self._feed_rows: list[dict[str, tk.Variable]] = []

        toolbar = ttk.Frame(self._body, style="Studio.TFrame")
        toolbar.pack(fill="x", pady=(0, 12))
        self._loading_label = ttk.Label(toolbar, text="", style="StudioMuted.TLabel")
        self._loading_label.pack(side="left", padx=(0, 12))
        self._error_label = ttk.Label(toolbar, text="", style="StudioMuted.TLabel", wraplength=520)
        self._error_label.pack(side="left", fill="x", expand=True)
        ttk.Button(toolbar, text="Import from News", bootstyle="secondary", command=self._import_live).pack(side="left")
        ttk.Button(toolbar, text="Reload", bootstyle="secondary", command=self._load).pack(side="left", padx=8)
        ttk.Button(toolbar, text="Publish to News", bootstyle="primary", command=self._publish).pack(side="right")
        ttk.Button(toolbar, text="Restore Last Backup", bootstyle="warning", command=self._restore).pack(
            side="right", padx=8
        )

        status = ttk.Labelframe(self._body, text="Task Status", style="StudioCard.TLabelframe", padding=16)
        status.pack(fill="x", pady=(0, 12))
        self._enabled_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(status, text="News automation enabled", variable=self._enabled_var, command=self._on_changed).pack(
            anchor="w"
        )
        self._last_run_label = ttk.Label(status, text="Last successful run: —", style="StudioCard.TLabel")
        self._last_run_label.pack(anchor="w", pady=(8, 0))
        self._path_label = ttk.Label(status, text="", style="StudioMuted.TLabel", wraplength=760)
        self._path_label.pack(anchor="w", pady=(8, 0))

        feeds = ttk.Labelframe(self._body, text="RSS Sources", style="StudioCard.TLabelframe", padding=16)
        feeds.pack(fill="both", expand=True)
        header = ttk.Frame(feeds, style="StudioPanel.TFrame")
        header.pack(fill="x", pady=(0, 8))
        ttk.Label(header, text="Enabled", style="StudioMuted.TLabel", width=8).pack(side="left")
        ttk.Label(header, text="Name", style="StudioMuted.TLabel", width=24).pack(side="left")
        ttk.Label(header, text="Feed URL", style="StudioMuted.TLabel").pack(side="left", fill="x", expand=True)
        ttk.Button(header, text="Add Feed", bootstyle="secondary", command=self._add_feed).pack(side="right")

        scroll = ScrolledFrame(feeds, autohide=True, bootstyle="secondary")
        scroll.pack(fill="both", expand=True)
        self._feeds_container = scroll.container

    def on_show(self) -> None:
        self._begin_background_load()

    def on_hide(self) -> None:
        self._load_generation += 1
        self._load_in_progress = False
        self._loading_label.configure(text="")
        self._show_busy_cursor(False)

    def _begin_background_load(self) -> None:
        self._load_generation += 1
        generation = self._load_generation
        self._load_in_progress = True
        self._loading_label.configure(text="Loading news settings…")
        self._error_label.configure(text="")
        self._show_busy_cursor(True)

        def work() -> NewsLoadResult:
            return load_news_page_data(self.config_manager.path_for("news"))

        def complete(result: NewsLoadResult) -> None:
            if generation != self._load_generation:
                return
            self._load_in_progress = False
            try:
                self._apply_loaded_data(result)
            except Exception as exc:
                self._loading_label.configure(text="")
                self._show_busy_cursor(False)
                self._show_error_dialog("News", str(exc))
                return
            self._loading_label.configure(text="")
            self._show_busy_cursor(False)

        def failed(error: Exception) -> None:
            if generation != self._load_generation:
                return
            self._load_in_progress = False
            self._loading_label.configure(text="")
            self._show_busy_cursor(False)
            self._show_error_dialog("News", str(error))

        run_in_background(self, work, complete, on_error=failed)

    def _apply_loaded_data(self, result: NewsLoadResult) -> None:
        self._loading = True
        self._data = result.news_data
        self.config_manager._cache["news"] = result.news_data
        self._enabled_var.set(self._data.get("enabled", True))
        self._last_run_label.configure(text=f"Last successful run: {self._data.get('last_successful_run') or 'Not recorded'}")
        live = news_live_paths(self._integration())
        self._path_label.configure(
            text=f"Mode: {environment_mode(self._settings())} · Live config: {live['config']}"
        )
        self._render_feeds()
        self._loading = False
        if result.load_errors:
            self._error_label.configure(text="; ".join(result.load_errors))
            self.set_status("; ".join(result.load_errors))
        else:
            self._error_label.configure(text="")
            self.set_status("News configuration loaded")

    def _load(self) -> None:
        self._begin_background_load()

    def _render_feeds(self) -> None:
        for child in self._feeds_container.winfo_children():
            child.destroy()
        self._feed_rows.clear()

        for index, feed in enumerate(self._data.get("rss_feeds", [])):
            row = ttk.Frame(self._feeds_container, style="StudioPanel.TFrame")
            row.pack(fill="x", pady=4)
            enabled = tk.BooleanVar(value=feed.get("enabled", True))
            name = tk.StringVar(value=feed.get("name", ""))
            url = tk.StringVar(value=feed.get("url", ""))
            ttk.Checkbutton(row, variable=enabled, command=self._on_changed).pack(side="left", padx=(0, 8))
            ttk.Entry(row, textvariable=name, width=24).pack(side="left", padx=(0, 8))
            ttk.Entry(row, textvariable=url).pack(side="left", fill="x", expand=True, padx=(0, 8))
            ttk.Button(
                row,
                text="Remove",
                bootstyle="danger-outline",
                command=lambda idx=index: self._remove_feed(idx),
            ).pack(side="right")
            self._feed_rows.append({"enabled": enabled, "name": name, "url": url})

    def _add_feed(self) -> None:
        feeds = self._collect_feeds()
        feeds.append({"id": f"feed-new-{len(feeds)+1}", "name": "", "url": "", "enabled": True})
        self._data["rss_feeds"] = feeds
        self._render_feeds()
        self._schedule_save()

    def _remove_feed(self, index: int) -> None:
        feeds = self._collect_feeds()
        if 0 <= index < len(feeds):
            feeds.pop(index)
        self._data["rss_feeds"] = feeds
        self._render_feeds()
        self._schedule_save()

    def _collect_feeds(self) -> list[dict]:
        feeds = []
        for row, original in zip(self._feed_rows, self._data.get("rss_feeds", [])):
            feeds.append(
                {
                    "id": original.get("id"),
                    "name": row["name"].get().strip(),
                    "url": row["url"].get().strip(),
                    "enabled": row["enabled"].get(),
                }
            )
        return feeds

    def _settings(self) -> dict:
        return self.config_manager.load("settings", {})

    def _integration(self) -> dict:
        return integration_bundle(self._settings())

    def _collect_data(self) -> dict:
        from app.core.news_model import normalize_news_data

        data = normalize_news_data(self._data)
        data["enabled"] = self._enabled_var.get()
        data["rss_feeds"] = self._collect_feeds()
        return data

    def _on_changed(self) -> None:
        if self._loading:
            return
        self._schedule_save()

    def _schedule_save(self) -> None:
        if self._autosave_job:
            self.after_cancel(self._autosave_job)
        self._autosave_job = self.after(700, self._save_dev_copy)

    def _save_dev_copy(self) -> None:
        self._autosave_job = None
        data = self._collect_data()
        self._data = data
        self._persist_config_async(
            "news",
            data,
            status_message="News development config saved",
            error_title="Save News",
        )

    def _import_live(self) -> None:
        if not confirm_action(
            "Import from News",
            "Import live news configuration into Studio development config?",
            self._settings(),
        ):
            return

        def work():
            return import_news_from_live(self._integration())

        def complete(result: tuple[bool, str]) -> None:
            ok, message = result
            if ok:
                self.config_manager._cache.pop("news", None)
                self._begin_background_load()
                Messagebox.show_info(message, "Import from News")
            else:
                Messagebox.show_warning(message, "Import from News")
            self.set_status(message)

        self._run_async_task(work, complete, loading_message="Importing news settings…", error_title="Import News")

    def _publish(self) -> None:
        data = self._collect_data()
        errors = validate_news_data(data)
        if errors:
            Messagebox.show_error("\n".join(errors), "Cannot Publish")
            return
        if not confirm_action(
            "Publish to News",
            "Publish news configuration to the live news path?\n"
            "A timestamped backup will be created first.",
            self._settings(),
        ):
            return

        def work():
            return publish_news(self.config_manager, self._integration())

        def complete(result: tuple[bool, str]) -> None:
            ok, message = result
            if ok:
                Messagebox.show_info(message, "Publish to News")
            else:
                Messagebox.show_error(message, "Publish to News")
            self.set_status(message)

        self._run_async_task(work, complete, loading_message="Publishing news settings…", error_title="Publish News")

    def _restore(self) -> None:
        if not confirm_action(
            "Restore Last Backup",
            "Restore the most recent news backup to the live news path?",
            self._settings(),
        ):
            return

        def work():
            return restore_news_backup(self._integration())

        def complete(result: tuple[bool, str]) -> None:
            ok, message = result
            if ok:
                Messagebox.show_info(message, "Restore News Backup")
            else:
                Messagebox.show_warning(message, "Restore News Backup")
            self.set_status(message)

        self._run_async_task(work, complete, loading_message="Restoring news backup…", error_title="Restore News")

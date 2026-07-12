"""News & Content Manager — development news configuration control center."""

from __future__ import annotations

import tkinter as tk
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

import ttkbootstrap as ttk
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.scrolled import ScrolledText

from app.core.background_tasks import run_in_background
from app.core.news_content_model import (
    NEWS_ROLES,
    REPORT_OPTIONS,
    SPEAKING_STYLES,
    build_overview_snapshot,
    build_report_lines,
    generate_dev_script_preview,
    list_output_files,
    normalize_bundle,
    refresh_overview_from_bundle,
    test_rss_feed,
    validate_news_content,
)
from app.core.news_content_storage import load_news_content_bundle, news_dev_output_dir, save_news_content_bundle
from app.core.platform_manager import open_folder, platform_path
from app.core.schedule_model import DAYS
from app.core.voice_model import normalize_voice_library_data
from app.pages.base_page import BasePage

DAY_LABELS = {day: day.title() for day in DAYS}


class NewsContentManagerPage(BasePage):
    page_id = "news_content_manager"
    page_title = "News & Content Manager"
    page_subtitle = "Plan news personalities, feeds, schedules, and development output"
    page_help = (
        "Development configuration for Mo's Place news. Data is stored in StationData/News and "
        "reports in Reports/News. This does not publish or replace the live News system."
    )

    def build(self) -> None:
        self._bundle = normalize_bundle({})
        self._voices: list[dict[str, Any]] = []
        self._busy = False
        self._selected_personality_id: str | None = None
        self._selected_category_id: str | None = None
        self._selected_source_id: str | None = None
        self._selected_slot_id: str | None = None
        self._overview_labels: dict[str, ttk.Label] = {}

        toolbar = ttk.Frame(self._body, style="Studio.TFrame")
        toolbar.pack(fill="x", pady=(0, 12))
        ttk.Button(
            toolbar,
            text="Save News Data",
            style="StudioAction.TButton",
            bootstyle="primary",
            command=self._save,
        ).pack(side="right")
        ttk.Button(
            toolbar,
            text="Validate",
            style="StudioAction.TButton",
            bootstyle="info",
            command=self._run_validation,
        ).pack(side="right", padx=8)
        ttk.Button(toolbar, text="Reload", bootstyle="secondary", command=self._load).pack(side="left")

        self._notebook = ttk.Notebook(self._body, bootstyle="primary")
        self._notebook.pack(fill="both", expand=True)
        self._build_overview_tab()
        self._build_personalities_tab()
        self._build_categories_tab()
        self._build_rss_tab()
        self._build_schedule_tab()
        self._build_script_rules_tab()
        self._build_voice_tab()
        self._build_output_tab()
        self._build_validation_tab()
        self._build_reports_tab()

    def on_show(self) -> None:
        self._load()

    def _load(self) -> None:
        self._voices = normalize_voice_library_data(
            self.config_manager.load("voice_library", {"voices": []})
        ).get("voices", [])
        self._bundle = normalize_bundle(load_news_content_bundle(self.config_manager))
        self._bundle["overview"] = refresh_overview_from_bundle(self._bundle, self.config_manager)
        self._refresh_all_views()
        self.set_status("News & Content data loaded")

    def _save(self) -> None:
        if self._busy:
            return
        self._busy = True
        self._bundle["overview"] = refresh_overview_from_bundle(self._bundle, self.config_manager)
        payload = deepcopy(self._bundle)

        def work() -> None:
            save_news_content_bundle(payload, self.config_manager)

        def complete(_: None) -> None:
            self._busy = False
            self.set_status("News data saved")

        def failed(error: Exception) -> None:
            self._busy = False
            self._show_error_dialog("Save News Data", str(error))

        self.set_status("Saving news data…")
        run_in_background(self, work, lambda _: complete(None), on_error=failed)

    def _run_validation(self) -> None:
        warnings = validate_news_content(self._bundle, self.config_manager)
        self._bundle["state"]["last_validated"] = datetime.now().strftime("%Y-%m-%d %I:%M %p")
        self._bundle["overview"]["errors_warnings"] = warnings
        self._refresh_validation_tab(warnings)
        self._refresh_overview()
        self.set_status("News validation complete")

    def _refresh_all_views(self) -> None:
        warnings = validate_news_content(self._bundle, self.config_manager)
        self._refresh_overview()
        self._refresh_personalities()
        self._refresh_categories()
        self._refresh_rss_sources()
        self._refresh_schedule()
        self._refresh_script_rules()
        self._refresh_voice_settings()
        self._refresh_output()
        self._refresh_validation_tab(warnings)

    @staticmethod
    def _set_scroll_text(widget: ScrolledText, content: str) -> None:
        widget.text.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("end", content)
        widget.text.configure(state="disabled")

    def _build_overview_tab(self) -> None:
        tab = ttk.Frame(self._notebook, style="Studio.TFrame", padding=12)
        self._notebook.add(tab, text="News Overview")
        grid = ttk.Frame(tab, style="Studio.TFrame")
        grid.pack(fill="x")
        specs = (
            ("morning_status", "Morning News"),
            ("midday_status", "Midday News"),
            ("afternoon_status", "Afternoon News"),
            ("last_successful_run", "Last Successful Run"),
            ("next_scheduled_run", "Next Scheduled Run"),
        )
        for index, (key, title) in enumerate(specs):
            card = ttk.Labelframe(grid, text=title, style="StudioCard.TLabelframe", padding=12)
            card.grid(row=index // 3, column=index % 3, sticky="nsew", padx=8, pady=8)
            label = ttk.Label(card, text="—", style="StudioMetric.TLabel", wraplength=220, justify="left")
            label.pack(anchor="w")
            self._overview_labels[key] = label
            grid.columnconfigure(index % 3, weight=1)

        lower = ttk.Frame(tab, style="Studio.TFrame")
        lower.pack(fill="both", expand=True, pady=(12, 0))
        output_card = ttk.Labelframe(lower, text="Current Output Files", style="StudioCard.TLabelframe", padding=12)
        output_card.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self._output_files_text = ScrolledText(
            output_card, height=10, autohide=True, bootstyle="secondary", state="disabled", wrap="word"
        )
        self._output_files_text.pack(fill="both", expand=True)

        alerts_card = ttk.Labelframe(lower, text="Errors and Warnings", style="StudioCard.TLabelframe", padding=12)
        alerts_card.pack(side="left", fill="both", expand=True, padx=(8, 0))
        self._overview_alerts_text = ScrolledText(
            alerts_card, height=10, autohide=True, bootstyle="secondary", state="disabled", wrap="word"
        )
        self._overview_alerts_text.pack(fill="both", expand=True)

    def _refresh_overview(self) -> None:
        snapshot = build_overview_snapshot(self._bundle)
        mapping = {
            "morning_status": snapshot.morning_status,
            "midday_status": snapshot.midday_status,
            "afternoon_status": snapshot.afternoon_status,
            "last_successful_run": snapshot.last_successful_run,
            "next_scheduled_run": snapshot.next_scheduled_run,
        }
        for key, value in mapping.items():
            if key in self._overview_labels:
                self._overview_labels[key].configure(text=value)
        files = snapshot.current_output_files or ["No output files found."]
        self._set_scroll_text(self._output_files_text, "\n".join(files))
        alerts = snapshot.errors_warnings or ["No errors or warnings."]
        self._set_scroll_text(self._overview_alerts_text, "\n".join(f"• {line}" for line in alerts))

    def _build_personalities_tab(self) -> None:
        tab = ttk.Frame(self._notebook, style="Studio.TFrame", padding=12)
        self._notebook.add(tab, text="News Personalities")
        toolbar = ttk.Frame(tab, style="Studio.TFrame")
        toolbar.pack(fill="x", pady=(0, 8))
        ttk.Button(toolbar, text="Add Personality", bootstyle="success", command=self._add_personality).pack(side="left")
        ttk.Button(toolbar, text="Delete Personality", bootstyle="danger", command=self._delete_personality).pack(
            side="left", padx=8
        )

        panes = ttk.Panedwindow(tab, orient="horizontal", bootstyle="secondary")
        panes.pack(fill="both", expand=True)
        list_panel = ttk.Labelframe(panes, text="Personalities", style="StudioCard.TLabelframe", padding=8)
        panes.add(list_panel, weight=1)
        self._personalities_tree = ttk.Treeview(
            list_panel,
            columns=("name", "role", "enabled"),
            show="headings",
            bootstyle="info",
            height=14,
        )
        for col, heading in (("name", "Name"), ("role", "Role"), ("enabled", "Active")):
            self._personalities_tree.heading(col, text=heading)
        self._personalities_tree.pack(fill="both", expand=True)
        self._personalities_tree.bind("<<TreeviewSelect>>", self._on_personality_select)

        form = ttk.Labelframe(panes, text="Personality Details", style="StudioCard.TLabelframe", padding=12)
        panes.add(form, weight=2)
        self._personality_fields: dict[str, tk.Variable] = {}
        for key, label in (("name", "Name"), ("notes", "Notes")):
            row = ttk.Frame(form, style="StudioPanel.TFrame")
            row.pack(fill="x", pady=4)
            ttk.Label(row, text=label, style="StudioMuted.TLabel", width=14).pack(side="left")
            var = tk.StringVar()
            ttk.Entry(row, textvariable=var).pack(side="left", fill="x", expand=True)
            self._personality_fields[key] = var
        row = ttk.Frame(form, style="StudioPanel.TFrame")
        row.pack(fill="x", pady=4)
        ttk.Label(row, text="Role", style="StudioMuted.TLabel", width=14).pack(side="left")
        self._personality_role = tk.StringVar()
        ttk.Combobox(row, textvariable=self._personality_role, values=NEWS_ROLES, state="readonly").pack(
            side="left", fill="x", expand=True
        )
        row = ttk.Frame(form, style="StudioPanel.TFrame")
        row.pack(fill="x", pady=4)
        ttk.Label(row, text="Voice", style="StudioMuted.TLabel", width=14).pack(side="left")
        self._personality_voice = tk.StringVar()
        self._personality_voice_combo = ttk.Combobox(row, textvariable=self._personality_voice, state="readonly")
        self._personality_voice_combo.pack(side="left", fill="x", expand=True)
        self._personality_enabled = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            form, text="Enabled", variable=self._personality_enabled, bootstyle="success-toolbutton"
        ).pack(anchor="w", pady=8)
        ttk.Button(form, text="Apply Personality Changes", bootstyle="primary", command=self._apply_personality).pack(
            anchor="w"
        )

    def _voice_labels(self) -> list[str]:
        return [""] + [
            voice.get("display_name", voice.get("id", ""))
            for voice in self._voices
            if voice.get("active", True)
        ]

    def _voice_id_for_label(self, label: str) -> str:
        for voice in self._voices:
            if voice.get("display_name", voice.get("id", "")) == label:
                return voice.get("id", "")
        return label

    def _voice_label_for_id(self, voice_id: str) -> str:
        for voice in self._voices:
            if voice.get("id") == voice_id:
                return voice.get("display_name", voice.get("id", ""))
        return voice_id

    def _refresh_personalities(self) -> None:
        self._personalities_tree.delete(*self._personalities_tree.get_children())
        self._personality_voice_combo.configure(values=self._voice_labels())
        for personality in self._bundle["personalities"]["personalities"]:
            self._personalities_tree.insert(
                "",
                "end",
                iid=personality["id"],
                values=(
                    personality.get("name", ""),
                    personality.get("role", ""),
                    "Yes" if personality.get("enabled") else "No",
                ),
            )

    def _on_personality_select(self, _event=None) -> None:
        selection = self._personalities_tree.selection()
        if not selection:
            return
        self._selected_personality_id = selection[0]
        personality = next(
            item for item in self._bundle["personalities"]["personalities"] if item["id"] == self._selected_personality_id
        )
        self._personality_fields["name"].set(personality.get("name", ""))
        self._personality_fields["notes"].set(personality.get("notes", ""))
        self._personality_role.set(personality.get("role", "anchor"))
        self._personality_voice.set(self._voice_label_for_id(personality.get("voice_id", "")))
        self._personality_enabled.set(personality.get("enabled", True))

    def _apply_personality(self) -> None:
        if not self._selected_personality_id:
            return
        for personality in self._bundle["personalities"]["personalities"]:
            if personality["id"] == self._selected_personality_id:
                personality["name"] = self._personality_fields["name"].get().strip()
                personality["notes"] = self._personality_fields["notes"].get().strip()
                personality["role"] = self._personality_role.get()
                personality["voice_id"] = self._voice_id_for_label(self._personality_voice.get())
                personality["enabled"] = self._personality_enabled.get()
                break
        self._refresh_personalities()
        self.set_status("Personality updated")

    def _add_personality(self) -> None:
        from app.core.news_content_model import _new_id

        self._bundle["personalities"]["personalities"].append(
            {
                "id": _new_id("np"),
                "name": "New Personality",
                "role": "anchor",
                "voice_id": "",
                "enabled": True,
                "notes": "",
            }
        )
        self._refresh_personalities()
        self.set_status("Personality added")

    def _delete_personality(self) -> None:
        if not self._selected_personality_id:
            return
        if Messagebox.yesno("Delete this personality?", "Delete Personality") != "Yes":
            return
        self._bundle["personalities"]["personalities"] = [
            item for item in self._bundle["personalities"]["personalities"] if item["id"] != self._selected_personality_id
        ]
        self._selected_personality_id = None
        self._refresh_personalities()
        self.set_status("Personality deleted")

    def _build_categories_tab(self) -> None:
        tab = ttk.Frame(self._notebook, style="Studio.TFrame", padding=12)
        self._notebook.add(tab, text="News Categories")
        panes = ttk.Panedwindow(tab, orient="horizontal", bootstyle="secondary")
        panes.pack(fill="both", expand=True)
        list_panel = ttk.Labelframe(panes, text="Categories", style="StudioCard.TLabelframe", padding=8)
        panes.add(list_panel, weight=1)
        self._categories_tree = ttk.Treeview(
            list_panel,
            columns=("name", "enabled", "priority"),
            show="headings",
            bootstyle="info",
            height=14,
        )
        for col, heading in (("name", "Category"), ("enabled", "Enabled"), ("priority", "Priority")):
            self._categories_tree.heading(col, text=heading)
        self._categories_tree.pack(fill="both", expand=True)
        self._categories_tree.bind("<<TreeviewSelect>>", self._on_category_select)

        form = ttk.Labelframe(panes, text="Category Details", style="StudioCard.TLabelframe", padding=12)
        panes.add(form, weight=2)
        self._category_name = tk.StringVar()
        row = ttk.Frame(form, style="StudioPanel.TFrame")
        row.pack(fill="x", pady=4)
        ttk.Label(row, text="Name", style="StudioMuted.TLabel", width=14).pack(side="left")
        ttk.Entry(row, textvariable=self._category_name).pack(side="left", fill="x", expand=True)
        self._category_enabled = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            form, text="Enabled", variable=self._category_enabled, bootstyle="success-toolbutton"
        ).pack(anchor="w", pady=8)
        ttk.Button(form, text="Apply Category Changes", bootstyle="primary", command=self._apply_category).pack(anchor="w")

    def _refresh_categories(self) -> None:
        self._categories_tree.delete(*self._categories_tree.get_children())
        for category in self._bundle["categories"]["categories"]:
            self._categories_tree.insert(
                "",
                "end",
                iid=category["id"],
                values=(category.get("name", ""), "Yes" if category.get("enabled") else "No", category.get("priority", "")),
            )

    def _on_category_select(self, _event=None) -> None:
        selection = self._categories_tree.selection()
        if not selection:
            return
        self._selected_category_id = selection[0]
        category = next(item for item in self._bundle["categories"]["categories"] if item["id"] == self._selected_category_id)
        self._category_name.set(category.get("name", ""))
        self._category_enabled.set(category.get("enabled", True))

    def _apply_category(self) -> None:
        if not self._selected_category_id:
            return
        for category in self._bundle["categories"]["categories"]:
            if category["id"] == self._selected_category_id:
                category["name"] = self._category_name.get().strip()
                category["enabled"] = self._category_enabled.get()
                break
        self._refresh_categories()
        self.set_status("Category updated")

    def _build_rss_tab(self) -> None:
        tab = ttk.Frame(self._notebook, style="Studio.TFrame", padding=12)
        self._notebook.add(tab, text="RSS Sources")
        toolbar = ttk.Frame(tab, style="Studio.TFrame")
        toolbar.pack(fill="x", pady=(0, 8))
        ttk.Button(toolbar, text="Add Feed", bootstyle="success", command=self._add_rss_source).pack(side="left")
        ttk.Button(toolbar, text="Delete Feed", bootstyle="danger", command=self._delete_rss_source).pack(side="left", padx=8)
        ttk.Button(toolbar, text="Test Feed", bootstyle="info", command=self._test_rss_source).pack(side="left")

        panes = ttk.Panedwindow(tab, orient="horizontal", bootstyle="secondary")
        panes.pack(fill="both", expand=True)
        list_panel = ttk.Labelframe(panes, text="Feeds", style="StudioCard.TLabelframe", padding=8)
        panes.add(list_panel, weight=1)
        self._rss_tree = ttk.Treeview(
            list_panel,
            columns=("name", "enabled", "status"),
            show="headings",
            bootstyle="info",
            height=14,
        )
        for col, heading in (("name", "Name"), ("enabled", "Enabled"), ("status", "Last Test")):
            self._rss_tree.heading(col, text=heading)
        self._rss_tree.pack(fill="both", expand=True)
        self._rss_tree.bind("<<TreeviewSelect>>", self._on_rss_select)

        form = ttk.Labelframe(panes, text="Feed Details", style="StudioCard.TLabelframe", padding=12)
        panes.add(form, weight=2)
        self._rss_fields: dict[str, tk.Variable] = {}
        for key, label in (("name", "Name"), ("url", "Feed URL")):
            row = ttk.Frame(form, style="StudioPanel.TFrame")
            row.pack(fill="x", pady=4)
            ttk.Label(row, text=label, style="StudioMuted.TLabel", width=16).pack(side="left")
            var = tk.StringVar()
            ttk.Entry(row, textvariable=var).pack(side="left", fill="x", expand=True)
            self._rss_fields[key] = var
        row = ttk.Frame(form, style="StudioPanel.TFrame")
        row.pack(fill="x", pady=4)
        ttk.Label(row, text="Category", style="StudioMuted.TLabel", width=16).pack(side="left")
        self._rss_category = tk.StringVar()
        self._rss_category_combo = ttk.Combobox(row, textvariable=self._rss_category, state="readonly")
        self._rss_category_combo.pack(side="left", fill="x", expand=True)
        self._rss_enabled = tk.BooleanVar(value=True)
        ttk.Checkbutton(form, text="Enabled", variable=self._rss_enabled, bootstyle="success-toolbutton").pack(
            anchor="w", pady=8
        )
        self._rss_last_update = ttk.Label(form, text="", style="StudioMuted.TLabel", wraplength=420, justify="left")
        self._rss_last_update.pack(anchor="w", pady=(0, 8))
        ttk.Button(form, text="Apply Feed Changes", bootstyle="primary", command=self._apply_rss_source).pack(anchor="w")

    def _category_labels(self) -> list[str]:
        return [item["name"] for item in self._bundle["categories"]["categories"]]

    def _category_id_for_name(self, name: str) -> str:
        for item in self._bundle["categories"]["categories"]:
            if item["name"] == name:
                return item["id"]
        return ""

    def _category_name_for_id(self, category_id: str) -> str:
        for item in self._bundle["categories"]["categories"]:
            if item["id"] == category_id:
                return item["name"]
        return ""

    def _refresh_rss_sources(self) -> None:
        self._rss_tree.delete(*self._rss_tree.get_children())
        self._rss_category_combo.configure(values=self._category_labels())
        for source in self._bundle["rss_sources"]["sources"]:
            self._rss_tree.insert(
                "",
                "end",
                iid=source["id"],
                values=(
                    source.get("name", ""),
                    "Yes" if source.get("enabled") else "No",
                    source.get("last_test_status", "") or "—",
                ),
            )

    def _on_rss_select(self, _event=None) -> None:
        selection = self._rss_tree.selection()
        if not selection:
            return
        self._selected_source_id = selection[0]
        source = next(item for item in self._bundle["rss_sources"]["sources"] if item["id"] == self._selected_source_id)
        self._rss_fields["name"].set(source.get("name", ""))
        self._rss_fields["url"].set(source.get("url", ""))
        self._rss_category.set(self._category_name_for_id(source.get("category_id", "")))
        self._rss_enabled.set(source.get("enabled", True))
        self._rss_last_update.configure(
            text=(
                f"Last successful update: {source.get('last_successful_update') or '—'}\n"
                f"Last test: {source.get('last_test_message') or '—'}"
            )
        )

    def _apply_rss_source(self) -> None:
        if not self._selected_source_id:
            return
        for source in self._bundle["rss_sources"]["sources"]:
            if source["id"] == self._selected_source_id:
                source["name"] = self._rss_fields["name"].get().strip()
                source["url"] = self._rss_fields["url"].get().strip()
                source["category_id"] = self._category_id_for_name(self._rss_category.get())
                source["enabled"] = self._rss_enabled.get()
                source["duplicate_key"] = source["url"].strip().lower()
                break
        self._refresh_rss_sources()
        self.set_status("RSS feed updated")

    def _add_rss_source(self) -> None:
        from app.core.news_content_model import _new_id

        self._bundle["rss_sources"]["sources"].append(
            {
                "id": _new_id("rss"),
                "name": "New Feed",
                "url": "",
                "enabled": True,
                "category_id": "",
                "last_successful_update": "",
                "last_test_status": "",
                "last_test_message": "",
                "duplicate_key": "",
            }
        )
        self._refresh_rss_sources()
        self.set_status("RSS feed added")

    def _delete_rss_source(self) -> None:
        if not self._selected_source_id:
            return
        if Messagebox.yesno("Delete this feed?", "Delete Feed") != "Yes":
            return
        self._bundle["rss_sources"]["sources"] = [
            item for item in self._bundle["rss_sources"]["sources"] if item["id"] != self._selected_source_id
        ]
        self._selected_source_id = None
        self._refresh_rss_sources()
        self.set_status("RSS feed deleted")

    def _test_rss_source(self) -> None:
        if not self._selected_source_id:
            return
        source = next(item for item in self._bundle["rss_sources"]["sources"] if item["id"] == self._selected_source_id)
        url = self._rss_fields["url"].get().strip() or source.get("url", "")

        def work() -> tuple[str, str]:
            return test_rss_feed(url)

        def complete(result: tuple[str, str]) -> None:
            status, message = result
            source["last_test_status"] = status
            source["last_test_message"] = message
            if status == "ok":
                source["last_successful_update"] = datetime.now().strftime("%Y-%m-%d %I:%M %p")
            self._bundle["feed_reliability"]["feeds"][source["id"]] = {
                "status": status,
                "message": message,
                "tested_at": datetime.now().isoformat(timespec="seconds"),
            }
            self._refresh_rss_sources()
            self._on_rss_select()
            self.set_status(message)

        self.set_status("Testing RSS feed…")
        run_in_background(self, work, complete, on_error=lambda err: self._show_error_dialog("Test Feed", str(err)))

    def _build_schedule_tab(self) -> None:
        tab = ttk.Frame(self._notebook, style="Studio.TFrame", padding=12)
        self._notebook.add(tab, text="News Schedule")
        toolbar = ttk.Frame(tab, style="Studio.TFrame")
        toolbar.pack(fill="x", pady=(0, 8))
        ttk.Button(toolbar, text="Add Holiday Override", bootstyle="warning", command=self._add_override).pack(side="left")

        panes = ttk.Panedwindow(tab, orient="horizontal", bootstyle="secondary")
        panes.pack(fill="both", expand=True)
        list_panel = ttk.Labelframe(panes, text="Schedule Slots", style="StudioCard.TLabelframe", padding=8)
        panes.add(list_panel, weight=1)
        self._schedule_tree = ttk.Treeview(
            list_panel,
            columns=("name", "time", "enabled"),
            show="headings",
            bootstyle="info",
            height=10,
        )
        for col, heading in (("name", "Slot"), ("time", "Time"), ("enabled", "Enabled")):
            self._schedule_tree.heading(col, text=heading)
        self._schedule_tree.pack(fill="both", expand=True)
        self._schedule_tree.bind("<<TreeviewSelect>>", self._on_slot_select)

        form = ttk.Labelframe(panes, text="Slot Details", style="StudioCard.TLabelframe", padding=12)
        panes.add(form, weight=2)
        self._slot_fields: dict[str, tk.Variable] = {}
        for key, label in (("name", "Name"), ("time", "Time"), ("notes", "Notes")):
            row = ttk.Frame(form, style="StudioPanel.TFrame")
            row.pack(fill="x", pady=4)
            ttk.Label(row, text=label, style="StudioMuted.TLabel", width=14).pack(side="left")
            var = tk.StringVar()
            ttk.Entry(row, textvariable=var).pack(side="left", fill="x", expand=True)
            self._slot_fields[key] = var
        row = ttk.Frame(form, style="StudioPanel.TFrame")
        row.pack(fill="x", pady=4)
        ttk.Label(row, text="Days", style="StudioMuted.TLabel", width=14).pack(side="left")
        self._slot_days = tk.StringVar()
        ttk.Entry(row, textvariable=self._slot_days).pack(side="left", fill="x", expand=True)
        self._slot_enabled = tk.BooleanVar(value=True)
        ttk.Checkbutton(form, text="Enabled", variable=self._slot_enabled, bootstyle="success-toolbutton").pack(
            anchor="w", pady=8
        )
        ttk.Button(form, text="Apply Schedule Changes", bootstyle="primary", command=self._apply_slot).pack(anchor="w")

        overrides = ttk.Labelframe(tab, text="Temporary & Holiday Overrides", style="StudioCard.TLabelframe", padding=12)
        overrides.pack(fill="x", pady=(12, 0))
        self._overrides_text = ScrolledText(
            overrides, height=6, autohide=True, bootstyle="secondary", state="disabled", wrap="word"
        )
        self._overrides_text.pack(fill="both", expand=True)

    def _refresh_schedule(self) -> None:
        self._schedule_tree.delete(*self._schedule_tree.get_children())
        for slot in self._bundle["schedule"]["slots"]:
            self._schedule_tree.insert(
                "",
                "end",
                iid=slot["id"],
                values=(slot.get("name", ""), slot.get("time", ""), "Yes" if slot.get("enabled") else "No"),
            )
        lines = []
        for override in self._bundle["schedule"]["overrides"]:
            lines.append(
                f"{override.get('override_type', 'temporary').title()} · "
                f"{override.get('date', '')} · {override.get('slot_type', '')} · "
                f"{override.get('time', '')} · {override.get('notes', '')}"
            )
        self._set_scroll_text(self._overrides_text, "\n".join(lines) if lines else "No overrides configured.")

    def _on_slot_select(self, _event=None) -> None:
        selection = self._schedule_tree.selection()
        if not selection:
            return
        self._selected_slot_id = selection[0]
        slot = next(item for item in self._bundle["schedule"]["slots"] if item["id"] == self._selected_slot_id)
        self._slot_fields["name"].set(slot.get("name", ""))
        self._slot_fields["time"].set(slot.get("time", ""))
        self._slot_fields["notes"].set(slot.get("notes", ""))
        self._slot_days.set(", ".join(slot.get("days", [])))
        self._slot_enabled.set(slot.get("enabled", True))

    def _apply_slot(self) -> None:
        if not self._selected_slot_id:
            return
        days = [part.strip().lower() for part in self._slot_days.get().split(",") if part.strip()]
        for slot in self._bundle["schedule"]["slots"]:
            if slot["id"] == self._selected_slot_id:
                slot["name"] = self._slot_fields["name"].get().strip()
                slot["time"] = self._slot_fields["time"].get().strip()
                slot["notes"] = self._slot_fields["notes"].get().strip()
                slot["days"] = days or list(DAYS)
                slot["enabled"] = self._slot_enabled.get()
                break
        self._refresh_schedule()
        self._refresh_overview()
        self.set_status("Schedule updated")

    def _add_override(self) -> None:
        from app.core.news_content_model import _new_id

        self._bundle["schedule"]["overrides"].append(
            {
                "id": _new_id("ovr"),
                "override_type": "holiday",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "slot_type": "morning",
                "time": "",
                "enabled": True,
                "notes": "Holiday override",
            }
        )
        self._refresh_schedule()
        self.set_status("Holiday override added")

    def _build_script_rules_tab(self) -> None:
        tab = ttk.Frame(self._notebook, style="Studio.TFrame", padding=12)
        self._notebook.add(tab, text="Script Rules")
        form = ttk.Labelframe(tab, text="Script Rules", style="StudioCard.TLabelframe", padding=16)
        form.pack(fill="both", expand=True)
        self._script_fields: dict[str, tk.Variable] = {}
        specs = (
            ("maximum_stories", "Maximum Stories"),
            ("opening", "Opening"),
            ("closing", "Closing"),
            ("pause_sound_between_stories", "Pause Sound Between Stories"),
            ("news_first_personality_rules", "News-First Personality Rules"),
            ("stale_hours_warning", "Stale News Warning (hours)"),
        )
        for key, label in specs:
            row = ttk.Frame(form, style="StudioPanel.TFrame")
            row.pack(fill="x", pady=4)
            ttk.Label(row, text=label, style="StudioMuted.TLabel", width=28).pack(side="left")
            var = tk.StringVar()
            ttk.Entry(row, textvariable=var).pack(side="left", fill="x", expand=True)
            self._script_fields[key] = var
        row = ttk.Frame(form, style="StudioPanel.TFrame")
        row.pack(fill="x", pady=4)
        ttk.Label(row, text="Story Order", style="StudioMuted.TLabel", width=28).pack(side="left")
        self._story_order = tk.StringVar()
        ttk.Entry(row, textvariable=self._story_order).pack(side="left", fill="x", expand=True)
        self._handoffs = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            form, text="Personality handoffs", variable=self._handoffs, bootstyle="success-toolbutton"
        ).pack(anchor="w", pady=8)
        ttk.Button(form, text="Apply Script Rules", bootstyle="primary", command=self._apply_script_rules).pack(anchor="w")

    def _refresh_script_rules(self) -> None:
        rules = self._bundle["script_rules"]
        for key, var in self._script_fields.items():
            var.set(str(rules.get(key, "")))
        self._story_order.set(", ".join(rules.get("story_order", [])))
        self._handoffs.set(rules.get("personality_handoffs", True))

    def _apply_script_rules(self) -> None:
        rules = self._bundle["script_rules"]
        for key, var in self._script_fields.items():
            value = var.get().strip()
            if key in {"maximum_stories", "stale_hours_warning"}:
                rules[key] = int(value) if value.isdigit() else rules.get(key, 0)
            else:
                rules[key] = value
        rules["story_order"] = [part.strip() for part in self._story_order.get().split(",") if part.strip()]
        rules["personality_handoffs"] = self._handoffs.get()
        self.set_status("Script rules updated")

    def _build_voice_tab(self) -> None:
        tab = ttk.Frame(self._notebook, style="Studio.TFrame", padding=12)
        self._notebook.add(tab, text="Voice Settings")
        form = ttk.Labelframe(tab, text="Voicebox Settings", style="StudioCard.TLabelframe", padding=16)
        form.pack(fill="x")
        self._voice_fields: dict[str, tk.Variable] = {}
        for key, label in (("voicebox_id", "Voicebox ID"), ("voice_volume", "Voice Volume")):
            row = ttk.Frame(form, style="StudioPanel.TFrame")
            row.pack(fill="x", pady=4)
            ttk.Label(row, text=label, style="StudioMuted.TLabel", width=22).pack(side="left")
            var = tk.StringVar()
            ttk.Entry(row, textvariable=var).pack(side="left", fill="x", expand=True)
            self._voice_fields[key] = var
        row = ttk.Frame(form, style="StudioPanel.TFrame")
        row.pack(fill="x", pady=4)
        ttk.Label(row, text="Speaking Style", style="StudioMuted.TLabel", width=22).pack(side="left")
        self._speaking_style = tk.StringVar()
        ttk.Combobox(row, textvariable=self._speaking_style, values=SPEAKING_STYLES, state="readonly").pack(
            side="left", fill="x", expand=True
        )
        row = ttk.Frame(form, style="StudioPanel.TFrame")
        row.pack(fill="x", pady=4)
        ttk.Label(row, text="Pronunciation Dictionary", style="StudioMuted.TLabel", width=22).pack(side="left", anchor="n")
        self._pronunciation_text = ScrolledText(row, height=6, autohide=True, bootstyle="secondary", wrap="word")
        self._pronunciation_text.pack(side="left", fill="x", expand=True)
        buttons = ttk.Frame(form, style="StudioPanel.TFrame")
        buttons.pack(fill="x", pady=(12, 0))
        ttk.Button(buttons, text="Save Voice Settings", bootstyle="primary", command=self._apply_voice_settings).pack(
            side="left"
        )
        ttk.Button(buttons, text="Test Voice", bootstyle="info", command=self._test_voice).pack(side="left", padx=8)

    def _refresh_voice_settings(self) -> None:
        settings = self._bundle["voice_settings"]
        self._voice_fields["voicebox_id"].set(settings.get("voicebox_id", ""))
        self._voice_fields["voice_volume"].set(str(settings.get("voice_volume", 100)))
        self._speaking_style.set(settings.get("speaking_style", "conversational"))
        dictionary = settings.get("pronunciation_dictionary", [])
        lines = []
        for entry in dictionary:
            if isinstance(entry, dict):
                lines.append(f"{entry.get('word', '')} = {entry.get('pronunciation', '')}")
            else:
                lines.append(str(entry))
        self._pronunciation_text.text.configure(state="normal")
        self._pronunciation_text.delete("1.0", "end")
        self._pronunciation_text.insert("end", "\n".join(lines))
        self._pronunciation_text.text.configure(state="normal")

    def _apply_voice_settings(self) -> None:
        settings = self._bundle["voice_settings"]
        settings["voicebox_id"] = self._voice_fields["voicebox_id"].get().strip()
        volume = self._voice_fields["voice_volume"].get().strip()
        settings["voice_volume"] = int(volume) if volume.isdigit() else 100
        settings["speaking_style"] = self._speaking_style.get()
        dictionary = []
        for line in self._pronunciation_text.get("1.0", "end").splitlines():
            if "=" in line:
                word, pronunciation = line.split("=", 1)
                dictionary.append({"word": word.strip(), "pronunciation": pronunciation.strip()})
        settings["pronunciation_dictionary"] = dictionary
        self.set_status("Voice settings updated")

    def _test_voice(self) -> None:
        voicebox = self._voice_fields["voicebox_id"].get().strip()
        if not voicebox:
            Messagebox.show_warning("Set a Voicebox ID before testing.", "Test Voice")
            return
        Messagebox.show_info(
            f"Development voice test queued for Voicebox ID: {voicebox}\n"
            "This preview does not publish to the live News system.",
            "Test Voice",
        )
        self.set_status("Voice test preview queued (development only)")

    def _build_output_tab(self) -> None:
        tab = ttk.Frame(self._notebook, style="Studio.TFrame", padding=12)
        self._notebook.add(tab, text="Output")
        toolbar = ttk.Frame(tab, style="Studio.TFrame")
        toolbar.pack(fill="x", pady=(0, 8))
        ttk.Button(
            toolbar, text="Generate Dev Script", bootstyle="success", command=self._generate_dev_script
        ).pack(side="left")
        ttk.Button(toolbar, text="Open Output Folder", bootstyle="secondary", command=self._open_output_folder).pack(
            side="left", padx=8
        )
        ttk.Label(
            tab,
            text="Development generation only — previews are saved under StationData/News/dev_output and do not replace live news output.",
            style="StudioMuted.TLabel",
            wraplength=900,
            justify="left",
        ).pack(anchor="w", pady=(0, 8))

        panes = ttk.Panedwindow(tab, orient="horizontal", bootstyle="secondary")
        panes.pack(fill="both", expand=True)
        script_card = ttk.Labelframe(panes, text="Generated Script Preview", style="StudioCard.TLabelframe", padding=12)
        panes.add(script_card, weight=1)
        self._script_preview_text = ScrolledText(
            script_card, height=14, autohide=True, bootstyle="secondary", state="disabled", wrap="word"
        )
        self._script_preview_text.pack(fill="both", expand=True)

        files_card = ttk.Labelframe(panes, text="Audio / Output Files", style="StudioCard.TLabelframe", padding=12)
        panes.add(files_card, weight=1)
        self._output_list_text = ScrolledText(
            files_card, height=14, autohide=True, bootstyle="secondary", state="disabled", wrap="word"
        )
        self._output_list_text.pack(fill="both", expand=True)

    def _refresh_output(self) -> None:
        files = list_output_files(self.config_manager)
        self._set_scroll_text(self._output_list_text, "\n".join(files) if files else "No output files found.")

    def _generate_dev_script(self) -> None:
        path = generate_dev_script_preview(self._bundle, self.config_manager)
        content = Path(path).read_text(encoding="utf-8")
        self._set_scroll_text(self._script_preview_text, content)
        self._refresh_output()
        self.set_status(f"Development script saved: {path}")

    def _open_output_folder(self) -> None:
        try:
            open_folder(str(news_dev_output_dir(self.config_manager)))
            self.set_status("Opened development output folder.")
        except OSError as exc:
            self._show_error_dialog("Open Output Folder", str(exc))

    def _build_validation_tab(self) -> None:
        tab = ttk.Frame(self._notebook, style="Studio.TFrame", padding=12)
        self._notebook.add(tab, text="Validation")
        self._validation_text = ScrolledText(
            tab, height=20, autohide=True, bootstyle="secondary", state="disabled", wrap="word"
        )
        self._validation_text.pack(fill="both", expand=True)

    def _refresh_validation_tab(self, warnings: list[str]) -> None:
        if not warnings:
            text = "No validation warnings. News configuration looks good."
        else:
            text = "\n".join(f"• {warning}" for warning in warnings)
        self._set_scroll_text(self._validation_text, text)

    def _build_reports_tab(self) -> None:
        tab = ttk.Frame(self._notebook, style="Studio.TFrame", padding=12)
        self._notebook.add(tab, text="Reports")
        toolbar = ttk.Frame(tab, style="Studio.TFrame")
        toolbar.pack(fill="x", pady=(0, 8))
        self._report_var = tk.StringVar(value=REPORT_OPTIONS[0][1])
        self._report_labels = {label: key for key, label in REPORT_OPTIONS}
        ttk.Combobox(
            toolbar,
            textvariable=self._report_var,
            values=[label for _key, label in REPORT_OPTIONS],
            state="readonly",
            width=28,
        ).pack(side="left")
        ttk.Button(toolbar, text="Run Report", bootstyle="info", command=self._run_report).pack(side="left", padx=8)
        self._report_text = ScrolledText(
            tab, height=18, autohide=True, bootstyle="secondary", state="disabled", wrap="word"
        )
        self._report_text.pack(fill="both", expand=True)

    def _run_report(self) -> None:
        key = self._report_labels.get(self._report_var.get(), REPORT_OPTIONS[0][0])
        lines = build_report_lines(self._bundle, key)
        self._set_scroll_text(self._report_text, "\n".join(lines))
        self.set_status("Report generated")

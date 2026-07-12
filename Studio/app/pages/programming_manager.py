"""Programming Manager — station programming control center."""

from __future__ import annotations

import tkinter as tk
from copy import deepcopy
from typing import Any

import ttkbootstrap as ttk
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.scrolled import ScrolledFrame, ScrolledText

from app.core.background_tasks import run_in_background
from app.core.personality_model import display_label, normalize_personalities_data
from app.core.programming_model import (
    SHOW_CATEGORIES,
    ProgrammingDashboard,
    build_programming_dashboard,
    copy_day_events,
    copy_week_events,
    normalize_bundle,
    validate_programming,
)
from app.core.programming_storage import load_programming_bundle, save_programming_bundle
from app.core.schedule_model import DAYS, default_end_time, new_slot_id
from app.core.voice_model import normalize_voice_library_data
from app.pages.base_page import BasePage
from app.ui.theme import StudioTheme

DAY_LABELS = {day: day.title() for day in DAYS}


class ProgrammingManagerPage(BasePage):
    page_id = "programming"
    page_title = "Programming Manager"
    page_subtitle = "Plan shows, formats, clocks, and your weekly station schedule"
    page_help = (
        "Everything related to programming the station is managed here. "
        "Data is stored in your platform StationData folder and does not connect to RadioDJ yet."
    )

    def build(self) -> None:
        self._bundle = normalize_bundle({})
        self._personalities: list[dict[str, Any]] = []
        self._voices: list[dict[str, Any]] = []
        self._busy = False
        self._selected_show_id: str | None = None
        self._selected_event_id: str | None = None
        self._search_var = tk.StringVar()
        self._dashboard_labels: dict[str, ttk.Label] = {}
        self._validation_list: tk.Listbox | None = None

        toolbar = ttk.Frame(self._body, style="Studio.TFrame")
        toolbar.pack(fill="x", pady=(0, 12))
        ttk.Button(toolbar, text="Save Programming", style="StudioAction.TButton", bootstyle="primary", command=self._save).pack(
            side="right"
        )
        ttk.Button(toolbar, text="Validate", style="StudioAction.TButton", bootstyle="info", command=self._run_validation).pack(
            side="right", padx=8
        )
        ttk.Button(toolbar, text="Reload", bootstyle="secondary", command=self._load).pack(side="left")

        self._notebook = ttk.Notebook(self._body, bootstyle="primary")
        self._notebook.pack(fill="both", expand=True)
        self._build_dashboard_tab()
        self._build_daily_schedule_tab()
        self._build_shows_tab()
        self._build_formats_tab()
        self._build_personalities_tab()
        self._build_clocks_tab()
        self._build_scheduler_tab()
        self._build_events_tab()
        self._build_validation_tab()

    def on_show(self) -> None:
        self._load()

    def _load(self) -> None:
        self._personalities = normalize_personalities_data(
            self.config_manager.load("personalities", {"personalities": []})
        ).get("personalities", [])
        self._voices = normalize_voice_library_data(
            self.config_manager.load("voice_library", {"voices": []})
        ).get("voices", [])
        self._bundle = normalize_bundle(load_programming_bundle(self.config_manager))
        self._refresh_all_views()
        self.set_status("Programming data loaded")

    def _save(self) -> None:
        if self._busy:
            return
        self._busy = True
        payload = deepcopy(self._bundle)

        def work() -> None:
            save_programming_bundle(payload, self.config_manager)

        def complete(_: None) -> None:
            self._busy = False
            self.set_status("Programming data saved")

        def failed(error: Exception) -> None:
            self._busy = False
            self._show_error_dialog("Save Programming", str(error))

        self.set_status("Saving programming data…")
        run_in_background(self, work, lambda _: complete(None), on_error=failed)

    def _run_validation(self) -> None:
        warnings = validate_programming(self._bundle, self._personalities, self._voices)
        self._bundle["state"]["last_validated"] = __import__("datetime").datetime.now().strftime("%Y-%m-%d %I:%M %p")
        self._refresh_validation_tab(warnings)
        self._refresh_dashboard(warnings)
        self.set_status("Programming validation complete")

    def _refresh_all_views(self) -> None:
        warnings = validate_programming(self._bundle, self._personalities, self._voices)
        self._refresh_dashboard(warnings)
        self._refresh_daily_schedule()
        self._refresh_shows()
        self._refresh_formats()
        self._refresh_personalities_tab()
        self._refresh_clocks()
        self._refresh_scheduler()
        self._refresh_events()
        self._refresh_validation_tab(warnings)

    def _build_dashboard_tab(self) -> None:
        tab = ttk.Frame(self._notebook, style="Studio.TFrame", padding=12)
        self._notebook.add(tab, text="Dashboard")
        grid = ttk.Frame(tab, style="Studio.TFrame")
        grid.pack(fill="x")
        specs = (
            ("current_show", "Current Show"),
            ("next_show", "Next Show"),
            ("current_format", "Current Format"),
        )
        for index, (key, title) in enumerate(specs):
            card = ttk.Labelframe(grid, text=title, style="StudioCard.TLabelframe", padding=12)
            card.grid(row=0, column=index, sticky="nsew", padx=8, pady=8)
            label = ttk.Label(card, text="—", style="StudioMetric.TLabel", wraplength=260, justify="left")
            label.pack(anchor="w")
            self._dashboard_labels[key] = label
            grid.columnconfigure(index, weight=1)

        lower = ttk.Frame(tab, style="Studio.TFrame")
        lower.pack(fill="both", expand=True, pady=(12, 0))
        for index, (key, title) in enumerate(
            (
                ("upcoming_changes", "Upcoming Changes"),
                ("validation_warnings", "Validation Warnings"),
            )
        ):
            card = ttk.Labelframe(lower, text=title, style="StudioCard.TLabelframe", padding=12)
            card.grid(row=0, column=index, sticky="nsew", padx=8, pady=8)
            text = ScrolledText(card, height=8, autohide=True, bootstyle="secondary", state="disabled", wrap="word")
            text.pack(fill="both", expand=True)
            self._dashboard_labels[key] = text
            lower.columnconfigure(index, weight=1)

    def _refresh_dashboard(self, warnings: list[str]) -> None:
        dashboard = build_programming_dashboard(self._bundle, warnings)
        self._dashboard_labels["current_show"].configure(text=dashboard.current_show)
        self._dashboard_labels["next_show"].configure(text=dashboard.next_show)
        self._dashboard_labels["current_format"].configure(text=dashboard.current_format)
        self._set_scroll_text(self._dashboard_labels["upcoming_changes"], "\n".join(dashboard.upcoming_changes))
        self._set_scroll_text(self._dashboard_labels["validation_warnings"], "\n".join(dashboard.validation_warnings))

    def _build_daily_schedule_tab(self) -> None:
        tab = ttk.Frame(self._notebook, style="Studio.TFrame", padding=12)
        self._notebook.add(tab, text="Daily Schedule")
        panes = ttk.Panedwindow(tab, orient="horizontal", bootstyle="secondary")
        panes.pack(fill="both", expand=True)

        calendar = ttk.Labelframe(panes, text="Calendar View", style="StudioCard.TLabelframe", padding=12)
        panes.add(calendar, weight=1)
        self._calendar_text = ScrolledText(calendar, height=16, autohide=True, bootstyle="secondary", state="disabled", wrap="word")
        self._calendar_text.pack(fill="both", expand=True)

        timeline = ttk.Labelframe(panes, text="Timeline View (Today)", style="StudioCard.TLabelframe", padding=12)
        panes.add(timeline, weight=1)
        self._timeline_text = ScrolledText(timeline, height=16, autohide=True, bootstyle="secondary", state="disabled", wrap="word")
        self._timeline_text.pack(fill="both", expand=True)

        status = ttk.Labelframe(tab, text="Programming Status", style="StudioCard.TLabelframe", padding=12)
        status.pack(fill="x", pady=(12, 0))
        self._current_programming_label = ttk.Label(status, text="", style="StudioCard.TLabel", wraplength=900, justify="left")
        self._current_programming_label.pack(anchor="w")
        self._upcoming_programming_label = ttk.Label(status, text="", style="StudioMuted.TLabel", wraplength=900, justify="left")
        self._upcoming_programming_label.pack(anchor="w", pady=(6, 0))

    def _refresh_daily_schedule(self) -> None:
        warnings = validate_programming(self._bundle, self._personalities, self._voices)
        dashboard = build_programming_dashboard(self._bundle, warnings)
        calendar_lines = []
        for day in DAYS:
            day_events = [
                event
                for event in self._bundle["events"]["events"]
                if event.get("day", "").lower() == day and event.get("enabled", True)
            ]
            day_events.sort(key=lambda item: item.get("start_time", ""))
            calendar_lines.append(f"{DAY_LABELS[day]}")
            if day_events:
                for event in day_events:
                    calendar_lines.append(
                        f"  {event.get('start_time')}–{event.get('end_time')} · "
                        f"{event.get('show_name', 'Event')} · {event.get('music_format', '')}"
                    )
            else:
                calendar_lines.append("  No events scheduled")
            calendar_lines.append("")
        self._set_scroll_text(self._calendar_text, "\n".join(calendar_lines))

        today = DAYS[__import__("datetime").datetime.now().weekday()]
        today_events = [
            event
            for event in self._bundle["events"]["events"]
            if event.get("day", "").lower() == today and event.get("enabled", True)
        ]
        today_events.sort(key=lambda item: item.get("start_time", ""))
        timeline_lines = [f"Today — {DAY_LABELS[today]}"]
        for event in today_events:
            timeline_lines.append(
                f"{event.get('start_time')} ── {event.get('show_name', 'Event')} ({event.get('music_format', 'Format')})"
            )
        if len(timeline_lines) == 1:
            timeline_lines.append("No programming scheduled for today.")
        self._set_scroll_text(self._timeline_text, "\n".join(timeline_lines))
        self._current_programming_label.configure(text="Current: " + " · ".join(dashboard.current_programming))
        self._upcoming_programming_label.configure(text="Upcoming: " + " · ".join(dashboard.upcoming_programming[:3]))

    def _build_shows_tab(self) -> None:
        tab = ttk.Frame(self._notebook, style="Studio.TFrame", padding=12)
        self._notebook.add(tab, text="Shows")
        toolbar = ttk.Frame(tab, style="Studio.TFrame")
        toolbar.pack(fill="x", pady=(0, 8))
        ttk.Button(toolbar, text="Add Show", bootstyle="success", command=self._add_show).pack(side="left")
        ttk.Button(toolbar, text="Delete Show", bootstyle="danger", command=self._delete_show).pack(side="left", padx=8)

        panes = ttk.Panedwindow(tab, orient="horizontal", bootstyle="secondary")
        panes.pack(fill="both", expand=True)
        list_panel = ttk.Labelframe(panes, text="Shows", style="StudioCard.TLabelframe", padding=8)
        panes.add(list_panel, weight=1)
        self._shows_tree = ttk.Treeview(
            list_panel,
            columns=("name", "category", "enabled"),
            show="headings",
            bootstyle="info",
            height=14,
        )
        self._shows_tree.heading("name", text="Show")
        self._shows_tree.heading("category", text="Category")
        self._shows_tree.heading("enabled", text="Active")
        self._shows_tree.column("name", width=180)
        self._shows_tree.pack(fill="both", expand=True)
        self._shows_tree.bind("<<TreeviewSelect>>", self._on_show_select)

        form = ttk.Labelframe(panes, text="Show Details", style="StudioCard.TLabelframe", padding=12)
        panes.add(form, weight=2)
        self._show_fields: dict[str, tk.Variable] = {}
        for key, label in (
            ("name", "Show Name"),
            ("category", "Category"),
            ("description", "Description"),
        ):
            row = ttk.Frame(form, style="StudioPanel.TFrame")
            row.pack(fill="x", pady=4)
            ttk.Label(row, text=label, style="StudioMuted.TLabel", width=16).pack(side="left")
            var = tk.StringVar()
            if key == "category":
                ttk.Combobox(row, textvariable=var, values=[label for _, label in SHOW_CATEGORIES], state="readonly").pack(
                    side="left", fill="x", expand=True
                )
            else:
                ttk.Entry(row, textvariable=var).pack(side="left", fill="x", expand=True)
            self._show_fields[key] = var
        self._show_enabled = tk.BooleanVar(value=True)
        ttk.Checkbutton(form, text="Active", variable=self._show_enabled, bootstyle="success-toolbutton").pack(anchor="w", pady=8)
        ttk.Button(form, text="Apply Show Changes", bootstyle="primary", command=self._apply_show).pack(anchor="w")

    def _refresh_shows(self) -> None:
        self._shows_tree.delete(*self._shows_tree.get_children())
        category_labels = {key: label for key, label in SHOW_CATEGORIES}
        for show in self._bundle["shows"]["shows"]:
            self._shows_tree.insert(
                "",
                "end",
                iid=show["id"],
                values=(show.get("name", ""), category_labels.get(show.get("category", ""), show.get("category", "")), "Yes" if show.get("enabled") else "No"),
            )

    def _on_show_select(self, _event=None) -> None:
        selection = self._shows_tree.selection()
        if not selection:
            return
        self._selected_show_id = selection[0]
        show = next(item for item in self._bundle["shows"]["shows"] if item["id"] == self._selected_show_id)
        category_labels = {label: key for key, label in SHOW_CATEGORIES}
        self._show_fields["name"].set(show.get("name", ""))
        self._show_fields["category"].set(
            next((label for key, label in SHOW_CATEGORIES if key == show.get("category")), "Specialty Shows")
        )
        self._show_fields["description"].set(show.get("description", ""))
        self._show_enabled.set(show.get("enabled", True))

    def _apply_show(self) -> None:
        if not self._selected_show_id:
            return
        category_labels = {label: key for key, label in SHOW_CATEGORIES}
        for show in self._bundle["shows"]["shows"]:
            if show["id"] == self._selected_show_id:
                show["name"] = self._show_fields["name"].get().strip()
                show["category"] = category_labels.get(self._show_fields["category"].get(), "specialty")
                show["description"] = self._show_fields["description"].get().strip()
                show["enabled"] = self._show_enabled.get()
                break
        self._refresh_shows()
        self.set_status("Show updated")

    def _add_show(self) -> None:
        show = {
            "id": new_slot_id().replace("slot", "show"),
            "name": "New Show",
            "category": "specialty",
            "description": "",
            "enabled": True,
            "default_format_id": "",
            "primary_personality_id": "",
            "backup_personality_id": "",
            "voice_id": "",
        }
        self._bundle["shows"]["shows"].append(show)
        self._refresh_shows()
        self.set_status("Show added")

    def _delete_show(self) -> None:
        if not self._selected_show_id:
            return
        if Messagebox.yesno("Delete this show?", "Delete Show") != "Yes":
            return
        self._bundle["shows"]["shows"] = [
            show for show in self._bundle["shows"]["shows"] if show["id"] != self._selected_show_id
        ]
        self._selected_show_id = None
        self._refresh_shows()
        self.set_status("Show deleted")

    def _build_formats_tab(self) -> None:
        tab = ttk.Frame(self._notebook, style="Studio.TFrame", padding=12)
        self._notebook.add(tab, text="Formats")
        self._formats_frame = ttk.Frame(tab, style="Studio.TFrame")
        self._formats_frame.pack(fill="both", expand=True)
        ttk.Button(tab, text="Add Format", bootstyle="success", command=self._add_format).pack(anchor="w", pady=(12, 0))

    def _refresh_formats(self) -> None:
        for child in self._formats_frame.winfo_children():
            child.destroy()
        for fmt in self._bundle["formats"]["formats"]:
            row = ttk.Frame(self._formats_frame, style="StudioPanel.TFrame")
            row.pack(fill="x", pady=4)
            enabled = tk.BooleanVar(value=fmt.get("enabled", True))
            ttk.Checkbutton(
                row,
                text=fmt.get("name", "Format"),
                variable=enabled,
                bootstyle="success-toolbutton",
                command=lambda f=fmt, v=enabled: self._toggle_format(f, v),
            ).pack(side="left")
            ttk.Label(row, text=fmt.get("description", ""), style="StudioMuted.TLabel").pack(side="left", padx=12)

    def _toggle_format(self, fmt: dict[str, Any], variable: tk.BooleanVar) -> None:
        fmt["enabled"] = variable.get()

    def _add_format(self) -> None:
        self._bundle["formats"]["formats"].append(
            {"id": new_slot_id().replace("slot", "fmt"), "name": "New Format", "enabled": True, "description": ""}
        )
        self._refresh_formats()

    def _build_personalities_tab(self) -> None:
        tab = ttk.Frame(self._notebook, style="Studio.TFrame", padding=12)
        self._notebook.add(tab, text="Personalities")
        self._assignments_frame = ScrolledFrame(tab, autohide=True, bootstyle="secondary")
        self._assignments_frame.pack(fill="both", expand=True)

    def _refresh_personalities_tab(self) -> None:
        for child in self._assignments_frame.container.winfo_children():
            child.destroy()
        personality_choices = [("", "—")] + [
            (item["id"], display_label(item)) for item in self._personalities if item.get("active", True)
        ]
        voice_choices = [("", "—")] + [
            (item["id"], item.get("display_name", item["id"])) for item in self._voices if item.get("active", True)
        ]
        for show in self._bundle["shows"]["shows"]:
            card = ttk.Labelframe(
                self._assignments_frame.container,
                text=show.get("name", "Show"),
                style="StudioCard.TLabelframe",
                padding=10,
            )
            card.pack(fill="x", padx=4, pady=6)
            personality_id_to_label = {item_id: label for item_id, label in personality_choices}
            voice_id_to_label = {item_id: label for item_id, label in voice_choices}
            primary = tk.StringVar(value=personality_id_to_label.get(show.get("primary_personality_id", ""), "—"))
            backup = tk.StringVar(value=personality_id_to_label.get(show.get("backup_personality_id", ""), "—"))
            voice = tk.StringVar(value=voice_id_to_label.get(show.get("voice_id", ""), "—"))
            for label, variable, choices in (
                ("Primary Host", primary, personality_choices),
                ("Backup Host", backup, personality_choices),
                ("Voice", voice, voice_choices),
            ):
                row = ttk.Frame(card, style="StudioPanel.TFrame")
                row.pack(fill="x", pady=3)
                ttk.Label(row, text=label, style="StudioMuted.TLabel", width=14).pack(side="left")
                ttk.Combobox(
                    row,
                    textvariable=variable,
                    values=[label for _, label in choices],
                    state="readonly",
                ).pack(side="left", fill="x", expand=True)
            ttk.Button(
                card,
                text="Save Assignment",
                bootstyle="secondary",
                command=lambda s=show, p=primary, b=backup, v=voice, pc=personality_choices, vc=voice_choices: self._save_assignment(
                    s, p, b, v, pc, vc
                ),
            ).pack(anchor="w", pady=(6, 0))

    def _save_assignment(
        self,
        show: dict[str, Any],
        primary: tk.StringVar,
        backup: tk.StringVar,
        voice: tk.StringVar,
        personality_choices: list[tuple[str, str]],
        voice_choices: list[tuple[str, str]],
    ) -> None:
        label_to_id = {label: item_id for item_id, label in personality_choices}
        voice_label_to_id = {label: item_id for item_id, label in voice_choices}
        show["primary_personality_id"] = label_to_id.get(primary.get(), "")
        show["backup_personality_id"] = label_to_id.get(backup.get(), "")
        show["voice_id"] = voice_label_to_id.get(voice.get(), "")
        self.set_status(f"Assignments saved for {show.get('name', 'show')}")

    def _build_clocks_tab(self) -> None:
        tab = ttk.Frame(self._notebook, style="Studio.TFrame", padding=12)
        self._notebook.add(tab, text="Clocks")
        self._clocks_frame = ttk.Frame(tab, style="Studio.TFrame")
        self._clocks_frame.pack(fill="both", expand=True)

    def _refresh_clocks(self) -> None:
        for child in self._clocks_frame.winfo_children():
            child.destroy()
        for clock in self._bundle["clocks"]["clocks"]:
            row = ttk.Frame(self._clocks_frame, style="StudioPanel.TFrame")
            row.pack(fill="x", pady=4)
            enabled = tk.BooleanVar(value=clock.get("enabled", True))
            ttk.Checkbutton(
                row,
                text=clock.get("name", "Clock"),
                variable=enabled,
                bootstyle="success-toolbutton",
                command=lambda c=clock, v=enabled: c.update({"enabled": v.get()}),
            ).pack(side="left")
            ttk.Label(row, text=clock.get("notes", ""), style="StudioMuted.TLabel").pack(side="left", padx=12)

    def _build_scheduler_tab(self) -> None:
        tab = ttk.Frame(self._notebook, style="Studio.TFrame", padding=12)
        self._notebook.add(tab, text="Scheduler")
        toolbar = ttk.Frame(tab, style="Studio.TFrame")
        toolbar.pack(fill="x", pady=(0, 8))
        ttk.Button(toolbar, text="Add Event", bootstyle="success", command=self._add_event).pack(side="left")
        ttk.Button(toolbar, text="Copy Day", bootstyle="secondary", command=self._copy_day).pack(side="left", padx=8)
        ttk.Button(toolbar, text="Copy Week", bootstyle="secondary", command=self._copy_week).pack(side="left")
        ttk.Button(toolbar, text="Add Holiday Override", bootstyle="secondary", command=self._add_override).pack(side="right")

        panes = ttk.Panedwindow(tab, orient="horizontal", bootstyle="secondary")
        panes.pack(fill="both", expand=True)
        palette = ttk.Labelframe(panes, text="Drag Host to Schedule", style="StudioCard.TLabelframe", padding=8)
        panes.add(palette, weight=1)
        ttk.Label(palette, text="Select a host, then click Add Event.", style="StudioMuted.TLabel", wraplength=180).pack(anchor="w")
        self._palette_list = tk.Listbox(palette, height=14, exportselection=False)
        self._palette_list.pack(fill="both", expand=True, pady=(8, 0))

        schedule = ttk.Labelframe(panes, text="Weekly Schedule", style="StudioCard.TLabelframe", padding=8)
        panes.add(schedule, weight=3)
        self._scheduler_tree = ttk.Treeview(
            schedule,
            columns=("day", "time", "show", "format", "enabled"),
            show="headings",
            bootstyle="info",
            height=14,
        )
        for col, title, width in (
            ("day", "Day", 90),
            ("time", "Time", 120),
            ("show", "Show", 160),
            ("format", "Format", 120),
            ("enabled", "Active", 60),
        ):
            self._scheduler_tree.heading(col, text=title)
            self._scheduler_tree.column(col, width=width)
        self._scheduler_tree.pack(fill="both", expand=True)
        self._scheduler_tree.bind("<<TreeviewSelect>>", self._on_event_select)

    def _refresh_scheduler(self) -> None:
        self._palette_list.delete(0, "end")
        for personality in self._personalities:
            if personality.get("active", True):
                self._palette_list.insert("end", display_label(personality))
        self._scheduler_tree.delete(*self._scheduler_tree.get_children())
        for event in sorted(
            self._bundle["events"]["events"],
            key=lambda item: (item.get("day", ""), item.get("start_time", "")),
        ):
            self._scheduler_tree.insert(
                "",
                "end",
                iid=event["id"],
                values=(
                    DAY_LABELS.get(event.get("day", ""), event.get("day", "")),
                    f"{event.get('start_time')}–{event.get('end_time')}",
                    event.get("show_name", ""),
                    event.get("music_format", ""),
                    "Yes" if event.get("enabled", True) else "No",
                ),
            )

    def _add_event(self) -> None:
        selection = self._palette_list.curselection()
        personality_id = ""
        if selection:
            label = self._palette_list.get(selection[0])
            for personality in self._personalities:
                if display_label(personality) == label:
                    personality_id = personality["id"]
                    break
        event = {
            "id": new_slot_id().replace("slot", "evt"),
            "show_id": "",
            "day": "monday",
            "start_time": "06:00",
            "end_time": default_end_time("06:00"),
            "format_id": "",
            "personality_id": personality_id,
            "show_name": "New Event",
            "music_format": "Classic Rock",
            "enabled": True,
            "notes": "",
        }
        self._bundle["events"]["events"].append(event)
        self._refresh_scheduler()
        self._refresh_daily_schedule()
        self.set_status("Event added — edit details in Events tab")

    def _copy_day(self) -> None:
        copied = copy_day_events(self._bundle["events"]["events"], "monday", "tuesday")
        self._bundle["events"]["events"] = copied
        self._refresh_scheduler()
        self.set_status("Copied Monday schedule to Tuesday")

    def _copy_week(self) -> None:
        self._bundle["events"]["events"] = copy_week_events(self._bundle["events"]["events"])
        self._refresh_scheduler()
        self.set_status("Week schedule copied")

    def _add_override(self) -> None:
        self._bundle["overrides"]["overrides"].append(
            {
                "id": new_slot_id().replace("slot", "ovr"),
                "override_type": "holiday",
                "label": "Holiday Override",
                "date": "",
                "day": "",
                "enabled": True,
                "notes": "",
                "events": [],
            }
        )
        self.set_status("Holiday override added")

    def _build_events_tab(self) -> None:
        tab = ttk.Frame(self._notebook, style="Studio.TFrame", padding=12)
        self._notebook.add(tab, text="Events")
        search_row = ttk.Frame(tab, style="Studio.TFrame")
        search_row.pack(fill="x", pady=(0, 8))
        ttk.Label(search_row, text="Search", style="StudioMuted.TLabel").pack(side="left")
        ttk.Entry(search_row, textvariable=self._search_var).pack(side="left", fill="x", expand=True, padx=8)
        self._search_var.trace_add("write", lambda *_: self._refresh_events())
        toolbar = ttk.Frame(tab, style="Studio.TFrame")
        toolbar.pack(fill="x", pady=(0, 8))
        ttk.Button(toolbar, text="Duplicate Event", bootstyle="secondary", command=self._duplicate_event).pack(side="left")
        ttk.Button(toolbar, text="Disable Event", bootstyle="secondary", command=self._disable_event).pack(side="left", padx=8)
        ttk.Button(toolbar, text="Delete Event", bootstyle="danger", command=self._delete_event).pack(side="left")

        self._events_tree = ttk.Treeview(
            tab,
            columns=("day", "time", "show", "format"),
            show="headings",
            bootstyle="info",
            height=12,
        )
        for col, title in (("day", "Day"), ("time", "Time"), ("show", "Show"), ("format", "Format")):
            self._events_tree.heading(col, text=title)
        self._events_tree.pack(fill="both", expand=True, pady=(0, 8))
        self._events_tree.bind("<<TreeviewSelect>>", self._on_event_select)

        form = ttk.Labelframe(tab, text="Edit Event", style="StudioCard.TLabelframe", padding=12)
        form.pack(fill="x")
        self._event_fields: dict[str, tk.Variable] = {}
        for key, label in (
            ("show_name", "Show Name"),
            ("day", "Day"),
            ("start_time", "Start Time"),
            ("end_time", "End Time"),
            ("music_format", "Format"),
            ("notes", "Notes"),
        ):
            row = ttk.Frame(form, style="StudioPanel.TFrame")
            row.pack(fill="x", pady=3)
            ttk.Label(row, text=label, style="StudioMuted.TLabel", width=12).pack(side="left")
            var = tk.StringVar()
            if key == "day":
                ttk.Combobox(row, textvariable=var, values=[DAY_LABELS[day] for day in DAYS], state="readonly").pack(
                    side="left", fill="x", expand=True
                )
            else:
                ttk.Entry(row, textvariable=var).pack(side="left", fill="x", expand=True)
            self._event_fields[key] = var
        self._event_enabled = tk.BooleanVar(value=True)
        ttk.Checkbutton(form, text="Enabled", variable=self._event_enabled, bootstyle="success-toolbutton").pack(anchor="w", pady=6)
        ttk.Button(form, text="Apply Event Changes", bootstyle="primary", command=self._apply_event).pack(anchor="w")

    def _refresh_events(self) -> None:
        query = self._search_var.get().strip().lower()
        self._events_tree.delete(*self._events_tree.get_children())
        for event in self._bundle["events"]["events"]:
            haystack = " ".join(
                [
                    event.get("show_name", ""),
                    event.get("music_format", ""),
                    event.get("day", ""),
                    event.get("notes", ""),
                ]
            ).lower()
            if query and query not in haystack:
                continue
            self._events_tree.insert(
                "",
                "end",
                iid=event["id"],
                values=(
                    DAY_LABELS.get(event.get("day", ""), event.get("day", "")),
                    f"{event.get('start_time')}–{event.get('end_time')}",
                    event.get("show_name", ""),
                    event.get("music_format", ""),
                ),
            )

    def _apply_event(self) -> None:
        if not self._selected_event_id:
            return
        day_labels = {label.lower(): key for key, label in DAY_LABELS.items()}
        for event in self._bundle["events"]["events"]:
            if event["id"] != self._selected_event_id:
                continue
            event["show_name"] = self._event_fields["show_name"].get().strip()
            event["day"] = day_labels.get(self._event_fields["day"].get().lower(), event.get("day", "monday"))
            event["start_time"] = self._event_fields["start_time"].get().strip()
            event["end_time"] = self._event_fields["end_time"].get().strip()
            event["music_format"] = self._event_fields["music_format"].get().strip()
            event["notes"] = self._event_fields["notes"].get().strip()
            event["enabled"] = self._event_enabled.get()
            break
        self._refresh_events()
        self._refresh_scheduler()
        self._refresh_daily_schedule()
        self.set_status("Event updated")

    def _duplicate_event(self) -> None:
        if not self._selected_event_id:
            return
        source = next(event for event in self._bundle["events"]["events"] if event["id"] == self._selected_event_id)
        clone = deepcopy(source)
        clone["id"] = new_slot_id().replace("slot", "evt")
        clone["show_name"] = f"{clone.get('show_name', 'Event')} (Copy)"
        self._bundle["events"]["events"].append(clone)
        self._refresh_events()
        self._refresh_scheduler()

    def _disable_event(self) -> None:
        if not self._selected_event_id:
            return
        for event in self._bundle["events"]["events"]:
            if event["id"] == self._selected_event_id:
                event["enabled"] = False
                break
        self._refresh_events()
        self._refresh_scheduler()

    def _delete_event(self) -> None:
        if not self._selected_event_id:
            return
        if Messagebox.yesno("Delete this event?", "Delete Event") != "Yes":
            return
        self._bundle["events"]["events"] = [
            event for event in self._bundle["events"]["events"] if event["id"] != self._selected_event_id
        ]
        self._selected_event_id = None
        self._refresh_events()
        self._refresh_scheduler()

    def _build_validation_tab(self) -> None:
        tab = ttk.Frame(self._notebook, style="Studio.TFrame", padding=12)
        self._notebook.add(tab, text="Validation")
        self._validation_list = tk.Listbox(tab, height=18, exportselection=False)
        self._validation_list.pack(fill="both", expand=True)

    def _refresh_validation_tab(self, warnings: list[str]) -> None:
        if not self._validation_list:
            return
        self._validation_list.delete(0, "end")
        for warning in warnings:
            self._validation_list.insert("end", warning)

    def _set_scroll_text(self, widget: ScrolledText | ttk.Label, content: str) -> None:
        if isinstance(widget, ScrolledText):
            widget.text.configure(state="normal")
            widget.delete("1.0", "end")
            widget.insert("end", content)
            widget.text.configure(state="disabled")
        else:
            widget.configure(text=content)

    def _on_event_select(self, _event=None) -> None:
        selection = ()
        if hasattr(self, "_scheduler_tree"):
            selection = self._scheduler_tree.selection()
        if not selection and hasattr(self, "_events_tree"):
            selection = self._events_tree.selection()
        if not selection:
            return
        self._selected_event_id = selection[0]
        event = next(item for item in self._bundle["events"]["events"] if item["id"] == self._selected_event_id)
        if hasattr(self, "_event_fields"):
            self._event_fields["show_name"].set(event.get("show_name", ""))
            self._event_fields["day"].set(DAY_LABELS.get(event.get("day", ""), "Monday"))
            self._event_fields["start_time"].set(event.get("start_time", ""))
            self._event_fields["end_time"].set(event.get("end_time", ""))
            self._event_fields["music_format"].set(event.get("music_format", ""))
            self._event_fields["notes"].set(event.get("notes", ""))
            self._event_enabled.set(event.get("enabled", True))

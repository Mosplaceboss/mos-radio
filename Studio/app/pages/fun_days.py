"""Fun / National Days — edit one observance, including Category."""

from __future__ import annotations

import tkinter as tk
from typing import Any

import ttkbootstrap as ttk

from app.core.fun_day_editor import FORM_FIELDS, form_values, record_from_form
from app.pages.base_page import BasePage

CONFIG_NAME = "fun_days"


class FunDaysPage(BasePage):
    page_id = "fun_days"
    page_title = "Fun / National Days"
    page_subtitle = "Recurring observances the DJs can mention"
    page_help = (
        "Pick a row, then edit it here. Category is Fun Day or Serious Day. "
        "Serious Day is one respectful mention. Breast Cancer Awareness Month "
        "opens as Serious Day until you choose otherwise."
    )

    def build(self) -> None:
        self._days: list[dict[str, Any]] = []
        self._index: int | None = None
        self._loading = False
        self._vars: dict[str, tk.Variable] = {}
        self._labels: dict[str, ttk.Label] = {}
        self._category_combo: ttk.Combobox | None = None

        toolbar = ttk.Frame(self._body, style="Studio.TFrame")
        toolbar.pack(fill="x", pady=(0, 12))
        ttk.Button(toolbar, text="Add Fun Day", bootstyle="secondary", command=self._add).pack(side="left")
        ttk.Button(toolbar, text="Save", bootstyle="primary", command=self._save_selected).pack(side="left", padx=8)
        ttk.Button(toolbar, text="Delete", bootstyle="secondary", command=self._delete).pack(side="left")
        ttk.Button(toolbar, text="Enable / Disable", bootstyle="secondary", command=self._toggle_enabled).pack(
            side="left", padx=8
        )
        ttk.Button(toolbar, text="Refresh", bootstyle="secondary", command=self._load).pack(side="left")

        panes = ttk.Frame(self._body, style="Studio.TFrame")
        panes.pack(fill="both", expand=True)
        panes.columnconfigure(0, weight=1)
        panes.columnconfigure(1, weight=1)
        panes.rowconfigure(0, weight=1)

        list_panel = ttk.Labelframe(panes, text="Today", style="StudioCard.TLabelframe", padding=8)
        list_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        columns = ("title", "date", "dj", "note", "on")
        self._tree = ttk.Treeview(list_panel, columns=columns, show="headings", height=16)
        for key, heading, width in (
            ("title", "Title", 220),
            ("date", "Date", 110),
            ("dj", "DJ", 120),
            ("note", "Note", 180),
            ("on", "On", 50),
        ):
            self._tree.heading(key, text=heading)
            self._tree.column(key, width=width, anchor="w")
        self._tree.pack(fill="both", expand=True)
        self._tree.bind("<<TreeviewSelect>>", self._on_select)

        form = ttk.Labelframe(panes, text="Edit Fun Day", style="StudioCard.TLabelframe", padding=16)
        form.grid(row=0, column=1, sticky="nsew")
        form.columnconfigure(1, weight=1)
        self._edit_form = form
        for row, field in enumerate(FORM_FIELDS):
            label = ttk.Label(form, text=field.label, style="StudioCard.TLabel")
            label.grid(row=row, column=0, sticky="w", pady=6, padx=(0, 12))
            self._labels[field.key] = label
            if field.kind == "check":
                variable = tk.BooleanVar(value=True)
                widget = ttk.Checkbutton(form, text="Enabled", variable=variable)
            elif field.kind == "choice":
                variable = tk.StringVar()
                widget = ttk.Combobox(
                    form,
                    textvariable=variable,
                    values=list(field.choices),
                    state="readonly",
                    width=42,
                )
                if field.key == "category":
                    self._category_combo = widget
            else:
                variable = tk.StringVar()
                widget = ttk.Entry(form, textvariable=variable, width=44)
            self._vars[field.key] = variable
            widget.grid(row=row, column=1, sticky="ew", pady=6)

    def on_show(self) -> None:
        self._load()

    def _load(self) -> None:
        bundle = self.config_manager.load(CONFIG_NAME, {"days": []})
        days = bundle.get("days") if isinstance(bundle, dict) else []
        self.replace_days([item for item in days if isinstance(item, dict)])

    def replace_days(self, days: list[dict[str, Any]], *, select: int | None = 0) -> None:
        self._days = [dict(item) for item in days]
        self._reload_tree(None if not self._days else (0 if select is None else select))

    def _reload_tree(self, select_index: int | None) -> None:
        self._loading = True
        self._tree.delete(*self._tree.get_children())
        for index, record in enumerate(self._days):
            shown = form_values(record)
            self._tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    shown["title"],
                    shown["date"],
                    shown["who"],
                    shown["note"],
                    "Yes" if shown["enabled"] else "No",
                ),
            )
        self._loading = False
        if select_index is None or not self._days:
            self._index = None
            return
        bounded = max(0, min(select_index, len(self._days) - 1))
        self._tree.selection_set(str(bounded))
        self._tree.focus(str(bounded))
        self._show_index(bounded)

    def _on_select(self, _event=None) -> None:
        if self._loading:
            return
        selected = self._tree.selection()
        if not selected:
            return
        self._show_index(int(selected[0]))

    def _show_index(self, index: int) -> None:
        self._index = index
        self._show_record(self._days[index])

    def _show_record(self, record: dict[str, Any]) -> None:
        shown = form_values(record)
        for key, variable in self._vars.items():
            variable.set(shown[key])

    def _collect(self) -> dict[str, Any]:
        values = {key: variable.get() for key, variable in self._vars.items()}
        previous = self._days[self._index] if self._index is not None else None
        return record_from_form(values, previous)

    def _save_selected(self) -> None:
        if self._index is None or not (0 <= self._index < len(self._days)):
            self.set_status("Select a fun day first")
            return
        self._days[self._index] = self._collect()
        self._persist()
        self._reload_tree(self._index)
        self.set_status("Fun day saved")

    def _persist(self) -> None:
        self.config_manager.save(CONFIG_NAME, {"days": self._days})

    def _add(self) -> None:
        self._days.append(
            record_from_form(
                {
                    "title": "",
                    "category": "Fun Day",
                    "when": "One-day",
                    "date": "",
                    "days_of_month": "",
                    "who": "Each DJ, each day",
                    "selected_djs": "",
                    "read_by": "",
                    "note": "",
                    "enabled": True,
                }
            )
        )
        self._persist()
        self._reload_tree(len(self._days) - 1)

    def _delete(self) -> None:
        if self._index is None:
            return
        del self._days[self._index]
        self._persist()
        self._reload_tree(0 if self._days else None)
        self.set_status("Fun day deleted")

    def _toggle_enabled(self) -> None:
        if self._index is None:
            return
        current = bool(self._vars["enabled"].get())
        self._vars["enabled"].set(not current)
        self._save_selected()

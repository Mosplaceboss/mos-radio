"""Weekly schedule manager with drag-and-drop programming."""

from __future__ import annotations

import tkinter as tk
from typing import Any

import ttkbootstrap as ttk
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.scrolled import ScrolledFrame

from app.core.background_tasks import run_in_background
from app.core.personality_model import display_label
from app.core.schedule_loader import ScheduleLoadResult, load_schedule_page_data
from app.core.schedule_model import (
    DAYS,
    DEFAULT_SLOT_DURATION_MINUTES,
    TIME_OPTIONS,
    color_for_personality,
    default_end_time,
    index_to_time,
    new_slot_id,
    normalize_schedule_data,
    slot_rowspan,
    time_to_index,
    validate_slot,
)
from app.pages.base_page import BasePage
from app.ui.theme import StudioTheme

CELL_HEIGHT = 26
TIME_COLUMN_WIDTH = 72
DAY_COLUMN_MIN_WIDTH = 120


def _text_color_for_background(hex_color: str) -> str:
    color = hex_color.lstrip("#")
    red, green, blue = int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
    brightness = (red * 299 + green * 587 + blue * 114) / 1000
    return "#111111" if brightness > 150 else "#ffffff"


class SchedulePage(BasePage):
    page_id = "schedule"
    page_title = "Schedule"
    page_subtitle = "Weekly programming calendar — drag personalities onto the grid"

    def build(self) -> None:
        self._data: dict[str, Any] = {"timezone": "America/New_York", "slots": []}
        self._personalities: list[dict[str, Any]] = []
        self._personality_colors: dict[str, str] = {}
        self._cells: dict[tuple[str, int], tk.Frame] = {}
        self._event_widgets: dict[str, tk.Frame] = {}
        self._selected_slot_id: str | None = None
        self._autosave_job: str | None = None
        self._drag_state: dict[str, Any] | None = None
        self._highlighted_cell: tuple[str, int] | None = None
        self._load_in_progress = False
        self._load_generation = 0

        toolbar = ttk.Frame(self._body, style="Studio.TFrame")
        toolbar.pack(fill="x", pady=(0, 12))
        self._loading_label = ttk.Label(toolbar, text="", style="StudioMuted.TLabel")
        self._loading_label.pack(side="left", padx=(0, 12))
        self._error_label = ttk.Label(toolbar, text="", style="StudioMuted.TLabel", wraplength=520)
        self._error_label.pack(side="left", fill="x", expand=True)
        ttk.Button(toolbar, text="Add Event", bootstyle="success", command=self._add_event).pack(side="left")
        ttk.Button(toolbar, text="Delete Event", bootstyle="danger", command=self._delete_selected_event).pack(
            side="left", padx=8
        )
        ttk.Button(toolbar, text="Save Now", bootstyle="primary", command=self._save_now).pack(side="right")

        panes = ttk.Panedwindow(self._body, orient="horizontal", bootstyle="secondary")
        panes.pack(fill="both", expand=True)

        palette_panel = ttk.Labelframe(
            panes,
            text="Personalities",
            style="StudioCard.TLabelframe",
            padding=12,
        )
        panes.add(palette_panel, weight=1)
        ttk.Label(
            palette_panel,
            text="Drag a personality onto the schedule to create an event.",
            style="StudioMuted.TLabel",
            wraplength=180,
        ).pack(anchor="w", pady=(0, 8))
        self._palette_frame = ttk.Frame(palette_panel, style="StudioPanel.TFrame")
        self._palette_frame.pack(fill="both", expand=True)

        calendar_panel = ttk.Labelframe(
            panes,
            text="Weekly Calendar",
            style="StudioCard.TLabelframe",
            padding=8,
        )
        panes.add(calendar_panel, weight=5)

        canvas_frame = ttk.Frame(calendar_panel, style="Studio.TFrame")
        canvas_frame.pack(fill="both", expand=True)

        self._canvas = tk.Canvas(
            canvas_frame,
            background=StudioTheme.BG_PANEL,
            highlightthickness=0,
            borderwidth=0,
        )
        scrollbar_y = ttk.Scrollbar(canvas_frame, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=scrollbar_y.set)
        self._grid_host = tk.Frame(self._canvas, background=StudioTheme.BG_PANEL)
        self._canvas_window = self._canvas.create_window((0, 0), window=self._grid_host, anchor="nw")
        self._canvas.pack(side="left", fill="both", expand=True)
        scrollbar_y.pack(side="right", fill="y")
        self._grid_host.bind("<Configure>", self._on_grid_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)

        self.bind_all("<ButtonRelease-1>", self._on_global_release, add="+")
        self.bind_all("<B1-Motion>", self._on_global_motion, add="+")

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
        self._loading_label.configure(text="Loading schedule…")
        self._error_label.configure(text="")
        self._show_busy_cursor(True)

        personalities_path = self.config_manager.path_for("personalities")
        schedule_path = self.config_manager.path_for("schedule")

        def work() -> ScheduleLoadResult:
            return load_schedule_page_data(personalities_path, schedule_path)

        def complete(result: ScheduleLoadResult) -> None:
            if generation != self._load_generation:
                return
            self._load_in_progress = False
            try:
                self._apply_loaded_data(result)
            except Exception as exc:
                self._loading_label.configure(text="")
                self._show_busy_cursor(False)
                self._error_label.configure(text=str(exc))
                self._show_error_dialog("Schedule", str(exc))
                return
            self._loading_label.configure(text="")
            self._show_busy_cursor(False)

        def failed(error: Exception) -> None:
            if generation != self._load_generation:
                return
            self._load_in_progress = False
            self._loading_label.configure(text="")
            self._show_busy_cursor(False)
            self._error_label.configure(text=str(error))
            self._show_error_dialog("Schedule", str(error))

        run_in_background(self, work, complete, on_error=failed)

    def _apply_loaded_data(self, result: ScheduleLoadResult) -> None:
        self._personalities = result.personalities
        self._data = result.schedule_data
        self.config_manager._cache["personalities"] = {"personalities": result.personalities}
        self.config_manager._cache["schedule"] = result.schedule_data
        if result.load_errors:
            self._error_label.configure(text="; ".join(result.load_errors))
            self.set_status("; ".join(result.load_errors))
        else:
            self._error_label.configure(text="")
            self.set_status(f"Schedule loaded ({len(self._data.get('slots', []))} events)")
        self._build_personality_colors()
        self._render_palette()
        self._render_calendar()

    def _build_personality_colors(self) -> None:
        personality_ids = [item["id"] for item in self._personalities]
        self._personality_colors = {
            personality_id: color_for_personality(personality_id, personality_ids)
            for personality_id in personality_ids
        }

    def _personality_by_id(self, personality_id: str) -> dict[str, Any] | None:
        for personality in self._personalities:
            if personality["id"] == personality_id:
                return personality
        return None

    def _slot_by_id(self, slot_id: str) -> dict[str, Any] | None:
        for slot in self._data.get("slots", []):
            if slot["id"] == slot_id:
                return slot
        return None

    def _on_grid_configure(self, _event=None) -> None:
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event) -> None:
        self._canvas.itemconfigure(self._canvas_window, width=event.width)

    def _render_palette(self) -> None:
        for child in self._palette_frame.winfo_children():
            child.destroy()
        if not self._personalities:
            ttk.Label(
                self._palette_frame,
                text="No personalities configured.",
                style="StudioMuted.TLabel",
                wraplength=180,
            ).pack(anchor="w")
            return

        for personality in self._personalities:
            color = self._personality_colors.get(personality["id"], StudioTheme.ACCENT)
            chip = tk.Frame(
                self._palette_frame,
                background=color,
                cursor="hand2",
                padx=10,
                pady=8,
            )
            chip.pack(fill="x", pady=4)
            tk.Label(
                chip,
                text=display_label(personality),
                background=color,
                foreground=_text_color_for_background(color),
                font=("Segoe UI", 10, "bold"),
                anchor="w",
            ).pack(fill="x")
            tk.Label(
                chip,
                text=personality.get("show_name", ""),
                background=color,
                foreground=_text_color_for_background(color),
                font=("Segoe UI", 9),
                anchor="w",
            ).pack(fill="x", pady=(2, 0))
            self._bind_drag_source(chip, "personality", personality_id=personality["id"])

    def _render_calendar(self) -> None:
        for child in self._grid_host.winfo_children():
            child.destroy()
        self._cells.clear()
        self._event_widgets.clear()

        for col, day in enumerate(DAYS, start=1):
            header = tk.Label(
                self._grid_host,
                text=day.title(),
                background=StudioTheme.BG_PANEL,
                foreground=StudioTheme.TEXT_PRIMARY,
                font=("Segoe UI", 10, "bold"),
                padx=8,
                pady=6,
            )
            header.grid(row=0, column=col, sticky="nsew", padx=1, pady=1)
            self._grid_host.columnconfigure(col, weight=1, minsize=DAY_COLUMN_MIN_WIDTH)

        time_header = tk.Label(
            self._grid_host,
            text="Time",
            background=StudioTheme.BG_PANEL,
            foreground=StudioTheme.TEXT_PRIMARY,
            font=("Segoe UI", 10, "bold"),
            width=8,
            padx=4,
            pady=6,
        )
        time_header.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)

        for index, time_label in enumerate(TIME_OPTIONS):
            row = index + 1
            label = tk.Label(
                self._grid_host,
                text=time_label,
                background=StudioTheme.BG_PANEL,
                foreground=StudioTheme.TEXT_MUTED,
                font=("Segoe UI", 9),
                width=8,
                anchor="e",
                padx=4,
            )
            label.grid(row=row, column=0, sticky="nsew", padx=1, pady=0)
            label.configure(height=1)

            for col, day in enumerate(DAYS, start=1):
                cell = tk.Frame(
                    self._grid_host,
                    background=StudioTheme.BG_DARK,
                    highlightthickness=1,
                    highlightbackground=StudioTheme.BORDER,
                    height=CELL_HEIGHT,
                )
                cell.grid(row=row, column=col, sticky="nsew", padx=1, pady=0)
                cell.grid_propagate(False)
                cell.day = day
                cell.time_index = index
                self._cells[(day, index)] = cell
                self._bind_drop_target(cell)

        occupied: set[tuple[str, int]] = set()
        for slot in sorted(self._data.get("slots", []), key=self._slot_sort_key):
            day = slot.get("day", "monday").lower()
            try:
                start_index = time_to_index(slot.get("start_time", "00:00"))
                end_index = time_to_index(slot.get("end_time", "00:30"))
            except ValueError:
                continue
            if day not in DAYS or end_index <= start_index:
                continue

            covered = {(day, idx) for idx in range(start_index, end_index)}
            if covered & occupied:
                continue
            occupied |= covered

            row = start_index + 1
            col = DAYS.index(day) + 1
            rowspan = slot_rowspan(slot["start_time"], slot["end_time"])
            widget = self._create_event_widget(self._grid_host, slot)
            widget.grid(row=row, column=col, rowspan=rowspan, sticky="nsew", padx=2, pady=1)
            self._event_widgets[slot["id"]] = widget

    def _slot_sort_key(self, slot: dict[str, Any]) -> tuple[str, int]:
        try:
            return (slot.get("day", ""), time_to_index(slot.get("start_time", "00:00")))
        except ValueError:
            return ("", 0)

    def _create_event_widget(self, parent: tk.Misc, slot: dict[str, Any]) -> tk.Frame:
        color = slot.get("color") or self._personality_colors.get(slot.get("personality_id", ""), StudioTheme.ACCENT)
        text_color = _text_color_for_background(color)
        frame = tk.Frame(parent, background=color, cursor="hand2", padx=6, pady=4)
        frame.slot_id = slot["id"]

        title = slot.get("show_name") or "Scheduled Show"
        tk.Label(
            frame,
            text=title,
            background=color,
            foreground=text_color,
            font=("Segoe UI", 9, "bold"),
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            frame,
            text=f"{slot.get('start_time', '')} – {slot.get('end_time', '')}",
            background=color,
            foreground=text_color,
            font=("Segoe UI", 8),
            anchor="w",
        ).pack(fill="x")
        personality = self._personality_by_id(slot.get("personality_id", ""))
        personality_name = display_label(personality) if personality else "Unassigned"
        tk.Label(
            frame,
            text=personality_name,
            background=color,
            foreground=text_color,
            font=("Segoe UI", 8),
            anchor="w",
        ).pack(fill="x", pady=(2, 0))

        frame.bind("<Button-1>", lambda e, sid=slot["id"]: self._select_event(sid))
        frame.bind("<Double-Button-1>", lambda e, sid=slot["id"]: self._edit_event(sid))
        for child in frame.winfo_children():
            child.bind("<Button-1>", lambda e, sid=slot["id"]: self._select_event(sid))
            child.bind("<Double-Button-1>", lambda e, sid=slot["id"]: self._edit_event(sid))

        self._bind_drag_source(frame, "event", slot_id=slot["id"])
        return frame

    def _bind_drag_source(self, widget: tk.Misc, source_type: str, **payload: str) -> None:
        def on_press(event) -> None:
            self._drag_state = {
                "type": source_type,
                "payload": payload,
                "x": event.x_root,
                "y": event.y_root,
                "dragging": False,
            }

        widget.bind("<ButtonPress-1>", on_press, add="+")

    def _bind_drop_target(self, cell: tk.Frame) -> None:
        cell.bind("<ButtonRelease-1>", lambda e, c=cell: self._handle_drop_on_cell(c), add="+")

    def _on_global_motion(self, event) -> None:
        if not self._drag_state:
            return
        delta_x = abs(event.x_root - self._drag_state["x"])
        delta_y = abs(event.y_root - self._drag_state["y"])
        if delta_x > 4 or delta_y > 4:
            self._drag_state["dragging"] = True
        cell = self._cell_at_position(event.x_root, event.y_root)
        self._set_highlighted_cell(cell)

    def _on_global_release(self, event) -> None:
        if not self._drag_state or not self._drag_state.get("dragging"):
            self._drag_state = None
            self._set_highlighted_cell(None)
            return

        cell = self._cell_at_position(event.x_root, event.y_root)
        if cell:
            self._handle_drop_on_cell(cell)

        self._drag_state = None
        self._set_highlighted_cell(None)

    def _cell_at_position(self, x_root: int, y_root: int) -> tk.Frame | None:
        target = self.winfo_containing(x_root, y_root)
        while target is not None:
            if isinstance(target, tk.Frame) and hasattr(target, "day") and hasattr(target, "time_index"):
                return target
            target = target.master
        return None

    def _set_highlighted_cell(self, cell: tk.Frame | None) -> None:
        if self._highlighted_cell and self._highlighted_cell in self._cells:
            old = self._cells[self._highlighted_cell]
            old.configure(highlightbackground=StudioTheme.BORDER)
        if cell is not None:
            key = (cell.day, cell.time_index)
            self._highlighted_cell = key
            cell.configure(highlightbackground=StudioTheme.ACCENT)
        else:
            self._highlighted_cell = None

    def _handle_drop_on_cell(self, cell: tk.Frame) -> None:
        if not self._drag_state:
            return
        day = cell.day
        start_time = index_to_time(cell.time_index)
        payload = self._drag_state.get("payload", {})
        source_type = self._drag_state.get("type")

        if source_type == "personality":
            personality_id = payload.get("personality_id", "")
            self._create_event_from_drop(personality_id, day, start_time)
        elif source_type == "event":
            slot_id = payload.get("slot_id", "")
            self._move_event(slot_id, day, start_time)

    def _create_event_from_drop(self, personality_id: str, day: str, start_time: str) -> None:
        personality = self._personality_by_id(personality_id)
        if not personality:
            return
        end_time = default_end_time(start_time, DEFAULT_SLOT_DURATION_MINUTES)
        music_formats = personality.get("music_formats", [])
        slot = {
            "id": new_slot_id(),
            "day": day,
            "start_time": start_time,
            "end_time": end_time,
            "personality_id": personality_id,
            "show_name": personality.get("show_name") or display_label(personality),
            "music_format": music_formats[0] if music_formats else "",
            "requests_enabled": True,
            "notes": "",
            "color": self._personality_colors.get(personality_id, StudioTheme.ACCENT),
        }
        errors = validate_slot(slot)
        if errors:
            Messagebox.show_warning("\n".join(errors), "Schedule")
            return
        self._data.setdefault("slots", []).append(slot)
        self._render_calendar()
        self._select_event(slot["id"])
        self._schedule_autosave()
        self.set_status(f"Scheduled {slot['show_name']} on {day.title()} at {start_time}")

    def _move_event(self, slot_id: str, day: str, start_time: str) -> None:
        slot = self._slot_by_id(slot_id)
        if not slot:
            return
        try:
            duration = time_to_index(slot["end_time"]) - time_to_index(slot["start_time"])
        except ValueError:
            return
        new_end = index_to_time(time_to_index(start_time) + duration)
        slot["day"] = day
        slot["start_time"] = start_time
        slot["end_time"] = new_end
        errors = validate_slot(slot)
        if errors:
            Messagebox.show_warning("\n".join(errors), "Schedule")
            self.on_show()
            return
        self._render_calendar()
        self._select_event(slot_id)
        self._schedule_autosave()
        self.set_status(f"Moved {slot['show_name']} to {day.title()} at {start_time}")

    def _select_event(self, slot_id: str) -> None:
        for widget in self._event_widgets.values():
            widget.configure(highlightthickness=0)
        self._selected_slot_id = slot_id
        widget = self._event_widgets.get(slot_id)
        if widget:
            widget.configure(highlightthickness=2, highlightbackground="#ffffff")

    def _add_event(self) -> None:
        if not self._personalities:
            Messagebox.show_info("Add personalities before creating schedule events.", "Schedule")
            return
        slot = {
            "id": new_slot_id(),
            "day": "monday",
            "start_time": "06:00",
            "end_time": default_end_time("06:00"),
            "personality_id": self._personalities[0]["id"],
            "show_name": self._personalities[0].get("show_name", ""),
            "music_format": "",
            "requests_enabled": True,
            "notes": "",
            "color": self._personality_colors.get(self._personalities[0]["id"], StudioTheme.ACCENT),
        }
        edited = self._open_event_editor(slot)
        if not edited:
            return
        slot.update(edited)
        errors = validate_slot(slot)
        if errors:
            Messagebox.show_warning("\n".join(errors), "Schedule")
            return
        self._data.setdefault("slots", []).append(slot)
        self._render_calendar()
        self._select_event(slot["id"])
        self._schedule_autosave()

    def _edit_event(self, slot_id: str) -> None:
        slot = self._slot_by_id(slot_id)
        if not slot:
            return
        edited = self._open_event_editor(slot)
        if not edited:
            return
        slot.update(edited)
        errors = validate_slot(slot)
        if errors:
            Messagebox.show_warning("\n".join(errors), "Schedule")
            return
        self._render_calendar()
        self._select_event(slot_id)
        self._schedule_autosave()

    def _delete_selected_event(self) -> None:
        if not self._selected_slot_id:
            Messagebox.show_info("Select an event to delete.", "Schedule")
            return
        slot = self._slot_by_id(self._selected_slot_id)
        if not slot:
            return
        confirmed = Messagebox.yesno(f"Delete '{slot.get('show_name', 'event')}'?", "Confirm Delete")
        if confirmed != "Yes":
            return
        self._data["slots"] = [item for item in self._data.get("slots", []) if item["id"] != slot["id"]]
        self._selected_slot_id = None
        self._render_calendar()
        self._schedule_autosave()
        self.set_status(f"Deleted schedule event '{slot.get('show_name', '')}'")

    def _open_event_editor(self, slot: dict[str, Any]) -> dict[str, Any] | None:
        dialog = ttk.Toplevel(self)
        dialog.title("Edit Scheduled Event")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        dialog.geometry("560x620")
        dialog.minsize(520, 560)

        scroll = ScrolledFrame(dialog, autohide=True, bootstyle="secondary")
        scroll.pack(fill="both", expand=True, padx=16, pady=16)
        form = scroll.container

        personality_map = {item["id"]: display_label(item) for item in self._personalities}
        personality_ids = list(personality_map.keys())

        ttk.Label(form, text="Personality").grid(row=0, column=0, sticky="w", pady=6)
        personality_combo = ttk.Combobox(
            form,
            values=[personality_map[pid] for pid in personality_ids],
            state="readonly",
            width=36,
        )
        personality_combo.grid(row=0, column=1, sticky="ew", pady=6)

        ttk.Label(form, text="Day").grid(row=1, column=0, sticky="w", pady=6)
        day_combo = ttk.Combobox(form, values=[day.title() for day in DAYS], state="readonly", width=36)
        day_combo.grid(row=1, column=1, sticky="ew", pady=6)

        ttk.Label(form, text="Start Time").grid(row=2, column=0, sticky="w", pady=6)
        start_combo = ttk.Combobox(form, values=list(TIME_OPTIONS), state="readonly", width=36)
        start_combo.grid(row=2, column=1, sticky="ew", pady=6)

        ttk.Label(form, text="End Time").grid(row=3, column=0, sticky="w", pady=6)
        end_combo = ttk.Combobox(form, values=list(TIME_OPTIONS), state="readonly", width=36)
        end_combo.grid(row=3, column=1, sticky="ew", pady=6)

        ttk.Label(form, text="Show Name").grid(row=4, column=0, sticky="w", pady=6)
        show_entry = ttk.Entry(form, width=38)
        show_entry.grid(row=4, column=1, sticky="ew", pady=6)

        ttk.Label(form, text="Music Format").grid(row=5, column=0, sticky="w", pady=6)
        music_entry = ttk.Entry(form, width=38)
        music_entry.grid(row=5, column=1, sticky="ew", pady=6)

        requests_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(form, text="Requests On", variable=requests_var).grid(
            row=6, column=1, sticky="w", pady=6
        )

        ttk.Label(form, text="Notes").grid(row=7, column=0, sticky="nw", pady=6)
        notes_text = tk.Text(
            form,
            height=5,
            wrap="word",
            bg=StudioTheme.BG_PANEL,
            fg=StudioTheme.TEXT_PRIMARY,
            insertbackground=StudioTheme.TEXT_PRIMARY,
            relief="flat",
            highlightthickness=1,
            highlightbackground=StudioTheme.BORDER,
            font=("Segoe UI", 10),
        )
        notes_text.grid(row=7, column=1, sticky="ew", pady=6)

        color = slot.get("color", StudioTheme.ACCENT)
        ttk.Label(form, text="Color").grid(row=8, column=0, sticky="w", pady=6)
        color_chip = tk.Frame(form, background=color, width=180, height=24)
        color_chip.grid(row=8, column=1, sticky="w", pady=6)

        day_combo.set(slot.get("day", "monday").title())
        start_combo.set(slot.get("start_time", "06:00"))
        end_combo.set(slot.get("end_time", default_end_time("06:00")))
        show_entry.insert(0, slot.get("show_name", ""))
        music_entry.insert(0, slot.get("music_format", ""))
        requests_var.set(slot.get("requests_enabled", True))
        notes_text.insert("1.0", slot.get("notes", ""))
        if slot.get("personality_id") in personality_map:
            personality_combo.set(personality_map[slot["personality_id"]])

        def on_personality_change(_event=None) -> None:
            selected = personality_combo.get()
            personality_id = next((pid for pid, name in personality_map.items() if name == selected), "")
            personality = self._personality_by_id(personality_id)
            if not personality:
                return
            if not show_entry.get().strip():
                show_entry.delete(0, "end")
                show_entry.insert(0, personality.get("show_name", ""))
            if not music_entry.get().strip():
                formats = personality.get("music_formats", [])
                if formats:
                    music_entry.delete(0, "end")
                    music_entry.insert(0, formats[0])
            new_color = self._personality_colors.get(personality_id, StudioTheme.ACCENT)
            color_chip.configure(background=new_color)

        personality_combo.bind("<<ComboboxSelected>>", on_personality_change)

        form.columnconfigure(1, weight=1)
        result: dict[str, Any] | None = {}

        def save_and_close() -> None:
            selected_name = personality_combo.get()
            personality_id = next(
                (pid for pid, name in personality_map.items() if name == selected_name),
                personality_ids[0] if personality_ids else "",
            )
            show_name = show_entry.get().strip()
            if not show_name:
                Messagebox.show_warning("Show name is required.", "Validation")
                return
            result.clear()
            result.update(
                {
                    "personality_id": personality_id,
                    "day": day_combo.get().lower(),
                    "start_time": start_combo.get(),
                    "end_time": end_combo.get(),
                    "show_name": show_name,
                    "music_format": music_entry.get().strip(),
                    "requests_enabled": requests_var.get(),
                    "notes": notes_text.get("1.0", "end").strip(),
                    "color": self._personality_colors.get(personality_id, StudioTheme.ACCENT),
                }
            )
            dialog.destroy()

        buttons = ttk.Frame(dialog, padding=(16, 0, 16, 16))
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Cancel", bootstyle="secondary", command=dialog.destroy).pack(side="right")
        ttk.Button(buttons, text="Save", bootstyle="primary", command=save_and_close).pack(side="right", padx=8)

        dialog.wait_window()
        return result if result else None

    def _autosave_enabled(self) -> bool:
        settings = self.config_manager.load("settings", {})
        return settings.get("auto_save", True)

    def _schedule_autosave(self) -> None:
        if not self._autosave_enabled():
            return
        if self._autosave_job:
            self.after_cancel(self._autosave_job)
        self._autosave_job = self.after(700, self._autosave_now)

    def _autosave_now(self) -> None:
        self._autosave_job = None
        self._persist_config_async(
            "schedule",
            self._data,
            status_message="Schedule saved automatically",
            error_title="Save Schedule",
        )

    def _save_now(self) -> None:
        self._persist_config_async(
            "schedule",
            self._data,
            status_message="Schedule saved",
            error_title="Save Schedule",
        )

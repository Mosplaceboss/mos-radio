"""Weekly schedule page with drag-and-drop foundation."""

from __future__ import annotations

import tkinter as tk
import uuid
from typing import Callable

import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox

from app.pages.base_page import BasePage
from app.ui.theme import StudioTheme

DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
HOURS = list(range(24))


class ScheduleSlotWidget(ttk.Frame):
    """Single schedule block prepared for future drag-and-drop support."""

    def __init__(
        self,
        parent: ttk.Misc,
        slot: dict,
        on_edit: Callable[[dict], None],
        on_delete: Callable[[dict], None],
    ) -> None:
        super().__init__(parent, style="StudioPanel.TFrame", padding=4)
        self.slot = slot
        self._on_edit = on_edit
        self._on_delete = on_delete
        self._drag_data: dict[str, int] = {}

        color = slot.get("color", StudioTheme.ACCENT)

        card = ttk.Labelframe(
            self,
            text=slot.get("show_name", "Show"),
            style="StudioCard.TLabelframe",
            padding=6,
        )
        card.pack(fill="x")

        ttk.Label(
            card,
            text=f"{slot.get('start_time', '')} – {slot.get('end_time', '')}",
            style="StudioMuted.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            card,
            text=f"Personality: {slot.get('personality_id', '—')}",
            style="StudioMuted.TLabel",
        ).pack(anchor="w", pady=(2, 4))

        actions = ttk.Frame(card, style="StudioPanel.TFrame")
        actions.pack(fill="x")
        ttk.Button(
            actions,
            text="Edit",
            bootstyle="secondary-link",
            command=lambda: self._on_edit(self.slot),
        ).pack(side="left")
        ttk.Button(
            actions,
            text="Delete",
            bootstyle="danger-link",
            command=lambda: self._on_delete(self.slot),
        ).pack(side="right")

        for widget in (self, card):
            widget.bind("<ButtonPress-1>", self._on_drag_start)
            widget.bind("<B1-Motion>", self._on_drag_motion)
            widget.bind("<ButtonRelease-1>", self._on_drag_release)

    def _on_drag_start(self, event) -> None:
        self._drag_data = {"x": event.x_root, "y": event.y_root, "dragging": False}

    def _on_drag_motion(self, event) -> None:
        if not self._drag_data:
            return
        delta_x = abs(event.x_root - self._drag_data["x"])
        delta_y = abs(event.y_root - self._drag_data["y"])
        if delta_x > 5 or delta_y > 5:
            self._drag_data["dragging"] = True

    def _on_drag_release(self, event) -> None:
        self._drag_data = {}


class SchedulePage(BasePage):
    page_id = "schedule"
    page_title = "Schedule"
    page_subtitle = "Weekly programming grid — structured for future drag-and-drop scheduling"

    def build(self) -> None:
        toolbar = ttk.Frame(self._body, style="Studio.TFrame")
        toolbar.pack(fill="x", pady=(0, 12))
        ttk.Button(toolbar, text="Add Slot", bootstyle="success", command=self._add_slot).pack(side="left")
        ttk.Button(toolbar, text="Save Schedule", bootstyle="primary", command=self._save).pack(side="right")

        self._canvas_frame = ttk.Frame(self._body, style="Studio.TFrame")
        self._canvas_frame.pack(fill="both", expand=True)

        self._canvas = tk.Canvas(
            self._canvas_frame,
            background=StudioTheme.BG_PANEL,
            highlightthickness=0,
            borderwidth=0,
        )
        scrollbar_y = ttk.Scrollbar(self._canvas_frame, orient="vertical", command=self._canvas.yview)
        scrollbar_x = ttk.Scrollbar(self._canvas_frame, orient="horizontal", command=self._canvas.xview)
        self._canvas.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)

        self._grid_frame = ttk.Frame(self._canvas, style="StudioPanel.TFrame")
        self._canvas_window = self._canvas.create_window((0, 0), window=self._grid_frame, anchor="nw")

        self._canvas.pack(side="left", fill="both", expand=True)
        scrollbar_y.pack(side="right", fill="y")
        scrollbar_x.pack(side="bottom", fill="x")

        self._grid_frame.bind("<Configure>", self._on_frame_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)

        self._data = {"timezone": "America/New_York", "slots": []}
        self._slot_widgets: list[ScheduleSlotWidget] = []

    def on_show(self) -> None:
        self._data = self.config_manager.load("schedule", {"timezone": "America/New_York", "slots": []})
        self._render_grid()

    def _on_frame_configure(self, _event=None) -> None:
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event) -> None:
        self._canvas.itemconfigure(self._canvas_window, width=event.width)

    def _render_grid(self) -> None:
        for child in self._grid_frame.winfo_children():
            child.destroy()
        self._slot_widgets.clear()

        ttk.Label(self._grid_frame, text="Time", style="StudioCard.TLabel", width=8).grid(
            row=0, column=0, padx=4, pady=4, sticky="nsew"
        )
        for col, day in enumerate(DAYS, start=1):
            ttk.Label(
                self._grid_frame,
                text=day.title(),
                style="StudioCard.TLabel",
                anchor="center",
            ).grid(row=0, column=col, padx=4, pady=4, sticky="nsew")

        for row, hour in enumerate(HOURS, start=1):
            ttk.Label(
                self._grid_frame,
                text=f"{hour:02d}:00",
                style="StudioMuted.TLabel",
                width=8,
            ).grid(row=row, column=0, padx=4, pady=2, sticky="nsew")

            for col, day in enumerate(DAYS, start=1):
                cell = ttk.Frame(self._grid_frame, style="StudioPanel.TFrame", padding=2)
                cell.grid(row=row, column=col, padx=2, pady=2, sticky="nsew")
                cell.configure(bootstyle="secondary")
                self._grid_frame.columnconfigure(col, weight=1)

                for slot in self._slots_for_cell(day, hour):
                    widget = ScheduleSlotWidget(
                        cell,
                        slot=slot,
                        on_edit=self._edit_slot,
                        on_delete=self._delete_slot,
                    )
                    widget.pack(fill="x", pady=2)
                    self._slot_widgets.append(widget)

    def _slots_for_cell(self, day: str, hour: int) -> list[dict]:
        matches = []
        for slot in self._data.get("slots", []):
            if slot.get("day", "").lower() != day:
                continue
            start_hour = int(slot.get("start_time", "00:00").split(":")[0])
            if start_hour == hour:
                matches.append(slot)
        return matches

    def _personality_names(self) -> dict[str, str]:
        personalities = self.config_manager.load("personalities", {"personalities": []})
        return {item["id"]: item.get("name", item["id"]) for item in personalities.get("personalities", [])}

    def _open_slot_editor(self, slot: dict | None = None) -> dict | None:
        dialog = ttk.Toplevel(self)
        dialog.title("Schedule Slot")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        dialog.geometry("500x380")

        form = ttk.Frame(dialog, padding=20)
        form.pack(fill="both", expand=True)

        personality_map = self._personality_names()
        personality_ids = list(personality_map.keys())

        ttk.Label(form, text="Show Name").grid(row=0, column=0, sticky="w", pady=6)
        show_entry = ttk.Entry(form, width=36)
        show_entry.grid(row=0, column=1, sticky="ew", pady=6)

        ttk.Label(form, text="Day").grid(row=1, column=0, sticky="w", pady=6)
        day_combo = ttk.Combobox(form, values=[day.title() for day in DAYS], state="readonly", width=34)
        day_combo.grid(row=1, column=1, sticky="ew", pady=6)
        day_combo.current(0)

        ttk.Label(form, text="Start Time (HH:MM)").grid(row=2, column=0, sticky="w", pady=6)
        start_entry = ttk.Entry(form, width=36)
        start_entry.grid(row=2, column=1, sticky="ew", pady=6)
        start_entry.insert(0, "06:00")

        ttk.Label(form, text="End Time (HH:MM)").grid(row=3, column=0, sticky="w", pady=6)
        end_entry = ttk.Entry(form, width=36)
        end_entry.grid(row=3, column=1, sticky="ew", pady=6)
        end_entry.insert(0, "10:00")

        ttk.Label(form, text="Personality").grid(row=4, column=0, sticky="w", pady=6)
        personality_combo = ttk.Combobox(
            form,
            values=[personality_map[pid] for pid in personality_ids],
            state="readonly",
            width=34,
        )
        personality_combo.grid(row=4, column=1, sticky="ew", pady=6)
        if personality_ids:
            personality_combo.current(0)

        ttk.Label(form, text="Color (#hex)").grid(row=5, column=0, sticky="w", pady=6)
        color_entry = ttk.Entry(form, width=36)
        color_entry.grid(row=5, column=1, sticky="ew", pady=6)
        color_entry.insert(0, StudioTheme.ACCENT)

        if slot:
            show_entry.insert(0, slot.get("show_name", ""))
            day_combo.set(slot.get("day", "monday").title())
            start_entry.delete(0, "end")
            start_entry.insert(0, slot.get("start_time", "06:00"))
            end_entry.delete(0, "end")
            end_entry.insert(0, slot.get("end_time", "10:00"))
            color_entry.delete(0, "end")
            color_entry.insert(0, slot.get("color", StudioTheme.ACCENT))
            if slot.get("personality_id") in personality_map:
                personality_combo.set(personality_map[slot["personality_id"]])

        form.columnconfigure(1, weight=1)
        result: dict | None = {}

        def save_and_close() -> None:
            show_name = show_entry.get().strip()
            if not show_name:
                Messagebox.show_warning("Show name is required.", "Validation")
                return
            selected_name = personality_combo.get()
            personality_id = next(
                (pid for pid, name in personality_map.items() if name == selected_name),
                personality_ids[0] if personality_ids else "",
            )
            result.clear()
            result.update(
                {
                    "show_name": show_name,
                    "day": day_combo.get().lower(),
                    "start_time": start_entry.get().strip(),
                    "end_time": end_entry.get().strip(),
                    "personality_id": personality_id,
                    "color": color_entry.get().strip() or StudioTheme.ACCENT,
                }
            )
            dialog.destroy()

        buttons = ttk.Frame(dialog, padding=(20, 0, 20, 20))
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Cancel", bootstyle="secondary", command=dialog.destroy).pack(side="right")
        ttk.Button(buttons, text="OK", bootstyle="primary", command=save_and_close).pack(side="right", padx=8)

        dialog.wait_window()
        return result if result else None

    def _add_slot(self) -> None:
        edited = self._open_slot_editor()
        if not edited:
            return
        slot = {"id": f"slot-{uuid.uuid4().hex[:8]}", **edited}
        self._data.setdefault("slots", []).append(slot)
        self._render_grid()
        self.set_status(f"Added schedule slot '{slot['show_name']}'")

    def _edit_slot(self, slot: dict) -> None:
        edited = self._open_slot_editor(slot)
        if not edited:
            return
        slot.update(edited)
        self._render_grid()
        self.set_status(f"Updated schedule slot '{slot['show_name']}'")

    def _delete_slot(self, slot: dict) -> None:
        confirmed = Messagebox.yesno(f"Delete slot '{slot.get('show_name', '')}'?", "Confirm Delete")
        if confirmed != "Yes":
            return
        self._data["slots"] = [item for item in self._data.get("slots", []) if item["id"] != slot["id"]]
        self._render_grid()
        self.set_status(f"Deleted schedule slot '{slot.get('show_name', '')}'")

    def _save(self) -> None:
        self.config_manager.save("schedule", self._data)
        self.set_status("Schedule configuration saved")

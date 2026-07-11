"""Personalities management page."""

from __future__ import annotations

import uuid
from datetime import datetime

import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox

from app.pages.base_page import BasePage


class PersonalitiesPage(BasePage):
    page_id = "personalities"
    page_title = "Personalities"
    page_subtitle = "Manage on-air personality profiles consumed by automation"

    def build(self) -> None:
        toolbar = ttk.Frame(self._body, style="Studio.TFrame")
        toolbar.pack(fill="x", pady=(0, 12))

        ttk.Button(toolbar, text="Add Personality", bootstyle="success", command=self._add_personality).pack(
            side="left"
        )
        ttk.Button(toolbar, text="Edit Selected", bootstyle="primary", command=self._edit_personality).pack(
            side="left", padx=8
        )
        ttk.Button(toolbar, text="Remove Selected", bootstyle="danger", command=self._remove_personality).pack(
            side="left"
        )
        ttk.Button(toolbar, text="Save", bootstyle="info", command=self._save).pack(side="right")

        columns = ("name", "voice_id", "active", "description")
        self._tree = ttk.Treeview(
            self._body,
            columns=columns,
            show="headings",
            bootstyle="info",
            height=14,
        )
        self._tree.heading("name", text="Name")
        self._tree.heading("voice_id", text="Voice ID")
        self._tree.heading("active", text="Active")
        self._tree.heading("description", text="Description")
        self._tree.column("name", width=160)
        self._tree.column("voice_id", width=140)
        self._tree.column("active", width=80, anchor="center")
        self._tree.column("description", width=360)
        self._tree.pack(fill="both", expand=True)

        self._data = {"personalities": []}

    def on_show(self) -> None:
        self._data = self.config_manager.load("personalities", {"personalities": []})
        self._refresh_tree()

    def _refresh_tree(self) -> None:
        self._tree.delete(*self._tree.get_children())
        for personality in self._data.get("personalities", []):
            self._tree.insert(
                "",
                "end",
                iid=personality["id"],
                values=(
                    personality.get("name", ""),
                    personality.get("voice_id", ""),
                    "Yes" if personality.get("active", True) else "No",
                    personality.get("description", ""),
                ),
            )

    def _selected_personality(self) -> dict | None:
        selection = self._tree.selection()
        if not selection:
            return None
        personality_id = selection[0]
        for personality in self._data.get("personalities", []):
            if personality["id"] == personality_id:
                return personality
        return None

    def _open_editor(self, personality: dict | None = None) -> dict | None:
        dialog = ttk.Toplevel(self)
        dialog.title("Personality")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        dialog.geometry("480x320")

        fields: dict[str, ttk.Entry | ttk.BooleanVar] = {}
        form = ttk.Frame(dialog, padding=20)
        form.pack(fill="both", expand=True)

        ttk.Label(form, text="Name").grid(row=0, column=0, sticky="w", pady=6)
        name_entry = ttk.Entry(form, width=40)
        name_entry.grid(row=0, column=1, sticky="ew", pady=6)
        fields["name"] = name_entry

        ttk.Label(form, text="Voice ID").grid(row=1, column=0, sticky="w", pady=6)
        voice_entry = ttk.Entry(form, width=40)
        voice_entry.grid(row=1, column=1, sticky="ew", pady=6)
        fields["voice_id"] = voice_entry

        active_var = ttk.BooleanVar(value=True)
        ttk.Checkbutton(form, text="Active", variable=active_var).grid(row=2, column=1, sticky="w", pady=6)
        fields["active"] = active_var

        ttk.Label(form, text="Description").grid(row=3, column=0, sticky="nw", pady=6)
        description_entry = ttk.Entry(form, width=40)
        description_entry.grid(row=3, column=1, sticky="ew", pady=6)
        fields["description"] = description_entry

        if personality:
            name_entry.insert(0, personality.get("name", ""))
            voice_entry.insert(0, personality.get("voice_id", ""))
            active_var.set(personality.get("active", True))
            description_entry.insert(0, personality.get("description", ""))

        form.columnconfigure(1, weight=1)
        result: dict | None = {}

        def save_and_close() -> None:
            name = name_entry.get().strip()
            voice_id = voice_entry.get().strip()
            if not name or not voice_id:
                Messagebox.show_warning("Name and Voice ID are required.", "Validation")
                return
            result.clear()
            result.update(
                {
                    "name": name,
                    "voice_id": voice_id,
                    "active": active_var.get(),
                    "description": description_entry.get().strip(),
                }
            )
            dialog.destroy()

        buttons = ttk.Frame(dialog, padding=(20, 0, 20, 20))
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Cancel", bootstyle="secondary", command=dialog.destroy).pack(side="right")
        ttk.Button(buttons, text="OK", bootstyle="primary", command=save_and_close).pack(side="right", padx=8)

        dialog.wait_window()
        return result if result else None

    def _add_personality(self) -> None:
        edited = self._open_editor()
        if not edited:
            return
        now = datetime.now().isoformat(timespec="seconds")
        personality = {
            "id": f"personality-{uuid.uuid4().hex[:8]}",
            "created": now,
            "updated": now,
            **edited,
        }
        self._data.setdefault("personalities", []).append(personality)
        self._refresh_tree()
        self.set_status(f"Added personality '{personality['name']}'")

    def _edit_personality(self) -> None:
        personality = self._selected_personality()
        if not personality:
            Messagebox.show_info("Select a personality to edit.", "Personalities")
            return
        edited = self._open_editor(personality)
        if not edited:
            return
        personality.update(edited)
        personality["updated"] = datetime.now().isoformat(timespec="seconds")
        self._refresh_tree()
        self.set_status(f"Updated personality '{personality['name']}'")

    def _remove_personality(self) -> None:
        personality = self._selected_personality()
        if not personality:
            Messagebox.show_info("Select a personality to remove.", "Personalities")
            return
        confirmed = Messagebox.yesno(
            f"Remove personality '{personality.get('name', '')}'?",
            "Confirm Remove",
        )
        if confirmed != "Yes":
            return
        self._data["personalities"] = [
            item for item in self._data.get("personalities", []) if item["id"] != personality["id"]
        ]
        self._refresh_tree()
        self.set_status(f"Removed personality '{personality.get('name', '')}'")

    def _save(self) -> None:
        self.config_manager.save("personalities", self._data)
        self.set_status("Personalities configuration saved")

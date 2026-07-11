"""Voice library management page."""

from __future__ import annotations

import uuid

import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox

from app.pages.base_page import BasePage


class VoiceLibraryPage(BasePage):
    page_id = "voice_library"
    page_title = "Voice Library"
    page_subtitle = "Manage Voicebox voices and station voice assignments"

    def build(self) -> None:
        toolbar = ttk.Frame(self._body, style="Studio.TFrame")
        toolbar.pack(fill="x", pady=(0, 12))

        ttk.Button(toolbar, text="Add Voice", bootstyle="success", command=self._add_voice).pack(side="left")
        ttk.Button(toolbar, text="Edit Selected", bootstyle="primary", command=self._edit_voice).pack(
            side="left", padx=8
        )
        ttk.Button(toolbar, text="Remove Selected", bootstyle="danger", command=self._remove_voice).pack(
            side="left"
        )
        ttk.Button(toolbar, text="Save", bootstyle="info", command=self._save).pack(side="right")

        columns = ("name", "provider", "voicebox_id", "tags", "description")
        self._tree = ttk.Treeview(
            self._body,
            columns=columns,
            show="headings",
            bootstyle="info",
            height=14,
        )
        self._tree.heading("name", text="Name")
        self._tree.heading("provider", text="Provider")
        self._tree.heading("voicebox_id", text="Voicebox ID")
        self._tree.heading("tags", text="Tags")
        self._tree.heading("description", text="Description")
        self._tree.column("name", width=180)
        self._tree.column("provider", width=90)
        self._tree.column("voicebox_id", width=180)
        self._tree.column("tags", width=140)
        self._tree.column("description", width=260)
        self._tree.pack(fill="both", expand=True)

        self._data = {"voices": []}

    def on_show(self) -> None:
        self._data = self.config_manager.load("voice_library", {"voices": []})
        self._refresh_tree()

    def _refresh_tree(self) -> None:
        self._tree.delete(*self._tree.get_children())
        for voice in self._data.get("voices", []):
            tags = ", ".join(voice.get("tags", []))
            self._tree.insert(
                "",
                "end",
                iid=voice["id"],
                values=(
                    voice.get("name", ""),
                    voice.get("provider", ""),
                    voice.get("voicebox_id", ""),
                    tags,
                    voice.get("description", ""),
                ),
            )

    def _selected_voice(self) -> dict | None:
        selection = self._tree.selection()
        if not selection:
            return None
        voice_id = selection[0]
        for voice in self._data.get("voices", []):
            if voice["id"] == voice_id:
                return voice
        return None

    def _open_editor(self, voice: dict | None = None) -> dict | None:
        dialog = ttk.Toplevel(self)
        dialog.title("Voice")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        dialog.geometry("520x360")

        form = ttk.Frame(dialog, padding=20)
        form.pack(fill="both", expand=True)

        entries: dict[str, ttk.Entry] = {}
        labels = (
            ("name", "Name"),
            ("provider", "Provider"),
            ("voicebox_id", "Voicebox ID"),
            ("tags", "Tags (comma-separated)"),
            ("description", "Description"),
        )
        for row, (key, label) in enumerate(labels):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", pady=6)
            entry = ttk.Entry(form, width=42)
            entry.grid(row=row, column=1, sticky="ew", pady=6)
            entries[key] = entry
            if voice:
                if key == "tags":
                    entry.insert(0, ", ".join(voice.get("tags", [])))
                else:
                    entry.insert(0, voice.get(key, ""))

        form.columnconfigure(1, weight=1)
        result: dict | None = {}

        def save_and_close() -> None:
            name = entries["name"].get().strip()
            voicebox_id = entries["voicebox_id"].get().strip()
            if not name or not voicebox_id:
                Messagebox.show_warning("Name and Voicebox ID are required.", "Validation")
                return
            tags = [tag.strip() for tag in entries["tags"].get().split(",") if tag.strip()]
            result.clear()
            result.update(
                {
                    "name": name,
                    "provider": entries["provider"].get().strip() or "voicebox",
                    "voicebox_id": voicebox_id,
                    "tags": tags,
                    "description": entries["description"].get().strip(),
                }
            )
            dialog.destroy()

        buttons = ttk.Frame(dialog, padding=(20, 0, 20, 20))
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Cancel", bootstyle="secondary", command=dialog.destroy).pack(side="right")
        ttk.Button(buttons, text="OK", bootstyle="primary", command=save_and_close).pack(side="right", padx=8)

        dialog.wait_window()
        return result if result else None

    def _add_voice(self) -> None:
        edited = self._open_editor()
        if not edited:
            return
        voice = {"id": f"vb-{uuid.uuid4().hex[:8]}", **edited}
        self._data.setdefault("voices", []).append(voice)
        self._refresh_tree()
        self.set_status(f"Added voice '{voice['name']}'")

    def _edit_voice(self) -> None:
        voice = self._selected_voice()
        if not voice:
            Messagebox.show_info("Select a voice to edit.", "Voice Library")
            return
        edited = self._open_editor(voice)
        if not edited:
            return
        voice.update(edited)
        self._refresh_tree()
        self.set_status(f"Updated voice '{voice['name']}'")

    def _remove_voice(self) -> None:
        voice = self._selected_voice()
        if not voice:
            Messagebox.show_info("Select a voice to remove.", "Voice Library")
            return
        confirmed = Messagebox.yesno(f"Remove voice '{voice.get('name', '')}'?", "Confirm Remove")
        if confirmed != "Yes":
            return
        self._data["voices"] = [item for item in self._data.get("voices", []) if item["id"] != voice["id"]]
        self._refresh_tree()
        self.set_status(f"Removed voice '{voice.get('name', '')}'")

    def _save(self) -> None:
        self.config_manager.save("voice_library", self._data)
        self.set_status("Voice library configuration saved")

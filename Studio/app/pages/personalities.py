"""Personalities management page."""

from __future__ import annotations

import shutil
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog

import ttkbootstrap as ttk
from PIL import Image, ImageTk
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.scrolled import ScrolledFrame

from app.core.paths import personality_images_dir, studio_root, writable_assets_dir
from app.core.personality_model import (
    display_label,
    formats_from_string,
    formats_to_string,
    new_personality_id,
    normalize_personalities_data,
    normalize_personality,
    validate_personality,
)
from app.pages.base_page import BasePage
from app.ui.theme import StudioTheme


class PersonalitiesPage(BasePage):
    page_id = "personalities"
    page_title = "Personalities"
    page_subtitle = "Manage on-air personality profiles for Studio configuration"

    def build(self) -> None:
        self._data: dict = {"personalities": []}
        self._selected_id: str | None = None
        self._autosave_job: str | None = None
        self._loading_form = False
        self._photo_image: ImageTk.PhotoImage | None = None
        self._field_vars: dict[str, tk.Variable] = {}
        self._text_widgets: dict[str, tk.Text] = {}
        self._entry_widgets: list[ttk.Entry] = []

        toolbar = ttk.Frame(self._body, style="Studio.TFrame")
        toolbar.pack(fill="x", pady=(0, 12))
        ttk.Button(toolbar, text="Add Personality", bootstyle="success", command=self._add_personality).pack(
            side="left"
        )
        ttk.Button(toolbar, text="Delete Personality", bootstyle="danger", command=self._delete_personality).pack(
            side="left", padx=8
        )
        ttk.Button(toolbar, text="Save Now", bootstyle="primary", command=self._save_now).pack(side="right")

        panes = ttk.Panedwindow(self._body, orient="horizontal", bootstyle="secondary")
        panes.pack(fill="both", expand=True)

        list_panel = ttk.Labelframe(
            panes,
            text="Personalities",
            style="StudioCard.TLabelframe",
            padding=12,
        )
        panes.add(list_panel, weight=1)

        columns = ("display_name", "show_name", "active")
        self._tree = ttk.Treeview(
            list_panel,
            columns=columns,
            show="headings",
            bootstyle="info",
            height=18,
            selectmode="browse",
        )
        self._tree.heading("display_name", text="Display Name")
        self._tree.heading("show_name", text="Show Name")
        self._tree.heading("active", text="Active")
        self._tree.column("display_name", width=150)
        self._tree.column("show_name", width=150)
        self._tree.column("active", width=70, anchor="center")
        self._tree.pack(fill="both", expand=True)
        self._tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        editor_panel = ttk.Labelframe(
            panes,
            text="Personality Details",
            style="StudioCard.TLabelframe",
            padding=12,
        )
        panes.add(editor_panel, weight=3)

        header = ttk.Frame(editor_panel, style="StudioPanel.TFrame")
        header.pack(fill="x", pady=(0, 12))

        self._picture_frame = ttk.Frame(header, style="StudioPanel.TFrame", width=120, height=120)
        self._picture_frame.pack(side="left")
        self._picture_frame.pack_propagate(False)
        self._picture_label = ttk.Label(
            self._picture_frame,
            text="No Photo",
            style="StudioMuted.TLabel",
            anchor="center",
        )
        self._picture_label.pack(fill="both", expand=True)

        picture_actions = ttk.Frame(header, style="StudioPanel.TFrame")
        picture_actions.pack(side="left", padx=16, anchor="n")
        ttk.Button(
            picture_actions,
            text="Upload Picture",
            bootstyle="info",
            command=self._upload_picture,
        ).pack(anchor="w")
        ttk.Button(
            picture_actions,
            text="Remove Picture",
            bootstyle="secondary",
            command=self._remove_picture,
        ).pack(anchor="w", pady=(8, 0))
        self._picture_path_label = ttk.Label(
            picture_actions,
            text="",
            style="StudioMuted.TLabel",
            wraplength=260,
        )
        self._picture_path_label.pack(anchor="w", pady=(12, 0))

        scroll = ScrolledFrame(editor_panel, autohide=True, bootstyle="secondary")
        scroll.pack(fill="both", expand=True)
        form = scroll.container

        self._active_var = tk.BooleanVar(value=True)
        self._field_vars = {
            "display_name": tk.StringVar(),
            "show_name": tk.StringVar(),
            "voicebox_voice_id": tk.StringVar(),
            "radiodj_cart_id": tk.StringVar(),
            "wav_output_path": tk.StringVar(),
            "prompt_file": tk.StringVar(),
            "air_staff_folder": tk.StringVar(),
            "music_formats": tk.StringVar(),
        }

        row = 0
        row = self._add_entry_row(form, row, "Display Name", "display_name", required=True)
        row = self._add_entry_row(form, row, "Show Name", "show_name")
        row = self._add_entry_row(form, row, "Voicebox Voice ID", "voicebox_voice_id", required=True)
        row = self._add_entry_row(form, row, "RadioDJ Cart ID", "radiodj_cart_id")
        row = self._add_path_row(form, row, "WAV Output Path", "wav_output_path", file_mode=False)
        row = self._add_path_row(form, row, "Prompt File", "prompt_file", file_mode=True)
        row = self._add_path_row(form, row, "Air Staff Folder", "air_staff_folder", file_mode=False, directory=True)

        ttk.Checkbutton(
            form,
            text="Active",
            variable=self._active_var,
            command=self._on_field_changed,
        ).grid(row=row, column=0, columnspan=3, sticky="w", pady=(8, 4))
        row += 1

        row = self._add_text_row(form, row, "Bio", "bio", height=4)
        row = self._add_text_row(form, row, "Personality Description", "personality_description", height=4)
        row = self._add_text_row(form, row, "Voice Description", "voice_description", height=3)
        row = self._add_entry_row(
            form,
            row,
            "Music Formats",
            "music_formats",
            help_text="Comma-separated (e.g. Classic Rock, Jazz)",
        )

        form.columnconfigure(1, weight=1)
        self._set_form_enabled(False)

    def on_show(self) -> None:
        loaded = self.config_manager.load("personalities", {"personalities": []})
        self._data = normalize_personalities_data(loaded)
        self._refresh_tree()
        if self._data["personalities"]:
            first_id = self._data["personalities"][0]["id"]
            self._tree.selection_set(first_id)
            self._tree.focus(first_id)
            self._load_personality(first_id)
        else:
            self._selected_id = None
            self._clear_form()
            self._set_form_enabled(False)

    def _add_entry_row(
        self,
        parent: ttk.Frame,
        row: int,
        label: str,
        key: str,
        *,
        required: bool = False,
        help_text: str = "",
    ) -> int:
        label_text = f"{label} *" if required else label
        ttk.Label(parent, text=label_text, style="StudioCard.TLabel").grid(
            row=row, column=0, sticky="nw", padx=(0, 12), pady=6
        )
        entry = ttk.Entry(parent, textvariable=self._field_vars[key], width=48)
        entry.grid(row=row, column=1, sticky="ew", pady=6)
        entry.bind("<KeyRelease>", self._on_field_changed)
        self._entry_widgets.append(entry)
        if help_text:
            ttk.Label(parent, text=help_text, style="StudioMuted.TLabel").grid(
                row=row, column=2, sticky="w", padx=(8, 0), pady=6
            )
        return row + 1

    def _add_path_row(
        self,
        parent: ttk.Frame,
        row: int,
        label: str,
        key: str,
        *,
        file_mode: bool,
        directory: bool = False,
    ) -> int:
        ttk.Label(parent, text=label, style="StudioCard.TLabel").grid(
            row=row, column=0, sticky="nw", padx=(0, 12), pady=6
        )
        entry = ttk.Entry(parent, textvariable=self._field_vars[key], width=48)
        entry.grid(row=row, column=1, sticky="ew", pady=6)
        entry.bind("<KeyRelease>", self._on_field_changed)
        self._entry_widgets.append(entry)
        ttk.Button(
            parent,
            text="Browse",
            bootstyle="secondary",
            command=lambda k=key, f=file_mode, d=directory: self._browse_path(k, file_mode=f, directory=d),
        ).grid(row=row, column=2, sticky="w", padx=(8, 0), pady=6)
        return row + 1

    def _add_text_row(self, parent: ttk.Frame, row: int, label: str, key: str, *, height: int) -> int:
        ttk.Label(parent, text=label, style="StudioCard.TLabel").grid(
            row=row, column=0, sticky="nw", padx=(0, 12), pady=6
        )
        text = tk.Text(
            parent,
            height=height,
            wrap="word",
            bg=StudioTheme.BG_PANEL,
            fg=StudioTheme.TEXT_PRIMARY,
            insertbackground=StudioTheme.TEXT_PRIMARY,
            relief="flat",
            highlightthickness=1,
            highlightbackground=StudioTheme.BORDER,
            highlightcolor=StudioTheme.ACCENT,
            font=("Segoe UI", 10),
        )
        text.grid(row=row, column=1, columnspan=2, sticky="ew", pady=6)
        text.bind("<KeyRelease>", self._on_field_changed)
        self._text_widgets[key] = text
        return row + 1

    def _set_form_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for entry in self._entry_widgets:
            entry.configure(state=state)
        for widget in self._text_widgets.values():
            widget.configure(state=state)

    def _selected_personality(self) -> dict | None:
        if not self._selected_id:
            return None
        for personality in self._data.get("personalities", []):
            if personality["id"] == self._selected_id:
                return personality
        return None

    def _refresh_tree(self) -> None:
        selected = self._selected_id
        self._tree.delete(*self._tree.get_children())
        for personality in self._data.get("personalities", []):
            self._tree.insert(
                "",
                "end",
                iid=personality["id"],
                values=(
                    display_label(personality),
                    personality.get("show_name", ""),
                    "Yes" if personality.get("active", True) else "No",
                ),
            )
        if selected and self._tree.exists(selected):
            self._tree.selection_set(selected)
            self._tree.focus(selected)

    def _on_tree_select(self, _event=None) -> None:
        if self._loading_form:
            return
        selection = self._tree.selection()
        if not selection:
            return
        self._apply_form_to_selected()
        self._load_personality(selection[0])

    def _load_personality(self, personality_id: str) -> None:
        personality = next(
            (item for item in self._data.get("personalities", []) if item["id"] == personality_id),
            None,
        )
        if not personality:
            return

        self._loading_form = True
        self._selected_id = personality_id
        self._field_vars["display_name"].set(personality.get("display_name", ""))
        self._field_vars["show_name"].set(personality.get("show_name", ""))
        self._field_vars["voicebox_voice_id"].set(personality.get("voicebox_voice_id", ""))
        self._field_vars["radiodj_cart_id"].set(personality.get("radiodj_cart_id", ""))
        self._field_vars["wav_output_path"].set(personality.get("wav_output_path", ""))
        self._field_vars["prompt_file"].set(personality.get("prompt_file", ""))
        self._field_vars["air_staff_folder"].set(personality.get("air_staff_folder", ""))
        self._field_vars["music_formats"].set(formats_to_string(personality.get("music_formats", [])))
        self._active_var.set(personality.get("active", True))

        for key, widget in self._text_widgets.items():
            widget.delete("1.0", "end")
            widget.insert("1.0", personality.get(key, ""))

        self._update_picture_preview(personality.get("picture", ""))
        self._set_form_enabled(True)
        self._loading_form = False
        self.set_status(f"Editing {display_label(personality)}")

    def _clear_form(self) -> None:
        self._loading_form = True
        for var in self._field_vars.values():
            var.set("")
        self._active_var.set(True)
        for widget in self._text_widgets.values():
            widget.delete("1.0", "end")
        self._update_picture_preview("")
        self._loading_form = False

    def _apply_form_to_selected(self) -> bool:
        personality = self._selected_personality()
        if not personality:
            return False

        personality.update(
            {
                "display_name": self._field_vars["display_name"].get().strip(),
                "show_name": self._field_vars["show_name"].get().strip(),
                "voicebox_voice_id": self._field_vars["voicebox_voice_id"].get().strip(),
                "radiodj_cart_id": self._field_vars["radiodj_cart_id"].get().strip(),
                "wav_output_path": self._field_vars["wav_output_path"].get().strip(),
                "prompt_file": self._field_vars["prompt_file"].get().strip(),
                "air_staff_folder": self._field_vars["air_staff_folder"].get().strip(),
                "music_formats": formats_from_string(self._field_vars["music_formats"].get()),
                "active": self._active_var.get(),
                "bio": self._text_widgets["bio"].get("1.0", "end").strip(),
                "personality_description": self._text_widgets["personality_description"].get("1.0", "end").strip(),
                "voice_description": self._text_widgets["voice_description"].get("1.0", "end").strip(),
                "updated": datetime.now().isoformat(timespec="seconds"),
            }
        )
        self._refresh_tree()
        return True

    def _on_field_changed(self, _event=None) -> None:
        if self._loading_form or not self._selected_id:
            return
        self._apply_form_to_selected()
        self._schedule_autosave()

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
        personality = self._selected_personality()
        if not personality:
            return
        errors = validate_personality(personality)
        if errors:
            return
        self.config_manager.save("personalities", self._data)
        self.set_status("Personalities saved automatically")

    def _save_now(self) -> None:
        if self._selected_id and not self._apply_form_to_selected():
            return
        if self._selected_id:
            personality = self._selected_personality()
            if personality:
                errors = validate_personality(personality)
                if errors:
                    Messagebox.show_warning("\n".join(errors), "Validation")
                    return
        self.config_manager.save("personalities", self._data)
        self.set_status("Personalities saved")

    def _add_personality(self) -> None:
        self._apply_form_to_selected()
        now = datetime.now().isoformat(timespec="seconds")
        personality = normalize_personality(
            {
                "id": new_personality_id(),
                "display_name": "New Personality",
                "show_name": "",
                "voicebox_voice_id": "",
                "created": now,
                "updated": now,
            }
        )
        self._data.setdefault("personalities", []).append(personality)
        self.config_manager.save("personalities", self._data)
        self._refresh_tree()
        self._tree.selection_set(personality["id"])
        self._tree.focus(personality["id"])
        self._load_personality(personality["id"])
        self.set_status("Added new personality")

    def _delete_personality(self) -> None:
        personality = self._selected_personality()
        if not personality:
            Messagebox.show_info("Select a personality to delete.", "Personalities")
            return
        confirmed = Messagebox.yesno(
            f"Delete personality '{display_label(personality)}'?",
            "Confirm Delete",
        )
        if confirmed != "Yes":
            return

        picture_path = self._resolve_picture_path(personality.get("picture", ""))
        if picture_path and picture_path.exists():
            picture_path.unlink(missing_ok=True)

        self._data["personalities"] = [
            item for item in self._data.get("personalities", []) if item["id"] != personality["id"]
        ]
        self._selected_id = None
        self.config_manager.save("personalities", self._data)
        self._refresh_tree()
        if self._data["personalities"]:
            next_id = self._data["personalities"][0]["id"]
            self._tree.selection_set(next_id)
            self._load_personality(next_id)
        else:
            self._clear_form()
            self._set_form_enabled(False)
        self.set_status(f"Deleted personality '{display_label(personality)}'")

    def _resolve_picture_path(self, picture: str) -> Path | None:
        if not picture:
            return None
        path = Path(picture)
        if path.is_absolute():
            return path
        return studio_root() / "assets" / picture

    def _picture_relative_path(self, absolute_path: Path) -> str:
        assets_root = writable_assets_dir()
        try:
            return str(absolute_path.relative_to(assets_root)).replace("\\", "/")
        except ValueError:
            return str(absolute_path)

    def _update_picture_preview(self, picture: str) -> None:
        self._photo_image = None
        path = self._resolve_picture_path(picture)
        if path and path.exists():
            image = Image.open(path)
            image.thumbnail((112, 112), Image.Resampling.LANCZOS)
            self._photo_image = ImageTk.PhotoImage(image)
            self._picture_label.configure(image=self._photo_image, text="")
            display_path = picture.replace("\\", "/")
            self._picture_path_label.configure(text=display_path)
        else:
            self._picture_label.configure(image="", text="No Photo")
            self._picture_path_label.configure(text="")

    def _upload_picture(self) -> None:
        personality = self._selected_personality()
        if not personality:
            Messagebox.show_info("Select a personality first.", "Personalities")
            return

        source = filedialog.askopenfilename(
            title="Select Personality Picture",
            filetypes=[
                ("Image files", "*.png;*.jpg;*.jpeg;*.gif;*.webp"),
                ("All files", "*.*"),
            ],
        )
        if not source:
            return

        source_path = Path(source)
        suffix = source_path.suffix.lower() or ".png"
        destination = personality_images_dir() / f"{personality['id']}{suffix}"
        shutil.copy2(source_path, destination)

        personality["picture"] = self._picture_relative_path(destination)
        personality["updated"] = datetime.now().isoformat(timespec="seconds")
        self._update_picture_preview(personality["picture"])
        self.config_manager.save("personalities", self._data)
        self.set_status("Personality picture updated")

    def _remove_picture(self) -> None:
        personality = self._selected_personality()
        if not personality:
            return
        path = self._resolve_picture_path(personality.get("picture", ""))
        if path and path.exists():
            path.unlink(missing_ok=True)
        personality["picture"] = ""
        personality["updated"] = datetime.now().isoformat(timespec="seconds")
        self._update_picture_preview("")
        self.config_manager.save("personalities", self._data)
        self.set_status("Personality picture removed")

    def _browse_path(self, key: str, *, file_mode: bool, directory: bool = False) -> None:
        if directory:
            selected = filedialog.askdirectory(title=f"Select {key.replace('_', ' ').title()}")
        elif file_mode:
            selected = filedialog.askopenfilename(
                title=f"Select {key.replace('_', ' ').title()}",
                filetypes=[("All files", "*.*")],
            )
        else:
            selected = filedialog.asksaveasfilename(
                title=f"Select {key.replace('_', ' ').title()}",
                defaultextension=".wav",
                filetypes=[("WAV files", "*.wav"), ("All files", "*.*")],
            )
        if selected:
            self._field_vars[key].set(selected)
            self._on_field_changed()

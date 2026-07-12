"""Voice library management page."""

from __future__ import annotations

import shutil
import tkinter as tk
from pathlib import Path
from tkinter import filedialog

import ttkbootstrap as ttk
from PIL import Image, ImageTk
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.scrolled import ScrolledFrame

from app.core.background_tasks import run_in_background
from app.core.paths import voice_portraits_dir, writable_assets_dir
from app.core.personality_model import display_label as personality_label
from app.core.voice_library_loader import VoiceLibraryLoadResult, load_voice_library_page_data
from app.core.voice_model import (
    display_label,
    new_voice_id,
    normalize_voice,
    specialties_from_string,
    specialties_to_string,
    validate_voice,
)
from app.core.voice_portrait_cache import (
    get_thumbnail,
    invalidate_path,
    resolve_voice_portrait_path,
    warm_thumbnail,
)
from app.pages.base_page import BasePage
from app.ui.theme import StudioTheme


class VoiceLibraryPage(BasePage):
    page_id = "voice_library"
    page_title = "Voice Library"
    page_subtitle = "Manage Voicebox voices and station voice assignments"

    def build(self) -> None:
        self._data: dict = {"voices": []}
        self._personalities: list[dict] = []
        self._selected_id: str | None = None
        self._autosave_job: str | None = None
        self._loading_form = False
        self._photo_image: ImageTk.PhotoImage | None = None
        self._field_vars: dict[str, tk.Variable] = {}
        self._text_widgets: dict[str, tk.Text] = {}
        self._entry_widgets: list[ttk.Entry] = []
        self._load_generation = 0
        self._load_in_progress = False

        toolbar = ttk.Frame(self._body, style="Studio.TFrame")
        toolbar.pack(fill="x", pady=(0, 12))
        self._loading_label = ttk.Label(toolbar, text="", style="StudioMuted.TLabel")
        self._loading_label.pack(side="left", padx=(0, 12))
        ttk.Button(toolbar, text="Add Voice", bootstyle="success", command=self._add_voice).pack(side="left")
        ttk.Button(toolbar, text="Delete Voice", bootstyle="danger", command=self._delete_voice).pack(
            side="left", padx=8
        )
        ttk.Button(toolbar, text="Save Now", bootstyle="primary", command=self._save_now).pack(side="right")

        panes = ttk.Panedwindow(self._body, orient="horizontal", bootstyle="secondary")
        panes.pack(fill="both", expand=True)

        list_panel = ttk.Labelframe(
            panes,
            text="Voices",
            style="StudioCard.TLabelframe",
            padding=12,
        )
        panes.add(list_panel, weight=1)

        columns = ("display_name", "voicebox_id", "active")
        self._tree = ttk.Treeview(
            list_panel,
            columns=columns,
            show="headings",
            bootstyle="info",
            height=18,
            selectmode="browse",
        )
        self._tree.heading("display_name", text="Display Name")
        self._tree.heading("voicebox_id", text="Voicebox ID")
        self._tree.heading("active", text="Active")
        self._tree.column("display_name", width=150)
        self._tree.column("voicebox_id", width=130)
        self._tree.column("active", width=70, anchor="center")
        self._tree.pack(fill="both", expand=True)
        self._tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        editor_panel = ttk.Labelframe(
            panes,
            text="Voice Details",
            style="StudioCard.TLabelframe",
            padding=12,
        )
        panes.add(editor_panel, weight=3)

        header = ttk.Frame(editor_panel, style="StudioPanel.TFrame")
        header.pack(fill="x", pady=(0, 12))

        self._portrait_frame = ttk.Frame(header, style="StudioPanel.TFrame", width=120, height=120)
        self._portrait_frame.pack(side="left")
        self._portrait_frame.pack_propagate(False)
        self._portrait_label = ttk.Label(
            self._portrait_frame,
            text="No Portrait",
            style="StudioMuted.TLabel",
            anchor="center",
        )
        self._portrait_label.pack(fill="both", expand=True)

        portrait_actions = ttk.Frame(header, style="StudioPanel.TFrame")
        portrait_actions.pack(side="left", padx=16, anchor="n")
        ttk.Button(
            portrait_actions,
            text="Upload Portrait",
            bootstyle="info",
            command=self._upload_portrait,
        ).pack(anchor="w")
        ttk.Button(
            portrait_actions,
            text="Remove Portrait",
            bootstyle="secondary",
            command=self._remove_portrait,
        ).pack(anchor="w", pady=(8, 0))
        self._portrait_path_label = ttk.Label(
            portrait_actions,
            text="",
            style="StudioMuted.TLabel",
            wraplength=260,
        )
        self._portrait_path_label.pack(anchor="w", pady=(12, 0))

        scroll = ScrolledFrame(editor_panel, autohide=True, bootstyle="secondary")
        scroll.pack(fill="both", expand=True)
        form = scroll.container

        self._active_var = tk.BooleanVar(value=True)
        self._field_vars = {
            "display_name": tk.StringVar(),
            "voicebox_id": tk.StringVar(),
            "personality_id": tk.StringVar(),
            "genre_specialties": tk.StringVar(),
            "default_shift": tk.StringVar(),
        }

        row = 0
        row = self._add_entry_row(form, row, "Display Name", "display_name", required=True)
        row = self._add_entry_row(form, row, "Voicebox ID", "voicebox_id", required=True)

        ttk.Label(form, text="Personality Assignment", style="StudioCard.TLabel").grid(
            row=row, column=0, sticky="w", padx=(0, 12), pady=6
        )
        self._personality_combo = ttk.Combobox(form, textvariable=self._field_vars["personality_id"], width=46)
        self._personality_combo.grid(row=row, column=1, sticky="ew", pady=6)
        self._personality_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_field_changed())
        self._entry_widgets.append(self._personality_combo)
        row += 1

        ttk.Checkbutton(
            form,
            text="Active",
            variable=self._active_var,
            command=self._on_field_changed,
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=(8, 4))
        row += 1

        row = self._add_text_row(form, row, "Voice Description", "voice_description", height=3)
        row = self._add_text_row(form, row, "Default Greeting", "default_greeting", height=3)
        row = self._add_text_row(form, row, "Default Closing", "default_closing", height=3)
        row = self._add_text_row(form, row, "Personality Prompt", "personality_prompt", height=4)
        row = self._add_text_row(form, row, "Pronunciation Notes", "pronunciation_notes", height=3)
        row = self._add_entry_row(
            form,
            row,
            "Genre Specialties",
            "genre_specialties",
            help_text="Comma-separated (e.g. Classic Rock, Jazz)",
        )
        row = self._add_entry_row(form, row, "Default Shift", "default_shift")

        form.columnconfigure(1, weight=1)
        self._set_form_enabled(False)

    def on_show(self) -> None:
        self._begin_background_load()

    def on_hide(self) -> None:
        self._load_generation += 1
        self._load_in_progress = False
        self._show_loading(False)

    def _begin_background_load(self) -> None:
        self._load_generation += 1
        generation = self._load_generation
        self._load_in_progress = True
        self._show_loading(True)
        self._set_form_enabled(False)

        personalities_path = self.config_manager.path_for("personalities")
        voice_library_path = self.config_manager.path_for("voice_library")

        def work() -> VoiceLibraryLoadResult:
            return load_voice_library_page_data(personalities_path, voice_library_path)

        def complete(result: VoiceLibraryLoadResult) -> None:
            if generation != self._load_generation:
                return
            self._load_in_progress = False
            self._apply_loaded_data(result)
            self._show_loading(False)

        def failed(error: Exception) -> None:
            if generation != self._load_generation:
                return
            self._load_in_progress = False
            self._show_loading(False)
            self._data = {"voices": []}
            self._personalities = []
            self._refresh_tree()
            self._clear_form()
            self._set_form_enabled(False)
            self.set_status(f"Voice Library load failed: {error}")

        run_in_background(self, work, complete, on_error=failed)

    def _show_loading(self, active: bool) -> None:
        self._loading_label.configure(text="Loading voices…" if active else "")

    def _apply_loaded_data(self, result: VoiceLibraryLoadResult) -> None:
        self._personalities = result.personalities
        self._data = result.voices_data
        self.config_manager._cache["personalities"] = {
            "personalities": result.personalities,
        }
        self.config_manager._cache["voice_library"] = result.voices_data
        self._update_personality_combo_values()
        self._refresh_tree()

        if result.load_errors:
            self.set_status("; ".join(result.load_errors))
        elif result.portrait_errors:
            self.set_status("Voice library loaded with some portrait warnings")
        else:
            self.set_status(
                f"Voice library loaded ({len(self._data.get('voices', []))} voices)"
            )

        if self._data.get("voices"):
            first_id = self._data["voices"][0]["id"]
            self._tree.selection_set(first_id)
            self._tree.focus(first_id)
            self._load_voice(first_id)
        else:
            self._selected_id = None
            self._clear_form()
            self._set_form_enabled(False)

    def _personality_options(self) -> list[tuple[str, str]]:
        options = [("", "Unassigned")]
        for personality in self._personalities:
            options.append((personality["id"], personality_label(personality)))
        return options

    def _update_personality_combo_values(self) -> None:
        labels = [label for _pid, label in self._personality_options()]
        self._personality_combo.configure(values=labels)

    def _personality_id_for_label(self, label: str) -> str:
        for personality_id, personality_name in self._personality_options():
            if personality_name == label:
                return personality_id
        return ""

    def _personality_label_for_id(self, personality_id: str) -> str:
        for pid, label in self._personality_options():
            if pid == personality_id:
                return label
        return "Unassigned"

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

    def _selected_voice(self) -> dict | None:
        if not self._selected_id:
            return None
        for voice in self._data.get("voices", []):
            if voice["id"] == self._selected_id:
                return voice
        return None

    def _refresh_tree(self) -> None:
        selected = self._selected_id
        self._tree.delete(*self._tree.get_children())
        for voice in self._data.get("voices", []):
            self._tree.insert(
                "",
                "end",
                iid=voice["id"],
                values=(
                    display_label(voice),
                    voice.get("voicebox_id", ""),
                    "Yes" if voice.get("active", True) else "No",
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
        self._load_voice(selection[0])

    def _load_voice(self, voice_id: str) -> None:
        voice = next((item for item in self._data.get("voices", []) if item["id"] == voice_id), None)
        if not voice:
            return

        self._loading_form = True
        self._selected_id = voice_id
        self._field_vars["display_name"].set(voice.get("display_name", ""))
        self._field_vars["voicebox_id"].set(voice.get("voicebox_id", ""))
        self._field_vars["personality_id"].set(self._personality_label_for_id(voice.get("personality_id", "")))
        self._field_vars["genre_specialties"].set(specialties_to_string(voice.get("genre_specialties", [])))
        self._field_vars["default_shift"].set(voice.get("default_shift", ""))
        self._active_var.set(voice.get("active", True))

        for key, widget in self._text_widgets.items():
            widget.delete("1.0", "end")
            widget.insert("1.0", voice.get(key, ""))

        self._update_portrait_preview(voice.get("portrait", ""))
        self._set_form_enabled(True)
        self._loading_form = False
        self.set_status(f"Editing {display_label(voice)}")

    def _clear_form(self) -> None:
        self._loading_form = True
        for var in self._field_vars.values():
            var.set("")
        self._field_vars["personality_id"].set("Unassigned")
        self._active_var.set(True)
        for widget in self._text_widgets.values():
            widget.delete("1.0", "end")
        self._update_portrait_preview("")
        self._loading_form = False

    def _apply_form_to_selected(self) -> bool:
        voice = self._selected_voice()
        if not voice:
            return False

        voice.update(
            {
                "display_name": self._field_vars["display_name"].get().strip(),
                "voicebox_id": self._field_vars["voicebox_id"].get().strip(),
                "personality_id": self._personality_id_for_label(self._field_vars["personality_id"].get()),
                "genre_specialties": specialties_from_string(self._field_vars["genre_specialties"].get()),
                "default_shift": self._field_vars["default_shift"].get().strip(),
                "active": self._active_var.get(),
                "voice_description": self._text_widgets["voice_description"].get("1.0", "end").strip(),
                "default_greeting": self._text_widgets["default_greeting"].get("1.0", "end").strip(),
                "default_closing": self._text_widgets["default_closing"].get("1.0", "end").strip(),
                "personality_prompt": self._text_widgets["personality_prompt"].get("1.0", "end").strip(),
                "pronunciation_notes": self._text_widgets["pronunciation_notes"].get("1.0", "end").strip(),
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
        voice = self._selected_voice()
        if not voice:
            return
        errors = validate_voice(voice)
        if errors:
            return
        self.config_manager.save("voice_library", self._data)
        self.set_status("Voice library saved automatically")

    def _save_now(self) -> None:
        if self._selected_id and not self._apply_form_to_selected():
            return
        if self._selected_id:
            voice = self._selected_voice()
            if voice:
                errors = validate_voice(voice)
                if errors:
                    Messagebox.show_warning("\n".join(errors), "Validation")
                    return
        self.config_manager.save("voice_library", self._data)
        self.set_status("Voice library saved")

    def _add_voice(self) -> None:
        self._apply_form_to_selected()
        voice = normalize_voice(
            {
                "id": new_voice_id(),
                "display_name": "New Voice",
                "voicebox_id": "",
            }
        )
        self._data.setdefault("voices", []).append(voice)
        self.config_manager.save("voice_library", self._data)
        self._refresh_tree()
        self._tree.selection_set(voice["id"])
        self._tree.focus(voice["id"])
        self._load_voice(voice["id"])
        self.set_status("Added new voice")

    def _delete_voice(self) -> None:
        voice = self._selected_voice()
        if not voice:
            Messagebox.show_info("Select a voice to delete.", "Voice Library")
            return
        confirmed = Messagebox.yesno(f"Delete voice '{display_label(voice)}'?", "Confirm Delete")
        if confirmed != "Yes":
            return

        portrait_path = self._resolve_portrait_path(voice.get("portrait", ""))
        if portrait_path and portrait_path.exists():
            portrait_path.unlink(missing_ok=True)

        self._data["voices"] = [item for item in self._data.get("voices", []) if item["id"] != voice["id"]]
        self._selected_id = None
        self.config_manager.save("voice_library", self._data)
        self._refresh_tree()
        if self._data["voices"]:
            next_id = self._data["voices"][0]["id"]
            self._tree.selection_set(next_id)
            self._load_voice(next_id)
        else:
            self._clear_form()
            self._set_form_enabled(False)
        self.set_status(f"Deleted voice '{display_label(voice)}'")

    def _resolve_portrait_path(self, portrait: str) -> Path | None:
        return resolve_voice_portrait_path(portrait)

    def _portrait_relative_path(self, absolute_path: Path) -> str:
        assets_root = writable_assets_dir()
        try:
            return str(absolute_path.relative_to(assets_root)).replace("\\", "/")
        except ValueError:
            return str(absolute_path)

    def _apply_portrait_image(self, portrait: str, thumb: Image.Image) -> None:
        self._photo_image = ImageTk.PhotoImage(thumb)
        self._portrait_label.configure(image=self._photo_image, text="")
        self._portrait_path_label.configure(text=portrait.replace("\\", "/"))

    def _update_portrait_preview(self, portrait: str) -> None:
        self._photo_image = None
        if not portrait:
            self._portrait_label.configure(image="", text="No Portrait")
            self._portrait_path_label.configure(text="")
            return

        path = self._resolve_portrait_path(portrait)
        if path is None or not path.exists():
            self._portrait_label.configure(image="", text="No Portrait")
            self._portrait_path_label.configure(text=portrait.replace("\\", "/"))
            return

        thumb = get_thumbnail(path)
        if thumb is not None:
            self._apply_portrait_image(portrait, thumb)
            return

        self._portrait_label.configure(image="", text="Loading…")
        self._portrait_path_label.configure(text=portrait.replace("\\", "/"))
        generation = self._load_generation

        def work() -> tuple[str, Path]:
            warm_thumbnail(path)
            return portrait, path

        def complete(payload: tuple[str, Path]) -> None:
            if generation != self._load_generation:
                return
            current = self._selected_voice()
            if not current or current.get("portrait", "") != payload[0]:
                return
            cached = get_thumbnail(payload[1])
            if cached is not None:
                self._apply_portrait_image(payload[0], cached)
            else:
                self._portrait_label.configure(image="", text="No Portrait")

        def failed(_error: Exception) -> None:
            if generation != self._load_generation:
                return
            self._portrait_label.configure(image="", text="No Portrait")

        run_in_background(self, work, complete, on_error=failed)

    def _upload_portrait(self) -> None:
        voice = self._selected_voice()
        if not voice:
            Messagebox.show_info("Select a voice first.", "Voice Library")
            return

        source = filedialog.askopenfilename(
            title="Select Voice Portrait",
            filetypes=[
                ("Image files", "*.png;*.jpg;*.jpeg;*.gif;*.webp"),
                ("All files", "*.*"),
            ],
        )
        if not source:
            return

        source_path = Path(source)
        suffix = source_path.suffix.lower() or ".png"
        destination = voice_portraits_dir() / f"{voice['id']}{suffix}"
        shutil.copy2(source_path, destination)
        invalidate_path(destination)

        voice["portrait"] = self._portrait_relative_path(destination)
        self._update_portrait_preview(voice["portrait"])
        self.config_manager.save("voice_library", self._data)
        self.set_status("Voice portrait updated")

    def _remove_portrait(self) -> None:
        voice = self._selected_voice()
        if not voice:
            return
        path = self._resolve_portrait_path(voice.get("portrait", ""))
        if path and path.exists():
            path.unlink(missing_ok=True)
            invalidate_path(path)
        voice["portrait"] = ""
        self._update_portrait_preview("")
        self.config_manager.save("voice_library", self._data)
        self.set_status("Voice portrait removed")

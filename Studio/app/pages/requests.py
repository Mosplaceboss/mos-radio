"""Request settings management page."""

from __future__ import annotations

import tkinter as tk

import ttkbootstrap as ttk
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.scrolled import ScrolledFrame

from app.core.personality_model import normalize_personalities_data
from app.core.requests_model import (
    COOLDOWN_PRESETS,
    REQUEST_MODES,
    collect_available_formats,
    effective_cooldown_hours,
    normalize_requests_data,
    request_mode_label,
    specialty_shows_from_schedule,
    validate_requests_settings,
)
from app.core.schedule_model import TIME_OPTIONS, normalize_schedule_data
from app.core.publish_manager import import_requests_from_live, integration_bundle, publish_requests, restore_requests_backup
from app.pages.base_page import BasePage
from app.ui.confirm_dialog import confirm_action
from app.ui.theme import StudioTheme


class RequestsPage(BasePage):
    page_id = "requests"
    page_title = "Requests"
    page_subtitle = "Configure listener request rules for the Requests automation engine"

    def build(self) -> None:
        self._data: dict = {}
        self._autosave_job: str | None = None
        self._loading_form = False
        self._format_vars: dict[str, tk.BooleanVar] = {}

        toolbar = ttk.Frame(self._body, style="Studio.TFrame")
        toolbar.pack(fill="x", pady=(0, 12))
        ttk.Button(toolbar, text="Import from Request System", bootstyle="secondary", command=self._import_live).pack(
            side="left"
        )
        ttk.Button(toolbar, text="Test Settings", bootstyle="info", command=self._test_settings).pack(side="left", padx=8)
        ttk.Button(toolbar, text="Reload", bootstyle="secondary", command=self._load).pack(side="left", padx=8)
        ttk.Button(toolbar, text="Restore Last Backup", bootstyle="warning", command=self._restore_live).pack(side="right")
        ttk.Button(toolbar, text="Publish to Request System", bootstyle="primary", command=self._publish_live).pack(
            side="right", padx=8
        )
        ttk.Button(toolbar, text="Save Now", bootstyle="secondary", command=self._save_now).pack(side="right", padx=8)

        scroll = ScrolledFrame(self._body, autohide=True, bootstyle="secondary")
        scroll.pack(fill="both", expand=True)
        content = scroll.container

        general = ttk.Labelframe(content, text="Request Mode", style="StudioCard.TLabelframe", padding=16)
        general.pack(fill="x", pady=(0, 12))
        self._request_mode = tk.StringVar(value="by_schedule")
        self._intro_enabled = tk.BooleanVar(value=True)

        for index, (mode_id, label) in enumerate(REQUEST_MODES):
            ttk.Radiobutton(
                general,
                text=label,
                value=mode_id,
                variable=self._request_mode,
                command=self._on_request_mode_changed,
            ).grid(row=index, column=0, sticky="w", pady=4)

        self._mode_help = ttk.Label(
            general,
            text="",
            style="StudioMuted.TLabel",
            wraplength=760,
        )
        self._mode_help.grid(row=len(REQUEST_MODES), column=0, sticky="w", pady=(8, 0))

        ttk.Checkbutton(
            general,
            text="Intro Announcement On",
            variable=self._intro_enabled,
            command=self._on_field_changed,
        ).grid(row=len(REQUEST_MODES) + 1, column=0, sticky="w", pady=(12, 4))

        limits = ttk.Labelframe(content, text="Listener Limits", style="StudioCard.TLabelframe", padding=16)
        limits.pack(fill="x", pady=(0, 12))

        ttk.Label(limits, text="Requests Per Listener", style="StudioCard.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 12), pady=6
        )
        self._requests_per_listener = tk.IntVar(value=3)
        ttk.Spinbox(limits, from_=1, to=100, textvariable=self._requests_per_listener, width=10).grid(
            row=0, column=1, sticky="w", pady=6
        )
        self._requests_per_listener.trace_add("write", lambda *_: self._on_field_changed())

        ttk.Label(limits, text="Cooldown", style="StudioCard.TLabel").grid(
            row=1, column=0, sticky="nw", padx=(0, 12), pady=6
        )
        cooldown_frame = ttk.Frame(limits, style="StudioPanel.TFrame")
        cooldown_frame.grid(row=1, column=1, sticky="ew", pady=6)

        self._cooldown_preset = tk.StringVar(value="2")
        preset_labels = [label for _id, label, _hours in COOLDOWN_PRESETS]
        for index, (preset_id, label, _hours) in enumerate(COOLDOWN_PRESETS):
            ttk.Radiobutton(
                cooldown_frame,
                text=label,
                value=preset_id,
                variable=self._cooldown_preset,
                command=self._on_cooldown_preset_changed,
            ).grid(row=index // 3, column=index % 3, sticky="w", padx=(0, 16), pady=2)

        custom_row = ttk.Frame(cooldown_frame, style="StudioPanel.TFrame")
        custom_row.grid(row=3, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Label(custom_row, text="Custom value (hours)", style="StudioMuted.TLabel").pack(side="left")
        self._cooldown_custom = tk.IntVar(value=2)
        self._custom_spinbox = ttk.Spinbox(custom_row, from_=1, to=168, textvariable=self._cooldown_custom, width=8)
        self._custom_spinbox.pack(side="left", padx=8)
        self._cooldown_custom.trace_add("write", lambda *_: self._on_field_changed())

        hours = ttk.Labelframe(content, text="Request Hours", style="StudioCard.TLabelframe", padding=16)
        hours.pack(fill="x", pady=(0, 12))
        self._hours_panel = hours
        ttk.Label(hours, text="Opening Time", style="StudioCard.TLabel").grid(row=0, column=0, sticky="w", pady=6)
        self._opening_time = tk.StringVar(value="06:00")
        self._opening_combo = ttk.Combobox(hours, textvariable=self._opening_time, values=list(TIME_OPTIONS), width=12)
        self._opening_combo.grid(row=0, column=1, sticky="w", pady=6, padx=(12, 0))
        self._opening_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_field_changed())

        ttk.Label(hours, text="Closing Time", style="StudioCard.TLabel").grid(row=1, column=0, sticky="w", pady=6)
        self._closing_time = tk.StringVar(value="23:00")
        self._closing_combo = ttk.Combobox(hours, textvariable=self._closing_time, values=list(TIME_OPTIONS), width=12)
        self._closing_combo.grid(row=1, column=1, sticky="w", pady=6, padx=(12, 0))
        self._closing_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_field_changed())

        queue = ttk.Labelframe(content, text="Queue", style="StudioCard.TLabelframe", padding=16)
        queue.pack(fill="x", pady=(0, 12))
        ttk.Label(queue, text="Maximum Active Requests in Queue", style="StudioCard.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 12), pady=6
        )
        self._max_queue = tk.IntVar(value=50)
        ttk.Spinbox(queue, from_=1, to=500, textvariable=self._max_queue, width=10).grid(row=0, column=1, sticky="w")
        self._max_queue.trace_add("write", lambda *_: self._on_field_changed())

        formats_panel = ttk.Labelframe(content, text="Allow Requests By Format", style="StudioCard.TLabelframe", padding=16)
        formats_panel.pack(fill="x", pady=(0, 12))
        self._formats_frame = ttk.Frame(formats_panel, style="StudioPanel.TFrame")
        self._formats_frame.pack(fill="x")

        specialty = ttk.Labelframe(
            content,
            text="Specialty Shows",
            style="StudioCard.TLabelframe",
            padding=16,
        )
        specialty.pack(fill="x", pady=(0, 12))
        self._specialty_panel = specialty
        self._disable_specialty = tk.BooleanVar(value=True)
        self._specialty_checkbox = ttk.Checkbutton(
            specialty,
            text="Disable requests during specialty shows (schedule blocks marked Requests Off)",
            variable=self._disable_specialty,
            command=self._on_field_changed,
        )
        self._specialty_checkbox.pack(anchor="w")
        self._specialty_list = ttk.Label(
            specialty,
            text="",
            style="StudioMuted.TLabel",
            wraplength=760,
            justify="left",
        )
        self._specialty_list.pack(anchor="w", pady=(8, 0))

        messages = ttk.Labelframe(content, text="Listener Messages", style="StudioCard.TLabelframe", padding=16)
        messages.pack(fill="x", pady=(0, 12))

        ttk.Label(messages, text="Email Shown When Song Isn't Found", style="StudioCard.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 12), pady=6
        )
        self._not_found_email = tk.StringVar()
        email_entry = ttk.Entry(messages, textvariable=self._not_found_email, width=48)
        email_entry.grid(row=0, column=1, sticky="ew", pady=6)
        email_entry.bind("<KeyRelease>", lambda _e: self._on_field_changed())

        ttk.Label(messages, text="Message When Request Limit Reached", style="StudioCard.TLabel").grid(
            row=1, column=0, sticky="nw", padx=(0, 12), pady=6
        )
        self._limit_message = tk.Text(
            messages,
            height=3,
            wrap="word",
            bg=StudioTheme.BG_PANEL,
            fg=StudioTheme.TEXT_PRIMARY,
            insertbackground=StudioTheme.TEXT_PRIMARY,
            relief="flat",
            highlightthickness=1,
            highlightbackground=StudioTheme.BORDER,
            font=("Segoe UI", 10),
        )
        self._limit_message.grid(row=1, column=1, sticky="ew", pady=6)
        self._limit_message.bind("<KeyRelease>", lambda _e: self._on_field_changed())
        messages.columnconfigure(1, weight=1)

        info = ttk.Labelframe(content, text="Automation Integration", style="StudioCard.TLabelframe", padding=16)
        info.pack(fill="x")
        ttk.Label(
            info,
            text=(
                "Settings are written to Studio/config/requests.json. "
                "The Requests automation engine can consume this file when integration is enabled."
            ),
            style="StudioCard.TLabel",
            wraplength=760,
        ).pack(anchor="w")

    def on_show(self) -> None:
        self._load()

    def _load(self) -> None:
        self._loading_form = True
        loaded = self.config_manager.load("requests", {})
        self._data = normalize_requests_data(loaded)
        self._populate_form(self._data)
        self._loading_form = False
        self.set_status("Request settings loaded")

    def _populate_form(self, data: dict) -> None:
        self._request_mode.set(data.get("request_mode", "by_schedule"))
        self._intro_enabled.set(data.get("intro_announcement_enabled", True))
        self._requests_per_listener.set(data.get("requests_per_listener", 3))
        self._cooldown_preset.set(data.get("cooldown_preset", "2"))
        self._cooldown_custom.set(int(data.get("cooldown_custom_hours", 2)))
        self._opening_time.set(data.get("opening_time", "06:00"))
        self._closing_time.set(data.get("closing_time", "23:00"))
        self._max_queue.set(data.get("max_active_queue", 50))
        self._disable_specialty.set(data.get("disable_during_specialty_shows", True))
        self._not_found_email.set(data.get("song_not_found_email", ""))

        self._limit_message.delete("1.0", "end")
        self._limit_message.insert("1.0", data.get("limit_reached_message", ""))

        self._render_format_checkboxes(data.get("allowed_formats", []))
        self._render_specialty_shows()
        self._update_custom_cooldown_state()
        self._update_request_mode_state()

    def _mode_help_text(self, mode: str) -> str:
        if mode == "24_7":
            return "Requests are accepted around the clock. Daily opening and closing times are ignored."
        if mode == "disabled":
            return "All listener requests are turned off."
        return "Requests follow daily opening/closing times and schedule blocks marked Requests Off."

    def _update_request_mode_state(self) -> None:
        mode = self._request_mode.get()
        self._mode_help.configure(text=self._mode_help_text(mode))

        if mode == "disabled":
            hours_state = "disabled"
            specialty_state = "disabled"
        elif mode == "24_7":
            hours_state = "disabled"
            specialty_state = "normal"
        else:
            hours_state = "normal"
            specialty_state = "normal"

        for widget in (self._opening_combo, self._closing_combo):
            widget.configure(state=hours_state)
        self._specialty_checkbox.configure(state=specialty_state)

    def _on_request_mode_changed(self) -> None:
        self._update_request_mode_state()
        self._on_field_changed()

    def _render_format_checkboxes(self, selected_formats: list[str]) -> None:
        for child in self._formats_frame.winfo_children():
            child.destroy()
        self._format_vars.clear()

        personalities = normalize_personalities_data(
            self.config_manager.load("personalities", {"personalities": []})
        ).get("personalities", [])
        schedule = normalize_schedule_data(
            self.config_manager.load("schedule", {"slots": []}),
            [item["id"] for item in personalities],
        ).get("slots", [])
        available = collect_available_formats(personalities, schedule)

        if not available:
            ttk.Label(
                self._formats_frame,
                text="No music formats found. Add formats in Personalities or Schedule first.",
                style="StudioMuted.TLabel",
                wraplength=720,
            ).pack(anchor="w")
            return

        for index, fmt in enumerate(available):
            var = tk.BooleanVar(value=fmt in selected_formats)
            self._format_vars[fmt] = var
            ttk.Checkbutton(
                self._formats_frame,
                text=fmt,
                variable=var,
                command=self._on_field_changed,
            ).grid(row=index // 3, column=index % 3, sticky="w", padx=(0, 20), pady=4)

    def _render_specialty_shows(self) -> None:
        personalities = normalize_personalities_data(
            self.config_manager.load("personalities", {"personalities": []})
        ).get("personalities", [])
        schedule = normalize_schedule_data(
            self.config_manager.load("schedule", {"slots": []}),
            [item["id"] for item in personalities],
        ).get("slots", [])
        blocked = specialty_shows_from_schedule(schedule)
        if not blocked:
            self._specialty_list.configure(text="No specialty show blocks are currently marked Requests Off in Schedule.")
            return
        lines = [
            f"• {show['show_name']} — {show['day'].title()} {show['start_time']}–{show['end_time']}"
            for show in blocked
        ]
        self._specialty_list.configure(text="\n".join(lines))

    def _update_custom_cooldown_state(self) -> None:
        is_custom = self._cooldown_preset.get() == "custom"
        state = "normal" if is_custom else "disabled"
        self._custom_spinbox.configure(state=state)

    def _on_cooldown_preset_changed(self) -> None:
        self._update_custom_cooldown_state()
        self._on_field_changed()

    def _collect_data(self) -> dict:
        allowed_formats = [fmt for fmt, var in self._format_vars.items() if var.get()]
        data = {
            "request_mode": self._request_mode.get(),
            "requests_per_listener": int(self._requests_per_listener.get()),
            "cooldown_preset": self._cooldown_preset.get(),
            "cooldown_custom_hours": int(self._cooldown_custom.get()),
            "opening_time": self._opening_time.get(),
            "closing_time": self._closing_time.get(),
            "max_active_queue": int(self._max_queue.get()),
            "allowed_formats": allowed_formats,
            "disable_during_specialty_shows": self._disable_specialty.get(),
            "intro_announcement_enabled": self._intro_enabled.get(),
            "song_not_found_email": self._not_found_email.get().strip(),
            "limit_reached_message": self._limit_message.get("1.0", "end").strip(),
        }
        return normalize_requests_data(data)

    def _on_field_changed(self) -> None:
        if self._loading_form:
            return
        self._data = self._collect_data()
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
        data = self._collect_data()
        errors, _warnings = validate_requests_settings(data)
        if errors:
            return
        self.config_manager.save("requests", data)
        self._data = data
        self.set_status("Request settings saved automatically")

    def _save_now(self) -> None:
        data = self._collect_data()
        errors, _warnings = validate_requests_settings(data)
        if errors:
            Messagebox.show_warning("\n".join(errors), "Validation")
            return
        self.config_manager.save("requests", data)
        self._data = data
        self.set_status("Request settings saved")

    def _test_settings(self) -> None:
        data = self._collect_data()
        errors, warnings = validate_requests_settings(data)
        cooldown = effective_cooldown_hours(data)
        lines = [
            "Request Settings Test",
            "",
            f"Request mode: {request_mode_label(data.get('request_mode', 'by_schedule'))}",
            f"Requests per listener: {data.get('requests_per_listener')}",
            f"Cooldown: {cooldown} hour(s)",
        ]
        if data.get("request_mode") == "by_schedule":
            lines.append(f"Hours: {data.get('opening_time')} – {data.get('closing_time')}")
        elif data.get("request_mode") == "24_7":
            lines.append("Hours: 24/7 (daily window not used)")
        else:
            lines.append("Hours: Not applicable (requests disabled)")
        lines.extend(
            [
                f"Max queue: {data.get('max_active_queue')}",
                f"Allowed formats: {len(data.get('allowed_formats', []))}",
                f"Specialty show blocking: {'On' if data.get('disable_during_specialty_shows') else 'Off'}",
                "",
            ]
        )
        if errors:
            lines.append("Errors:")
            lines.extend(f"• {error}" for error in errors)
            lines.append("")
        if warnings:
            lines.append("Warnings:")
            lines.extend(f"• {warning}" for warning in warnings)
            lines.append("")
        if not errors:
            lines.append("Configuration is valid.")
        else:
            lines.append("Configuration needs attention.")

        if errors:
            Messagebox.show_error("\n".join(lines), "Test Settings")
            self.set_status("Request settings test failed")
        elif warnings:
            Messagebox.show_warning("\n".join(lines), "Test Settings")
            self.set_status("Request settings test passed with warnings")
        else:
            Messagebox.show_info("\n".join(lines), "Test Settings")
            self.set_status("Request settings test passed")

    def _settings(self) -> dict:
        return self.config_manager.load("settings", {})

    def _integration(self) -> dict:
        return integration_bundle(self._settings())

    def _import_live(self) -> None:
        if not confirm_action(
            "Import from Request System",
            "Import live request settings into Studio development config?",
            self._settings(),
        ):
            return
        ok, message = import_requests_from_live(self._integration())
        if ok:
            self.config_manager._cache.pop("requests", None)
            self._load()
            Messagebox.show_info(message, "Import Requests")
        else:
            Messagebox.show_warning(message, "Import Requests")
        self.set_status(message)

    def _publish_live(self) -> None:
        data = self._collect_data()
        errors, warnings = validate_requests_settings(data)
        if errors:
            Messagebox.show_error("\n".join(errors), "Cannot Publish")
            return
        if warnings and not confirm_action(
            "Publish with Warnings",
            "Validation warnings were found.\nPublish anyway?\n\n" + "\n".join(warnings[:6]),
            self._settings(),
        ):
            return
        if not confirm_action(
            "Publish to Request System",
            "Publish request settings to the live request path?\n"
            "A timestamped backup will be created first.",
            self._settings(),
        ):
            return
        ok, message = publish_requests(self.config_manager, self._integration())
        if ok:
            Messagebox.show_info(message, "Publish Requests")
        else:
            Messagebox.show_error(message, "Publish Requests")
        self.set_status(message)

    def _restore_live(self) -> None:
        if not confirm_action(
            "Restore Last Backup",
            "Restore the most recent request backup to the live request path?",
            self._settings(),
        ):
            return
        ok, message = restore_requests_backup(self._integration())
        if ok:
            Messagebox.show_info(message, "Restore Requests Backup")
        else:
            Messagebox.show_warning(message, "Restore Requests Backup")
        self.set_status(message)

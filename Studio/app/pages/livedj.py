"""LiveDJ integration — import, validate, publish, and restore."""

from __future__ import annotations

import tkinter as tk

import ttkbootstrap as ttk
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.scrolled import ScrolledText

from app.core.integration_settings import livedj_live_paths
from app.core.livedj_integration import import_livedj_from_live, validate_livedj_bundle
from app.core.publish_manager import integration_bundle, publish_livedj, restore_livedj_backup
from app.core.studio_info import environment_mode
from app.pages.base_page import BasePage
from app.ui.confirm_dialog import confirm_action


class LiveDJPage(BasePage):
    page_id = "livedj"
    page_title = "LiveDJ"
    page_subtitle = "Import, edit in Studio, validate, and publish LiveDJ configuration safely"

    def build(self) -> None:
        toolbar = ttk.Frame(self._body, style="Studio.TFrame")
        toolbar.pack(fill="x", pady=(0, 12))
        ttk.Button(toolbar, text="Import from LiveDJ", bootstyle="secondary", command=self._import_live).pack(
            side="left"
        )
        ttk.Button(toolbar, text="Validate", bootstyle="info", command=self._validate).pack(side="left", padx=8)
        ttk.Button(toolbar, text="Publish to LiveDJ", bootstyle="primary", command=self._publish).pack(side="right")
        ttk.Button(toolbar, text="Restore Last Backup", bootstyle="warning", command=self._restore).pack(
            side="right", padx=8
        )

        paths = ttk.Labelframe(self._body, text="Configuration Paths", style="StudioCard.TLabelframe", padding=16)
        paths.pack(fill="x", pady=(0, 12))
        self._paths_text = ttk.Label(paths, text="", style="StudioMuted.TLabel", justify="left")
        self._paths_text.pack(anchor="w")

        workflow = ttk.Labelframe(self._body, text="Safe Workflow", style="StudioCard.TLabelframe", padding=16)
        workflow.pack(fill="x", pady=(0, 12))
        for line in (
            "1. Import reads the live LiveDJ copy into Studio/config (development workspace).",
            "2. Edit personalities, voice library, and schedule in their Studio pages.",
            "3. Validate checks voice IDs, cart IDs, WAV paths, and schedule conflicts.",
            "4. Publish copies Studio/config to live paths after automatic timestamped backup.",
            "The LiveDJ engine itself is never rewritten by Studio.",
        ):
            ttk.Label(workflow, text=line, style="StudioCard.TLabel", wraplength=760).pack(anchor="w", pady=2)

        nav = ttk.Frame(self._body, style="Studio.TFrame")
        nav.pack(fill="x", pady=(0, 12))
        for page_id, label in (
            ("personalities", "Open Personalities"),
            ("schedule", "Open Schedule"),
            ("voice_library", "Open Voice Library"),
        ):
            ttk.Button(nav, text=label, bootstyle="secondary", command=lambda pid=page_id: self._open_page(pid)).pack(
                side="left", padx=(0, 8)
            )

        validation = ttk.Labelframe(self._body, text="Validation", style="StudioCard.TLabelframe", padding=16)
        validation.pack(fill="both", expand=True)
        self._validation_box = ScrolledText(validation, height=12, autohide=True, bootstyle="secondary", font=("Consolas", 9))
        self._validation_box.pack(fill="both", expand=True)

    def on_show(self) -> None:
        self._refresh_paths()
        self._validate(quiet=True)

    def _settings(self) -> dict:
        return self.config_manager.load("settings", {})

    def _integration(self) -> dict:
        return integration_bundle(self._settings())

    def _refresh_paths(self) -> None:
        settings = self._settings()
        live = livedj_live_paths(self._integration())
        lines = [
            f"Mode: {environment_mode(settings)}",
            f"Development config: Studio/config/",
            f"Live personalities: {live['personalities']}",
            f"Live schedule: {live['schedule']}",
            f"Live voice library: {live['voice_library']}",
        ]
        self._paths_text.configure(text="\n".join(lines))

    def _open_page(self, page_id: str) -> None:
        if self.on_navigate:
            self.on_navigate(page_id)

    def _import_live(self) -> None:
        if not confirm_action(
            "Import from LiveDJ",
            "Import live LiveDJ configuration into Studio development config?\n"
            "This overwrites Studio/config personalities, schedule, and voice library.",
            self._settings(),
        ):
            return
        ok, message, _imported = import_livedj_from_live(self._integration())
        if ok:
            self.config_manager._cache.pop("personalities", None)
            self.config_manager._cache.pop("schedule", None)
            self.config_manager._cache.pop("voice_library", None)
            Messagebox.show_info(message, "Import from LiveDJ")
            self.set_status(message)
            self._validate(quiet=True)
        else:
            Messagebox.show_warning(message, "Import from LiveDJ")
            self.set_status(message)

    def _validate(self, *, quiet: bool = False) -> None:
        errors = validate_livedj_bundle(self.config_manager)
        self._validation_box.delete("1.0", "end")
        if errors:
            self._validation_box.insert("end", "\n".join(errors))
            if not quiet:
                Messagebox.show_warning(f"{len(errors)} issue(s) found.", "LiveDJ Validation")
                self.set_status("LiveDJ validation found issues")
        else:
            self._validation_box.insert("end", "LiveDJ configuration is valid and ready to publish.")
            if not quiet:
                Messagebox.show_info("LiveDJ configuration is valid.", "LiveDJ Validation")
                self.set_status("LiveDJ validation passed")

    def _publish(self) -> None:
        errors = validate_livedj_bundle(self.config_manager)
        if errors:
            Messagebox.show_error("\n".join(errors[:10]), "Cannot Publish")
            return
        if not confirm_action(
            "Publish to LiveDJ",
            "Publish Studio development config to live LiveDJ paths?\n"
            "A timestamped backup of the current live files will be created first.",
            self._settings(),
        ):
            return
        ok, message = publish_livedj(self.config_manager, self._integration())
        if ok:
            Messagebox.show_info(message, "Publish to LiveDJ")
        else:
            Messagebox.show_error(message, "Publish to LiveDJ")
        self.set_status(message)

    def _restore(self) -> None:
        if not confirm_action(
            "Restore Last Backup",
            "Restore the most recent LiveDJ backup to live paths?",
            self._settings(),
        ):
            return
        ok, message = restore_livedj_backup(self._integration())
        if ok:
            Messagebox.show_info(message, "Restore LiveDJ Backup")
        else:
            Messagebox.show_warning(message, "Restore LiveDJ Backup")
        self.set_status(message)

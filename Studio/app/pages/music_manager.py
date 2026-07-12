"""Music Manager — station music library control center."""

from __future__ import annotations

import tkinter as tk
from copy import deepcopy
from datetime import datetime
from typing import Any

import ttkbootstrap as ttk
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.scrolled import ScrolledText

from app.core.background_tasks import run_in_background
from app.core.music_model import (
    build_library_overview,
    build_music_dashboard,
    build_report_lines,
    format_bytes,
    format_duration,
    normalize_bundle,
    scan_music_library,
    validate_music,
)
from app.core.music_storage import load_music_bundle, save_music_bundle
from app.core.platform_manager import platform_path
from app.pages.base_page import BasePage

REPORT_OPTIONS = (
    ("songs_by_format", "Songs by Format"),
    ("songs_by_genre", "Songs by Genre"),
    ("songs_by_year", "Songs by Year"),
    ("duplicate_songs", "Duplicate Songs"),
    ("missing_artwork", "Missing Artwork"),
    ("missing_metadata", "Missing Metadata"),
)


class MusicManagerPage(BasePage):
    page_id = "music_manager"
    page_title = "Music Manager"
    page_subtitle = "Browse, organize, and validate your station music library"
    page_help = (
        "Manage the station music library from Studio. Audio files are read-only in Version 1 — "
        "catalog, playlists, and categories are stored in your platform StationData folder."
    )

    def build(self) -> None:
        self._bundle = normalize_bundle({})
        self._busy = False
        self._scan_in_progress = False
        self._selected_song_id: str | None = None
        self._selected_playlist_id: str | None = None
        self._search_var = tk.StringVar()
        self._filter_genre_var = tk.StringVar(value="All Genres")
        self._filter_format_var = tk.StringVar(value="All Formats")
        self._filter_category_var = tk.StringVar(value="All Categories")
        self._dashboard_labels: dict[str, ttk.Label] = {}
        self._overview_labels: dict[str, ttk.Label] = {}
        self._report_text: ScrolledText | None = None

        toolbar = ttk.Frame(self._body, style="Studio.TFrame")
        toolbar.pack(fill="x", pady=(0, 12))
        ttk.Button(
            toolbar,
            text="Save Music Data",
            style="StudioAction.TButton",
            bootstyle="primary",
            command=self._save,
        ).pack(side="right")
        ttk.Button(
            toolbar,
            text="Validate",
            style="StudioAction.TButton",
            bootstyle="info",
            command=self._run_validation,
        ).pack(side="right", padx=8)
        ttk.Button(
            toolbar,
            text="Scan Library",
            style="StudioAction.TButton",
            bootstyle="success",
            command=self._scan_library,
        ).pack(side="right", padx=8)
        ttk.Button(toolbar, text="Reload", bootstyle="secondary", command=self._load).pack(side="left")

        self._notebook = ttk.Notebook(self._body, bootstyle="primary")
        self._notebook.pack(fill="both", expand=True)
        self._build_dashboard_tab()
        self._build_overview_tab()
        self._build_browser_tab()
        self._build_formats_tab()
        self._build_playlists_tab()
        self._build_categories_tab()
        self._build_resources_tab()
        self._build_validation_tab()
        self._build_reports_tab()
        self._build_settings_tab()

    def on_show(self) -> None:
        self._load()

    def _load(self) -> None:
        self._bundle = normalize_bundle(load_music_bundle(self.config_manager), self.config_manager)
        self._refresh_all_views()
        self.set_status("Music data loaded")

    def _save(self) -> None:
        if self._busy:
            return
        self._busy = True
        payload = deepcopy(self._bundle)

        def work() -> None:
            save_music_bundle(payload, self.config_manager)

        def complete(_: None) -> None:
            self._busy = False
            self.set_status("Music data saved")

        def failed(error: Exception) -> None:
            self._busy = False
            self._show_error_dialog("Save Music Data", str(error))

        self.set_status("Saving music data…")
        run_in_background(self, work, lambda _: complete(None), on_error=failed)

    def _scan_library(self) -> None:
        if self._scan_in_progress:
            return
        self._scan_in_progress = True
        music_root = self._bundle["settings"].get("music_root", r"W:\Music")
        existing = deepcopy(self._bundle["catalog"])

        def work() -> dict[str, Any]:
            return scan_music_library(music_root, existing)

        def complete(catalog: dict[str, Any]) -> None:
            self._scan_in_progress = False
            self._bundle["catalog"] = catalog
            self._bundle["settings"]["last_scan_at"] = catalog.get("last_scan_at", "")
            self._refresh_all_views()
            count = len([s for s in catalog["songs"] if not s.get("missing_file")])
            self.set_status(f"Library scan complete — {count} songs indexed")

        def failed(error: Exception) -> None:
            self._scan_in_progress = False
            self._show_error_dialog("Scan Library", str(error))

        self.set_status("Scanning music library (read-only)…")
        run_in_background(self, work, complete, on_error=failed)

    def _run_validation(self) -> None:
        warnings = validate_music(self._bundle)
        self._bundle["state"]["last_validated"] = datetime.now().strftime("%Y-%m-%d %I:%M %p")
        self._refresh_validation_tab(warnings)
        self._refresh_dashboard(warnings)
        self.set_status("Music validation complete")

    def _refresh_all_views(self) -> None:
        warnings = validate_music(self._bundle)
        self._refresh_dashboard(warnings)
        self._refresh_overview()
        self._refresh_browser()
        self._refresh_formats()
        self._refresh_playlists()
        self._refresh_categories()
        self._refresh_resources()
        self._refresh_validation_tab(warnings)
        self._refresh_settings()

    @staticmethod
    def _set_scroll_text(widget: ScrolledText, content: str) -> None:
        widget.text.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("end", content)
        widget.text.configure(state="disabled")

    def _build_dashboard_tab(self) -> None:
        tab = ttk.Frame(self._notebook, style="Studio.TFrame", padding=12)
        self._notebook.add(tab, text="Dashboard")
        grid = ttk.Frame(tab, style="Studio.TFrame")
        grid.pack(fill="x")
        specs = (
            ("total_library_size", "Total Library Size"),
            ("new_music", "New Music"),
            ("missing_files", "Missing Files"),
            ("duplicate_files", "Duplicate Files"),
        )
        for index, (key, title) in enumerate(specs):
            card = ttk.Labelframe(grid, text=title, style="StudioCard.TLabelframe", padding=12)
            card.grid(row=0, column=index, sticky="nsew", padx=8, pady=8)
            label = ttk.Label(card, text="—", style="StudioMetric.TLabel", wraplength=200, justify="left")
            label.pack(anchor="w")
            self._dashboard_labels[key] = label
            grid.columnconfigure(index, weight=1)

        recent = ttk.Labelframe(tab, text="Recently Added", style="StudioCard.TLabelframe", padding=12)
        recent.pack(fill="both", expand=True, pady=(12, 0))
        self._recent_text = ScrolledText(
            recent, height=10, autohide=True, bootstyle="secondary", state="disabled", wrap="word"
        )
        self._recent_text.pack(fill="both", expand=True)

    def _refresh_dashboard(self, warnings: list[str] | None = None) -> None:
        dashboard = build_music_dashboard(self._bundle, warnings)
        self._dashboard_labels["total_library_size"].configure(text=dashboard.total_library_size)
        self._dashboard_labels["new_music"].configure(text=str(dashboard.new_music))
        self._dashboard_labels["missing_files"].configure(text=str(dashboard.missing_files))
        self._dashboard_labels["duplicate_files"].configure(text=str(dashboard.duplicate_files))
        self._set_scroll_text(self._recent_text, "\n".join(dashboard.recently_added))

    def _build_overview_tab(self) -> None:
        tab = ttk.Frame(self._notebook, style="Studio.TFrame", padding=12)
        self._notebook.add(tab, text="Library Overview")
        grid = ttk.Frame(tab, style="Studio.TFrame")
        grid.pack(fill="x")
        specs = (
            ("total_songs", "Total Songs"),
            ("total_artists", "Total Artists"),
            ("total_albums", "Total Albums"),
            ("total_genres", "Total Genres"),
            ("total_playlists", "Total Playlists"),
            ("storage_used", "Storage Used"),
        )
        for index, (key, title) in enumerate(specs):
            card = ttk.Labelframe(grid, text=title, style="StudioCard.TLabelframe", padding=12)
            card.grid(row=index // 3, column=index % 3, sticky="nsew", padx=8, pady=8)
            label = ttk.Label(card, text="—", style="StudioMetric.TLabel")
            label.pack(anchor="w")
            self._overview_labels[key] = label
            grid.columnconfigure(index % 3, weight=1)

        info = ttk.Labelframe(tab, text="Library Status", style="StudioCard.TLabelframe", padding=12)
        info.pack(fill="x", pady=(16, 0))
        self._overview_status = ttk.Label(info, text="", style="StudioCard.TLabel", wraplength=900, justify="left")
        self._overview_status.pack(anchor="w")

    def _refresh_overview(self) -> None:
        overview = build_library_overview(self._bundle)
        self._overview_labels["total_songs"].configure(text=str(overview.total_songs))
        self._overview_labels["total_artists"].configure(text=str(overview.total_artists))
        self._overview_labels["total_albums"].configure(text=str(overview.total_albums))
        self._overview_labels["total_genres"].configure(text=str(overview.total_genres))
        self._overview_labels["total_playlists"].configure(text=str(overview.total_playlists))
        self._overview_labels["storage_used"].configure(text=overview.storage_used)
        root = self._bundle["settings"].get("music_root", r"W:\Music")
        scan_at = self._bundle["catalog"].get("last_scan_at", "Never")
        self._overview_status.configure(
            text=f"Music root: {root}\nLast scan: {scan_at}\nRead-only management — no changes are written to RadioDJ."
        )

    def _build_browser_tab(self) -> None:
        tab = ttk.Frame(self._notebook, style="Studio.TFrame", padding=12)
        self._notebook.add(tab, text="Library Browser")
        filters = ttk.Frame(tab, style="Studio.TFrame")
        filters.pack(fill="x", pady=(0, 8))
        ttk.Label(filters, text="Search", style="StudioMuted.TLabel").pack(side="left")
        search_entry = ttk.Entry(filters, textvariable=self._search_var, width=28)
        search_entry.pack(side="left", padx=(6, 12))
        self._search_var.trace_add("write", lambda *_: self._refresh_browser())
        ttk.Label(filters, text="Genre", style="StudioMuted.TLabel").pack(side="left")
        self._genre_filter = ttk.Combobox(filters, textvariable=self._filter_genre_var, width=16, state="readonly")
        self._genre_filter.pack(side="left", padx=(6, 12))
        self._genre_filter.bind("<<ComboboxSelected>>", lambda _e: self._refresh_browser())
        ttk.Label(filters, text="Format", style="StudioMuted.TLabel").pack(side="left")
        self._format_filter = ttk.Combobox(filters, textvariable=self._filter_format_var, width=16, state="readonly")
        self._format_filter.pack(side="left", padx=(6, 12))
        self._format_filter.bind("<<ComboboxSelected>>", lambda _e: self._refresh_browser())
        ttk.Label(filters, text="Category", style="StudioMuted.TLabel").pack(side="left")
        self._category_filter = ttk.Combobox(filters, textvariable=self._filter_category_var, width=16, state="readonly")
        self._category_filter.pack(side="left", padx=(6, 0))
        self._category_filter.bind("<<ComboboxSelected>>", lambda _e: self._refresh_browser())

        panes = ttk.Panedwindow(tab, orient="horizontal", bootstyle="secondary")
        panes.pack(fill="both", expand=True)
        list_panel = ttk.Labelframe(panes, text="Songs", style="StudioCard.TLabelframe", padding=8)
        panes.add(list_panel, weight=2)
        self._browser_tree = ttk.Treeview(
            list_panel,
            columns=("artist", "title", "album", "year", "genre", "length"),
            show="headings",
            bootstyle="info",
            height=16,
        )
        for col, heading, width in (
            ("artist", "Artist", 140),
            ("title", "Title", 160),
            ("album", "Album", 130),
            ("year", "Year", 60),
            ("genre", "Genre", 100),
            ("length", "Length", 70),
        ):
            self._browser_tree.heading(col, text=heading)
            self._browser_tree.column(col, width=width)
        self._browser_tree.pack(fill="both", expand=True)
        self._browser_tree.bind("<<TreeviewSelect>>", self._on_song_select)

        detail = ttk.Labelframe(panes, text="Song Details", style="StudioCard.TLabelframe", padding=12)
        panes.add(detail, weight=1)
        self._song_detail = ScrolledText(detail, height=18, autohide=True, bootstyle="secondary", state="disabled", wrap="word")
        self._song_detail.pack(fill="both", expand=True)

    def _filtered_songs(self) -> list[dict[str, Any]]:
        songs = self._bundle["catalog"]["songs"]
        query = self._search_var.get().strip().lower()
        genre = self._filter_genre_var.get()
        format_name = self._filter_format_var.get()
        category_name = self._filter_category_var.get()

        format_by_id = {item["id"]: item["name"] for item in self._bundle["formats"]["formats"]}
        category_by_id = {item["id"]: item["name"] for item in self._bundle["categories"]["categories"]}
        format_by_name = {item["name"]: item["id"] for item in self._bundle["formats"]["formats"]}
        category_by_name = {item["id"]: item["name"] for item in self._bundle["categories"]["categories"]}

        filtered = []
        for song in songs:
            if query:
                haystack = " ".join(
                    [
                        song.get("artist", ""),
                        song.get("title", ""),
                        song.get("album", ""),
                        song.get("genre", ""),
                        song.get("file_path", ""),
                    ]
                ).lower()
                if query not in haystack:
                    continue
            if genre != "All Genres" and song.get("genre", "") != genre:
                continue
            if format_name != "All Formats":
                format_id = format_by_name.get(format_name, "")
                if format_id not in song.get("format_ids", []):
                    continue
            if category_name != "All Categories":
                category_id = next(
                    (cid for cid, name in category_by_name.items() if name == category_name),
                    "",
                )
                if category_id not in song.get("category_ids", []):
                    continue
            filtered.append(song)
        return filtered

    def _refresh_browser(self) -> None:
        songs = self._bundle["catalog"]["songs"]
        genres = sorted({song.get("genre", "").strip() or "Unknown" for song in songs})
        self._genre_filter.configure(values=["All Genres", *genres])
        format_names = [item["name"] for item in self._bundle["formats"]["formats"] if item.get("enabled")]
        self._format_filter.configure(values=["All Formats", *format_names])
        category_names = [item["name"] for item in self._bundle["categories"]["categories"] if item.get("enabled")]
        self._category_filter.configure(values=["All Categories", *category_names])

        self._browser_tree.delete(*self._browser_tree.get_children())
        for song in self._filtered_songs():
            status = " (missing)" if song.get("missing_file") else ""
            self._browser_tree.insert(
                "",
                "end",
                iid=song["id"],
                values=(
                    song.get("artist", ""),
                    song.get("title", "") + status,
                    song.get("album", ""),
                    song.get("year", ""),
                    song.get("genre", ""),
                    format_duration(song.get("length_seconds", 0)),
                ),
            )

    def _on_song_select(self, _event=None) -> None:
        selection = self._browser_tree.selection()
        if not selection:
            return
        self._selected_song_id = selection[0]
        song = next(item for item in self._bundle["catalog"]["songs"] if item["id"] == self._selected_song_id)
        format_names = {
            item["id"]: item["name"] for item in self._bundle["formats"]["formats"]
        }
        category_names = {
            item["id"]: item["name"] for item in self._bundle["categories"]["categories"]
        }
        assigned_formats = ", ".join(format_names.get(fid, fid) for fid in song.get("format_ids", [])) or "—"
        assigned_categories = ", ".join(category_names.get(cid, cid) for cid in song.get("category_ids", [])) or "—"
        lines = [
            f"Artist: {song.get('artist', '')}",
            f"Title: {song.get('title', '')}",
            f"Album: {song.get('album', '')}",
            f"Year: {song.get('year', '')}",
            f"Genre: {song.get('genre', '')}",
            f"Length: {format_duration(song.get('length_seconds', 0))}",
            f"File Size: {format_bytes(song.get('file_size', 0))}",
            f"File Location: {song.get('file_path', '')}",
            f"Artwork: {song.get('artwork_path', '') or '—'}",
            f"Formats: {assigned_formats}",
            f"Categories: {assigned_categories}",
            f"Added: {song.get('added_at', '')}",
            f"Status: {'Missing file' if song.get('missing_file') else 'Present'}",
        ]
        self._set_scroll_text(self._song_detail, "\n".join(lines))
        self._refresh_resources_form()

    def _build_formats_tab(self) -> None:
        tab = ttk.Frame(self._notebook, style="Studio.TFrame", padding=12)
        self._notebook.add(tab, text="Formats")
        toolbar = ttk.Frame(tab, style="Studio.TFrame")
        toolbar.pack(fill="x", pady=(0, 8))
        ttk.Button(toolbar, text="Add Format", bootstyle="success", command=self._add_format).pack(side="left")

        panes = ttk.Panedwindow(tab, orient="horizontal", bootstyle="secondary")
        panes.pack(fill="both", expand=True)
        list_panel = ttk.Labelframe(panes, text="Formats", style="StudioCard.TLabelframe", padding=8)
        panes.add(list_panel, weight=1)
        self._formats_tree = ttk.Treeview(
            list_panel,
            columns=("name", "enabled", "songs"),
            show="headings",
            bootstyle="info",
            height=14,
        )
        self._formats_tree.heading("name", text="Format")
        self._formats_tree.heading("enabled", text="Enabled")
        self._formats_tree.heading("songs", text="Songs")
        self._formats_tree.pack(fill="both", expand=True)
        self._formats_tree.bind("<<TreeviewSelect>>", self._on_format_select)

        form = ttk.Labelframe(panes, text="Format Details", style="StudioCard.TLabelframe", padding=12)
        panes.add(form, weight=2)
        self._format_fields: dict[str, tk.Variable] = {}
        for key, label in (("name", "Name"), ("description", "Description")):
            row = ttk.Frame(form, style="StudioPanel.TFrame")
            row.pack(fill="x", pady=4)
            ttk.Label(row, text=label, style="StudioMuted.TLabel", width=14).pack(side="left")
            var = tk.StringVar()
            ttk.Entry(row, textvariable=var).pack(side="left", fill="x", expand=True)
            self._format_fields[key] = var
        self._format_enabled = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            form, text="Enabled", variable=self._format_enabled, bootstyle="success-toolbutton"
        ).pack(anchor="w", pady=8)
        ttk.Button(form, text="Apply Format Changes", bootstyle="primary", command=self._apply_format).pack(anchor="w")

        self._selected_format_id: str | None = None

    def _refresh_formats(self) -> None:
        self._formats_tree.delete(*self._formats_tree.get_children())
        songs = self._bundle["catalog"]["songs"]
        for fmt in self._bundle["formats"]["formats"]:
            count = sum(1 for song in songs if fmt["id"] in song.get("format_ids", []))
            self._formats_tree.insert(
                "",
                "end",
                iid=fmt["id"],
                values=(fmt.get("name", ""), "Yes" if fmt.get("enabled") else "No", count),
            )

    def _on_format_select(self, _event=None) -> None:
        selection = self._formats_tree.selection()
        if not selection:
            return
        self._selected_format_id = selection[0]
        fmt = next(item for item in self._bundle["formats"]["formats"] if item["id"] == self._selected_format_id)
        self._format_fields["name"].set(fmt.get("name", ""))
        self._format_fields["description"].set(fmt.get("description", ""))
        self._format_enabled.set(fmt.get("enabled", True))

    def _apply_format(self) -> None:
        if not self._selected_format_id:
            return
        for fmt in self._bundle["formats"]["formats"]:
            if fmt["id"] == self._selected_format_id:
                fmt["name"] = self._format_fields["name"].get().strip()
                fmt["description"] = self._format_fields["description"].get().strip()
                fmt["enabled"] = self._format_enabled.get()
                break
        self._refresh_formats()
        self._refresh_browser()
        self.set_status("Format updated")

    def _add_format(self) -> None:
        from app.core.music_model import _new_id

        self._bundle["formats"]["formats"].append(
            {"id": _new_id("fmt"), "name": "New Format", "enabled": True, "description": ""}
        )
        self._refresh_formats()
        self.set_status("Format added")

    def _build_playlists_tab(self) -> None:
        tab = ttk.Frame(self._notebook, style="Studio.TFrame", padding=12)
        self._notebook.add(tab, text="Playlists")
        toolbar = ttk.Frame(tab, style="Studio.TFrame")
        toolbar.pack(fill="x", pady=(0, 8))
        ttk.Button(toolbar, text="Create Playlist", bootstyle="success", command=self._create_playlist).pack(side="left")
        ttk.Button(toolbar, text="Duplicate Playlist", bootstyle="info", command=self._duplicate_playlist).pack(
            side="left", padx=8
        )
        ttk.Button(toolbar, text="Archive Playlist", bootstyle="warning", command=self._archive_playlist).pack(
            side="left", padx=8
        )
        ttk.Button(toolbar, text="Delete Playlist", bootstyle="danger", command=self._delete_playlist).pack(side="left")

        panes = ttk.Panedwindow(tab, orient="horizontal", bootstyle="secondary")
        panes.pack(fill="both", expand=True)
        list_panel = ttk.Labelframe(panes, text="Playlists", style="StudioCard.TLabelframe", padding=8)
        panes.add(list_panel, weight=1)
        self._playlists_tree = ttk.Treeview(
            list_panel,
            columns=("name", "songs", "archived"),
            show="headings",
            bootstyle="info",
            height=14,
        )
        self._playlists_tree.heading("name", text="Playlist")
        self._playlists_tree.heading("songs", text="Songs")
        self._playlists_tree.heading("archived", text="Status")
        self._playlists_tree.pack(fill="both", expand=True)
        self._playlists_tree.bind("<<TreeviewSelect>>", self._on_playlist_select)

        form = ttk.Labelframe(panes, text="Playlist Details", style="StudioCard.TLabelframe", padding=12)
        panes.add(form, weight=2)
        self._playlist_fields: dict[str, tk.Variable] = {}
        for key, label in (("name", "Name"), ("description", "Description")):
            row = ttk.Frame(form, style="StudioPanel.TFrame")
            row.pack(fill="x", pady=4)
            ttk.Label(row, text=label, style="StudioMuted.TLabel", width=14).pack(side="left")
            var = tk.StringVar()
            ttk.Entry(row, textvariable=var).pack(side="left", fill="x", expand=True)
            self._playlist_fields[key] = var
        ttk.Button(form, text="Apply Playlist Changes", bootstyle="primary", command=self._apply_playlist).pack(
            anchor="w", pady=8
        )

    def _refresh_playlists(self) -> None:
        self._playlists_tree.delete(*self._playlists_tree.get_children())
        for playlist in self._bundle["playlists"]["playlists"]:
            self._playlists_tree.insert(
                "",
                "end",
                iid=playlist["id"],
                values=(
                    playlist.get("name", ""),
                    len(playlist.get("song_ids", [])),
                    "Archived" if playlist.get("archived") else "Active",
                ),
            )

    def _on_playlist_select(self, _event=None) -> None:
        selection = self._playlists_tree.selection()
        if not selection:
            return
        self._selected_playlist_id = selection[0]
        playlist = next(
            item for item in self._bundle["playlists"]["playlists"] if item["id"] == self._selected_playlist_id
        )
        self._playlist_fields["name"].set(playlist.get("name", ""))
        self._playlist_fields["description"].set(playlist.get("description", ""))

    def _apply_playlist(self) -> None:
        if not self._selected_playlist_id:
            return
        for playlist in self._bundle["playlists"]["playlists"]:
            if playlist["id"] == self._selected_playlist_id:
                playlist["name"] = self._playlist_fields["name"].get().strip()
                playlist["description"] = self._playlist_fields["description"].get().strip()
                break
        self._refresh_playlists()
        self._refresh_overview()
        self.set_status("Playlist updated")

    def _create_playlist(self) -> None:
        from app.core.music_model import _new_id

        playlist = {
            "id": _new_id("pl"),
            "name": "New Playlist",
            "description": "",
            "song_ids": [],
            "format_id": "",
            "archived": False,
            "created_at": datetime.now().strftime("%Y-%m-%d"),
        }
        self._bundle["playlists"]["playlists"].append(playlist)
        self._refresh_playlists()
        self.set_status("Playlist created")

    def _duplicate_playlist(self) -> None:
        if not self._selected_playlist_id:
            return
        from app.core.music_model import _new_id

        source = next(
            item for item in self._bundle["playlists"]["playlists"] if item["id"] == self._selected_playlist_id
        )
        clone = deepcopy(source)
        clone["id"] = _new_id("pl")
        clone["name"] = source.get("name", "Playlist") + " (Copy)"
        clone["created_at"] = datetime.now().strftime("%Y-%m-%d")
        self._bundle["playlists"]["playlists"].append(clone)
        self._refresh_playlists()
        self.set_status("Playlist duplicated")

    def _archive_playlist(self) -> None:
        if not self._selected_playlist_id:
            return
        for playlist in self._bundle["playlists"]["playlists"]:
            if playlist["id"] == self._selected_playlist_id:
                playlist["archived"] = True
                break
        self._refresh_playlists()
        self._refresh_overview()
        self.set_status("Playlist archived")

    def _delete_playlist(self) -> None:
        if not self._selected_playlist_id:
            return
        if Messagebox.yesno("Delete this playlist?", "Delete Playlist") != "Yes":
            return
        self._bundle["playlists"]["playlists"] = [
            pl for pl in self._bundle["playlists"]["playlists"] if pl["id"] != self._selected_playlist_id
        ]
        self._selected_playlist_id = None
        self._refresh_playlists()
        self.set_status("Playlist deleted")

    def _build_categories_tab(self) -> None:
        tab = ttk.Frame(self._notebook, style="Studio.TFrame", padding=12)
        self._notebook.add(tab, text="Categories")
        panes = ttk.Panedwindow(tab, orient="horizontal", bootstyle="secondary")
        panes.pack(fill="both", expand=True)
        list_panel = ttk.Labelframe(panes, text="Categories", style="StudioCard.TLabelframe", padding=8)
        panes.add(list_panel, weight=1)
        self._categories_tree = ttk.Treeview(
            list_panel,
            columns=("name", "enabled", "songs"),
            show="headings",
            bootstyle="info",
            height=14,
        )
        self._categories_tree.heading("name", text="Category")
        self._categories_tree.heading("enabled", text="Enabled")
        self._categories_tree.heading("songs", text="Songs")
        self._categories_tree.pack(fill="both", expand=True)
        self._categories_tree.bind("<<TreeviewSelect>>", self._on_category_select)

        form = ttk.Labelframe(panes, text="Category Details", style="StudioCard.TLabelframe", padding=12)
        panes.add(form, weight=2)
        self._category_fields: dict[str, tk.Variable] = {}
        row = ttk.Frame(form, style="StudioPanel.TFrame")
        row.pack(fill="x", pady=4)
        ttk.Label(row, text="Name", style="StudioMuted.TLabel", width=14).pack(side="left")
        self._category_fields["name"] = tk.StringVar()
        ttk.Entry(row, textvariable=self._category_fields["name"]).pack(side="left", fill="x", expand=True)
        row = ttk.Frame(form, style="StudioPanel.TFrame")
        row.pack(fill="x", pady=4)
        ttk.Label(row, text="Description", style="StudioMuted.TLabel", width=14).pack(side="left")
        self._category_fields["description"] = tk.StringVar()
        ttk.Entry(row, textvariable=self._category_fields["description"]).pack(side="left", fill="x", expand=True)
        self._category_enabled = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            form, text="Enabled", variable=self._category_enabled, bootstyle="success-toolbutton"
        ).pack(anchor="w", pady=8)
        ttk.Button(form, text="Apply Category Changes", bootstyle="primary", command=self._apply_category).pack(
            anchor="w"
        )
        self._selected_category_id: str | None = None

    def _refresh_categories(self) -> None:
        self._categories_tree.delete(*self._categories_tree.get_children())
        songs = self._bundle["catalog"]["songs"]
        for category in self._bundle["categories"]["categories"]:
            count = sum(1 for song in songs if category["id"] in song.get("category_ids", []))
            self._categories_tree.insert(
                "",
                "end",
                iid=category["id"],
                values=(category.get("name", ""), "Yes" if category.get("enabled") else "No", count),
            )

    def _on_category_select(self, _event=None) -> None:
        selection = self._categories_tree.selection()
        if not selection:
            return
        self._selected_category_id = selection[0]
        category = next(
            item for item in self._bundle["categories"]["categories"] if item["id"] == self._selected_category_id
        )
        self._category_fields["name"].set(category.get("name", ""))
        self._category_fields["description"].set(category.get("description", ""))
        self._category_enabled.set(category.get("enabled", True))

    def _apply_category(self) -> None:
        if not self._selected_category_id:
            return
        for category in self._bundle["categories"]["categories"]:
            if category["id"] == self._selected_category_id:
                category["name"] = self._category_fields["name"].get().strip()
                category["description"] = self._category_fields["description"].get().strip()
                category["enabled"] = self._category_enabled.get()
                break
        self._refresh_categories()
        self._refresh_browser()
        self.set_status("Category updated")

    def _build_resources_tab(self) -> None:
        tab = ttk.Frame(self._notebook, style="Studio.TFrame", padding=12)
        self._notebook.add(tab, text="Music Resources")
        ttk.Label(
            tab,
            text="Select a song in Library Browser to view or edit album art paths, lyrics, notes, and tags.",
            style="StudioMuted.TLabel",
            wraplength=900,
            justify="left",
        ).pack(anchor="w", pady=(0, 8))
        form = ttk.Labelframe(tab, text="Song Resources", style="StudioCard.TLabelframe", padding=12)
        form.pack(fill="both", expand=True)
        self._resource_fields: dict[str, tk.Variable] = {}
        for key, label in (
            ("album_art", "Album Art"),
            ("artist_image", "Artist Image"),
            ("lyrics", "Lyrics"),
            ("notes", "Notes"),
            ("tags", "Tags"),
        ):
            row = ttk.Frame(form, style="StudioPanel.TFrame")
            row.pack(fill="x", pady=4)
            ttk.Label(row, text=label, style="StudioMuted.TLabel", width=14).pack(side="left")
            var = tk.StringVar()
            ttk.Entry(row, textvariable=var).pack(side="left", fill="x", expand=True)
            self._resource_fields[key] = var
        ttk.Button(form, text="Save Resources", bootstyle="primary", command=self._save_resources).pack(anchor="w", pady=8)

    def _refresh_resources_form(self) -> None:
        if not self._selected_song_id:
            for var in self._resource_fields.values():
                var.set("")
            return
        resources = self._bundle["resources"]["resources"]
        record = resources.get(self._selected_song_id, {})
        self._resource_fields["album_art"].set(record.get("album_art", ""))
        self._resource_fields["artist_image"].set(record.get("artist_image", ""))
        self._resource_fields["lyrics"].set(record.get("lyrics", ""))
        self._resource_fields["notes"].set(record.get("notes", ""))
        tags = record.get("tags", [])
        self._resource_fields["tags"].set(", ".join(tags) if isinstance(tags, list) else str(tags))

    def _refresh_resources(self) -> None:
        self._refresh_resources_form()

    def _save_resources(self) -> None:
        if not self._selected_song_id:
            return
        tags_raw = self._resource_fields["tags"].get().strip()
        tags = [tag.strip() for tag in tags_raw.split(",") if tag.strip()] if tags_raw else []
        self._bundle["resources"]["resources"][self._selected_song_id] = {
            "album_art": self._resource_fields["album_art"].get().strip(),
            "artist_image": self._resource_fields["artist_image"].get().strip(),
            "lyrics": self._resource_fields["lyrics"].get().strip(),
            "notes": self._resource_fields["notes"].get().strip(),
            "tags": tags,
        }
        self.set_status("Song resources saved")

    def _build_validation_tab(self) -> None:
        tab = ttk.Frame(self._notebook, style="Studio.TFrame", padding=12)
        self._notebook.add(tab, text="Validation")
        self._validation_text = ScrolledText(
            tab, height=20, autohide=True, bootstyle="secondary", state="disabled", wrap="word"
        )
        self._validation_text.pack(fill="both", expand=True)

    def _refresh_validation_tab(self, warnings: list[str]) -> None:
        if not warnings:
            text = "No validation warnings. Your music library looks good."
        else:
            text = "\n".join(f"• {warning}" for warning in warnings)
        self._set_scroll_text(self._validation_text, text)

    def _build_reports_tab(self) -> None:
        tab = ttk.Frame(self._notebook, style="Studio.TFrame", padding=12)
        self._notebook.add(tab, text="Reports")
        toolbar = ttk.Frame(tab, style="Studio.TFrame")
        toolbar.pack(fill="x", pady=(0, 8))
        self._report_var = tk.StringVar(value=REPORT_OPTIONS[0][1])
        self._report_labels = {label: key for key, label in REPORT_OPTIONS}
        ttk.Combobox(
            toolbar,
            textvariable=self._report_var,
            values=[label for _key, label in REPORT_OPTIONS],
            state="readonly",
            width=24,
        ).pack(side="left")
        ttk.Button(toolbar, text="Run Report", bootstyle="info", command=self._run_report).pack(side="left", padx=8)
        self._report_text = ScrolledText(
            tab, height=18, autohide=True, bootstyle="secondary", state="disabled", wrap="word"
        )
        self._report_text.pack(fill="both", expand=True)

    def _run_report(self) -> None:
        key = self._report_labels.get(self._report_var.get(), REPORT_OPTIONS[0][0])
        lines = build_report_lines(self._bundle, key)
        self._set_scroll_text(self._report_text, "\n".join(lines))
        self.set_status("Report generated")

    def _build_settings_tab(self) -> None:
        tab = ttk.Frame(self._notebook, style="Studio.TFrame", padding=12)
        self._notebook.add(tab, text="Settings")
        card = ttk.Labelframe(tab, text="Music Library Settings", style="StudioCard.TLabelframe", padding=16)
        card.pack(fill="x")
        row = ttk.Frame(card, style="StudioPanel.TFrame")
        row.pack(fill="x", pady=4)
        ttk.Label(row, text="Default Music Root", style="StudioMuted.TLabel", width=18).pack(side="left")
        self._music_root_var = tk.StringVar()
        ttk.Entry(row, textvariable=self._music_root_var).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Use Platform Default", bootstyle="secondary", command=self._use_platform_default).pack(
            side="left", padx=8
        )
        ttk.Label(
            card,
            text="Default: W:\\Music. Scanning is read-only — no music files are moved, renamed, or written to RadioDJ.",
            style="StudioHelp.TLabel",
            wraplength=800,
            justify="left",
        ).pack(anchor="w", pady=(12, 0))
        ttk.Button(card, text="Save Settings", bootstyle="primary", command=self._save_settings).pack(anchor="w", pady=(12, 0))

    def _refresh_settings(self) -> None:
        self._music_root_var.set(self._bundle["settings"].get("music_root", r"W:\Music"))

    def _use_platform_default(self) -> None:
        self._music_root_var.set(str(platform_path("music_library", self.config_manager)))

    def _save_settings(self) -> None:
        self._bundle["settings"]["music_root"] = self._music_root_var.get().strip() or r"W:\Music"
        self._refresh_overview()
        self.set_status("Music settings updated")

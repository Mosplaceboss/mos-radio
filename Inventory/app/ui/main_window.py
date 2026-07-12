"""Mo's Place Inventory desktop UI."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from app.core.models import InventorySnapshot
from app.core.path_validation import ensure_default_output_folder, validate_output_path, validate_scan_path
from app.core.scan_engine import ScanEngine
from app.core.settings_store import (
    DEFAULT_OUTPUT_FOLDER,
    current_machine_name,
    load_settings,
    machine_defaults,
    save_settings,
)


class InventoryApplication:
    FIELD_SPECS = (
        ("office_pc_path", "Office PC Folder", "office_var"),
        ("radio_pc_path", "Radio PC Folder", "radio_var"),
        ("platform_folder", "Platform Folder", "platform_var"),
        ("output_folder", "Output Folder", "output_var"),
    )

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Mo's Place Inventory")
        self.root.geometry("1180x780")
        self.root.minsize(980, 680)

        saved = load_settings()
        defaults = machine_defaults()
        self.office_var = tk.StringVar(value=saved["office_pc_path"] or defaults["office_pc_path"])
        self.radio_var = tk.StringVar(value=saved["radio_pc_path"] or defaults["radio_pc_path"])
        self.platform_var = tk.StringVar(value=saved["platform_folder"] or defaults["platform_folder"])
        default_output = saved["output_folder"] or defaults["output_folder"] or DEFAULT_OUTPUT_FOLDER
        try:
            ok, _ = validate_output_path(default_output)
            if not ok:
                default_output = ensure_default_output_folder()
        except OSError:
            default_output = ensure_default_output_folder()
        self.output_var = tk.StringVar(value=default_output)

        self._snapshot: InventorySnapshot | None = None
        self._report_paths: dict[str, str] = {}
        self._validation_labels: dict[str, ttk.Label] = {}
        self._scanning = False
        self._engine = ScanEngine(
            on_progress=self._on_progress,
            on_complete=self._on_complete,
            on_error=self._on_error,
        )

        self._build_inputs()
        self._build_notebook()
        self._build_status()
        self._wire_change_handlers()
        self._refresh_validation()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_inputs(self) -> None:
        frame = ttk.LabelFrame(self.root, text="Scan Inputs", padding=12)
        frame.pack(fill="x", padx=12, pady=12)

        self._path_rows: dict[str, dict] = {}
        for row, (key, label, var_name) in enumerate(self.FIELD_SPECS):
            variable = getattr(self, var_name)
            ttk.Label(frame, text=label, width=18).grid(row=row, column=0, sticky="w", pady=4)

            entry = ttk.Entry(frame, textvariable=variable, width=72, state="readonly")
            entry.grid(row=row, column=1, sticky="ew", padx=8, pady=4)

            actions = ttk.Frame(frame)
            actions.grid(row=row, column=2, sticky="w", pady=4)
            ttk.Button(actions, text="Browse", command=lambda k=key: self._browse_path(k)).pack(side="left")
            ttk.Button(actions, text="Enter Path", command=lambda k=key: self._enter_path(k)).pack(side="left", padx=6)

            status = ttk.Label(frame, text="", wraplength=420)
            status.grid(row=row, column=3, sticky="w", padx=(8, 0), pady=4)
            self._validation_labels[key] = status
            self._path_rows[key] = {"entry": entry, "variable": variable, "label": label}

        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(3, weight=1)

        actions = ttk.Frame(frame)
        actions.grid(row=len(self.FIELD_SPECS), column=0, columnspan=4, sticky="w", pady=(10, 0))
        self.scan_button = ttk.Button(actions, text="Scan", command=self._start_scan, state="disabled")
        self.scan_button.pack(side="left")
        ttk.Button(actions, text="Cancel", command=self._cancel_scan).pack(side="left", padx=8)
        ttk.Label(
            actions,
            text="READ-ONLY: no copy, delete, move, rename, or modify operations.",
            foreground="#8a4b08",
        ).pack(side="left", padx=12)

        self.progress = ttk.Progressbar(frame, maximum=100)
        self.progress.grid(row=len(self.FIELD_SPECS) + 1, column=0, columnspan=4, sticky="ew", pady=(12, 4))
        self.progress_label = ttk.Label(frame, text="Select and validate all paths to enable Scan.")
        self.progress_label.grid(row=len(self.FIELD_SPECS) + 2, column=0, columnspan=4, sticky="w")

    def _build_notebook(self) -> None:
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self.tabs = {
            "Overview": self._make_text_tab("Overview"),
            "Computers": self._make_text_tab("Computers"),
            "Scheduled Tasks": self._make_text_tab("Scheduled Tasks"),
            "Services": self._make_text_tab("Services"),
            "Production Map": self._make_text_tab("Production Map"),
            "Duplicates": self._make_text_tab("Duplicates"),
            "Folder Comparison": self._make_text_tab("Folder Comparison"),
            "Reports": self._make_text_tab("Reports"),
            "Recommendations": self._make_text_tab("Recommendations"),
        }
        for title, widget in self.tabs.items():
            self.notebook.add(widget["frame"], text=title)

    def _make_text_tab(self, _title: str) -> dict:
        frame = ttk.Frame(self.notebook)
        text = tk.Text(frame, wrap="none", font=("Consolas", 10))
        yscroll = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        xscroll = ttk.Scrollbar(frame, orient="horizontal", command=text.xview)
        text.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        text.pack(side="left", fill="both", expand=True)
        yscroll.pack(side="right", fill="y")
        xscroll.pack(side="bottom", fill="x")
        return {"frame": frame, "text": text}

    def _build_status(self) -> None:
        self.status = ttk.Label(
            self.root,
            text=f"Mo's Place Inventory is ready on {current_machine_name()}. Paths are saved per machine.",
            anchor="w",
        )
        self.status.pack(fill="x", padx=12, pady=(0, 12))

    def _wire_change_handlers(self) -> None:
        for _key, _label, var_name in self.FIELD_SPECS:
            getattr(self, var_name).trace_add("write", lambda *_args: self._refresh_validation())

    def _current_settings(self) -> dict[str, str]:
        return {
            "office_pc_path": self.office_var.get().strip(),
            "radio_pc_path": self.radio_var.get().strip(),
            "platform_folder": self.platform_var.get().strip(),
            "output_folder": self.output_var.get().strip() or DEFAULT_OUTPUT_FOLDER,
        }

    def _save_settings(self) -> None:
        save_settings(self._current_settings())

    def _browse_path(self, key: str) -> None:
        row = self._path_rows[key]
        selected = filedialog.askdirectory(
            parent=self.root,
            title=f"Select {row['label']}",
            mustexist=True,
        )
        if selected:
            row["variable"].set(selected)
            self._save_settings()

    def _enter_path(self, key: str) -> None:
        row = self._path_rows[key]
        current = row["variable"].get().strip()
        entered = simpledialog.askstring(
            "Enter Path",
            f"Enter the full local or UNC path for {row['label']}:",
            initialvalue=current,
            parent=self.root,
        )
        if entered is not None:
            row["variable"].set(entered.strip())
            self._save_settings()

    def _set_validation(self, key: str, ok: bool, message: str) -> None:
        label = self._validation_labels[key]
        if ok:
            label.configure(text=f"✓ {message}", foreground="#0f7b0f")
        else:
            label.configure(text=f"✗ {message}", foreground="#b00020")

    def _refresh_validation(self) -> None:
        settings = self._current_settings()
        checks = [
            ("office_pc_path", validate_scan_path(settings["office_pc_path"], label="Office PC folder")),
            ("radio_pc_path", validate_scan_path(settings["radio_pc_path"], label="Radio PC folder")),
            ("platform_folder", validate_scan_path(settings["platform_folder"], label="Platform folder")),
            ("output_folder", validate_output_path(settings["output_folder"])),
        ]
        all_ok = True
        for key, (ok, message) in checks:
            self._set_validation(key, ok, message)
            if not ok:
                all_ok = False

        if self._scanning:
            self.scan_button.configure(state="disabled")
        elif all_ok:
            self.scan_button.configure(state="normal")
            self.progress_label.configure(text="All paths are valid. You can start the inventory scan.")
        else:
            self.scan_button.configure(state="disabled")
            self.progress_label.configure(text="Fix the paths marked with ✗ before scanning.")

    def _start_scan(self) -> None:
        self._refresh_validation()
        if self.scan_button.cget("state") == "disabled":
            messagebox.showwarning("Paths Required", "All paths must be valid before scanning.")
            return

        settings = self._current_settings()
        self._save_settings()
        self._scanning = True
        self.scan_button.configure(state="disabled")
        self.progress["value"] = 0
        self.status.configure(text="Scan started...")
        self._engine.start(
            office_pc=settings["office_pc_path"],
            radio_pc=settings["radio_pc_path"],
            platform_folder=settings["platform_folder"],
            output_folder=settings["output_folder"],
        )

    def _cancel_scan(self) -> None:
        self._engine.cancel()
        self.status.configure(text="Cancel requested...")

    def _on_progress(self, message: str, fraction: float, eta: str) -> None:
        def update() -> None:
            self.progress["value"] = fraction * 100
            self.progress_label.configure(text=f"{message} · {eta}")
            self.status.configure(text=message)

        self.root.after(0, update)

    def _on_complete(self, snapshot: InventorySnapshot, report_paths: dict[str, str]) -> None:
        def update() -> None:
            self._snapshot = snapshot
            self._report_paths = report_paths
            self._scanning = False
            self.progress["value"] = 100
            self.progress_label.configure(text="Scan complete")
            self.status.configure(text=f"Reports written to {snapshot.output_folder}")
            self._populate_tabs()
            self._refresh_validation()

        self.root.after(0, update)

    def _on_error(self, error: Exception) -> None:
        def update() -> None:
            self._scanning = False
            self.status.configure(text=f"Scan failed: {error}")
            messagebox.showerror("Scan Failed", str(error))
            self._refresh_validation()

        self.root.after(0, update)

    def _populate_tabs(self) -> None:
        if not self._snapshot:
            return
        snap = self._snapshot
        self._set_tab(
            "Overview",
            [
                f"Scanned at: {snap.scanned_at}",
                f"Office PC: {snap.office_pc}",
                f"Radio PC: {snap.radio_pc}",
                f"Platform Folder: {snap.platform_folder}",
                f"Output Folder: {snap.output_folder}",
                f"Files: {len(snap.files):,}",
                f"Folders: {len(snap.folders):,}",
                f"Drives: {len(snap.drives):,}",
                f"Tasks: {len(snap.tasks):,}",
                f"Processes: {len(snap.processes):,}",
                f"Services: {len(snap.services):,}",
                f"Components: {len(snap.components):,}",
                f"Duplicates: {len(snap.duplicates):,}",
                f"Recommendations: {len(snap.recommendations):,}",
            ],
        )
        self._set_tab(
            "Computers",
            [f"{drive.computer} {drive.letter}: total={drive.total_bytes:,} free={drive.free_bytes:,}" for drive in snap.drives],
        )
        self._set_tab(
            "Scheduled Tasks",
            [
                f"{task.computer} | {task.name} | {task.program} | {task.working_directory} | {task.status} | {task.trigger}"
                for task in snap.tasks
            ],
        )
        self._set_tab(
            "Services",
            [
                f"{svc.computer} | {svc.name} | {svc.status} | {svc.startup_type} | {svc.executable}"
                for svc in snap.services
            ],
        )
        self._set_tab(
            "Production Map",
            [f"{hit.name} | {hit.computer} | {hit.path}" for hit in snap.components],
        )
        self._set_tab(
            "Duplicates",
            [f"{group.kind} | {group.key} | {'; '.join(group.paths)}" for group in snap.duplicates[:2000]],
        )
        self._set_tab(
            "Folder Comparison",
            [
                f"{row.relative_path} | Office={row.office_status} Radio={row.radio_status} Platform={row.platform_status} | {row.detail}"
                for row in snap.comparisons[:2000]
            ],
        )
        self._set_tab(
            "Reports",
            [f"{name}: {path}" for name, path in self._report_paths.items()],
        )
        self._set_tab(
            "Recommendations",
            [f"[{rec.severity}] {rec.category} | {rec.title} | {rec.detail}" for rec in snap.recommendations],
        )

    def _set_tab(self, name: str, lines: list[str]) -> None:
        text = self.tabs[name]["text"]
        text.delete("1.0", "end")
        text.insert("end", "\n".join(lines))

    def _on_close(self) -> None:
        self._save_settings()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()

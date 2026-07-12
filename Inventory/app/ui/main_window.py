"""Mo's Place Inventory desktop UI."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

from app.core.models import InventorySnapshot
from app.core.scan_engine import ScanEngine


class InventoryApplication:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Mo's Place Inventory")
        self.root.geometry("1180x760")
        self.root.minsize(980, 640)

        self._snapshot: InventorySnapshot | None = None
        self._report_paths: dict[str, str] = {}
        self._engine = ScanEngine(
            on_progress=self._on_progress,
            on_complete=self._on_complete,
            on_error=self._on_error,
        )

        self._build_inputs()
        self._build_notebook()
        self._build_status()

    def _build_inputs(self) -> None:
        frame = ttk.LabelFrame(self.root, text="Scan Inputs", padding=12)
        frame.pack(fill="x", padx=12, pady=12)

        self.office_var = tk.StringVar(value=".")
        self.radio_var = tk.StringVar(value=".")
        self.platform_var = tk.StringVar()
        self.output_var = tk.StringVar(value=str(Path.cwd() / "InventoryOutput"))

        specs = (
            ("Office PC", self.office_var, False),
            ("Radio PC", self.radio_var, False),
            ("Platform Folder", self.platform_var, True),
            ("Output Folder", self.output_var, True),
        )
        for row, (label, variable, browse) in enumerate(specs):
            ttk.Label(frame, text=label, width=16).grid(row=row, column=0, sticky="w", pady=4)
            ttk.Entry(frame, textvariable=variable, width=80).grid(row=row, column=1, sticky="ew", padx=8, pady=4)
            if browse:
                ttk.Button(frame, text="Browse", command=lambda v=variable: self._browse_folder(v)).grid(
                    row=row, column=2, sticky="w", pady=4
                )
        frame.columnconfigure(1, weight=1)

        actions = ttk.Frame(frame)
        actions.grid(row=len(specs), column=0, columnspan=3, sticky="w", pady=(10, 0))
        self.scan_button = ttk.Button(actions, text="Scan", command=self._start_scan)
        self.scan_button.pack(side="left")
        ttk.Button(actions, text="Cancel", command=self._cancel_scan).pack(side="left", padx=8)
        ttk.Label(
            actions,
            text="READ-ONLY: no copy, delete, move, rename, or modify operations.",
            foreground="#8a4b08",
        ).pack(side="left", padx=12)

        self.progress = ttk.Progressbar(frame, maximum=100)
        self.progress.grid(row=len(specs) + 1, column=0, columnspan=3, sticky="ew", pady=(12, 4))
        self.progress_label = ttk.Label(frame, text="Ready")
        self.progress_label.grid(row=len(specs) + 2, column=0, columnspan=3, sticky="w")

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
        self.status = ttk.Label(self.root, text="Mo's Place Inventory is ready.", anchor="w")
        self.status.pack(fill="x", padx=12, pady=(0, 12))

    def _browse_folder(self, variable: tk.StringVar) -> None:
        selected = filedialog.askdirectory()
        if selected:
            variable.set(selected)

    def _start_scan(self) -> None:
        self.scan_button.configure(state="disabled")
        self.progress["value"] = 0
        self.status.configure(text="Scan started...")
        self._engine.start(
            office_pc=self.office_var.get().strip(),
            radio_pc=self.radio_var.get().strip(),
            platform_folder=self.platform_var.get().strip(),
            output_folder=self.output_var.get().strip(),
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
            self.scan_button.configure(state="normal")
            self.progress["value"] = 100
            self.progress_label.configure(text="Scan complete")
            self.status.configure(text=f"Reports written to {snapshot.output_folder}")
            self._populate_tabs()

        self.root.after(0, update)

    def _on_error(self, error: Exception) -> None:
        def update() -> None:
            self.scan_button.configure(state="normal")
            self.status.configure(text=f"Scan failed: {error}")

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

    def run(self) -> None:
        self.root.mainloop()

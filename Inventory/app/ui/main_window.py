"""Mo's Place Inventory desktop UI."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from app.core.models import InventorySnapshot
from app.core.path_validation import ensure_default_output_folder, validate_folder_list, validate_output_path
from app.core.paths_util import is_admin_share, sanitize_folder_path
from app.core.scan_engine import ScanEngine
from app.core.settings_store import (
    DEFAULT_OUTPUT_FOLDER,
    browse_initial_dir,
    current_machine_name,
    is_office_pc,
    load_settings,
    machine_defaults,
    sanitize_folder_list,
    save_settings,
)


class FolderListPanel:
    def __init__(
        self,
        parent: ttk.Frame,
        *,
        title: str,
        settings_key: str,
        required: bool,
        initial_folders: list[str],
        on_change,
    ) -> None:
        self.settings_key = settings_key
        self.required = required
        self._on_change = on_change
        self.folders = sanitize_folder_list(initial_folders)

        self.frame = ttk.LabelFrame(parent, text=title, padding=8)
        self.listbox = tk.Listbox(self.frame, height=5, width=90, font=("Consolas", 10))
        scroll = ttk.Scrollbar(self.frame, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scroll.set)
        self.listbox.grid(row=0, column=0, columnspan=2, sticky="nsew", pady=(0, 8))
        scroll.grid(row=0, column=2, sticky="ns", pady=(0, 8))

        buttons = ttk.Frame(self.frame)
        buttons.grid(row=1, column=0, columnspan=3, sticky="w")
        ttk.Button(buttons, text="Add Folder", command=self._add_local_folder).pack(side="left")
        ttk.Button(buttons, text="Browse Network Folder", command=self._browse_network_folder).pack(side="left", padx=6)
        ttk.Button(buttons, text="Enter Path", command=self._enter_path).pack(side="left", padx=6)
        ttk.Button(buttons, text="Remove Folder", command=self._remove_folder).pack(side="left", padx=6)

        self.status = ttk.Label(self.frame, text="", wraplength=900)
        self.status.grid(row=2, column=0, columnspan=3, sticky="w", pady=(8, 0))

        self.frame.columnconfigure(0, weight=1)
        self._refresh_listbox()

    def get_folders(self) -> list[str]:
        return list(self.folders)

    def _refresh_listbox(self) -> None:
        self.listbox.delete(0, "end")
        for folder in self.folders:
            self.listbox.insert("end", folder)
        self._on_change()

    def _add_path(self, path: str) -> None:
        cleaned = sanitize_folder_path(path)
        if not cleaned:
            if path.strip() and is_admin_share(path):
                messagebox.showerror(
                    "Administrative Share Not Allowed",
                    "Administrative shares such as C$, D$, and E$ are not supported.\n"
                    "Browse to or enter a normal shared folder instead.",
                )
            return
        if cleaned not in self.folders:
            self.folders.append(cleaned)
            self._refresh_listbox()

    def _add_local_folder(self) -> None:
        initialdir = browse_initial_dir(self.settings_key)
        selected = filedialog.askdirectory(
            parent=self.frame.winfo_toplevel(),
            title="Add Folder",
            initialdir=initialdir,
            mustexist=False,
        )
        if selected:
            self._add_path(selected)

    def _browse_network_folder(self) -> None:
        selected = filedialog.askdirectory(
            parent=self.frame.winfo_toplevel(),
            title="Browse Network Folder",
            initialdir=r"\\",
            mustexist=False,
        )
        if selected:
            self._add_path(selected)

    def _enter_path(self) -> None:
        entered = simpledialog.askstring(
            "Enter Path",
            "Enter the full local or UNC shared folder path:",
            parent=self.frame.winfo_toplevel(),
        )
        if entered is not None:
            self._add_path(entered.strip())

    def _remove_folder(self) -> None:
        selection = self.listbox.curselection()
        if not selection:
            return
        index = selection[0]
        if 0 <= index < len(self.folders):
            del self.folders[index]
            self._refresh_listbox()

    def validate(self) -> tuple[bool, str, bool]:
        return validate_folder_list(self.folders, label=self.frame.cget("text"), required=self.required)

    def set_status(self, ok: bool, message: str, *, warning: bool = False) -> None:
        if ok and warning:
            self.status.configure(text=f"⚠ {message}", foreground="#8a4b08")
        elif ok:
            self.status.configure(text=f"✓ {message}", foreground="#0f7b0f")
        else:
            self.status.configure(text=f"✗ {message}", foreground="#b00020")


class InventoryApplication:
    def __init__(self, *, auto_scan: bool = False) -> None:
        self._auto_scan = auto_scan
        self.root = tk.Tk()
        self.root.title("Mo's Place Inventory")
        self.root.geometry("1180x860")
        self.root.minsize(980, 760)

        saved = load_settings()
        defaults = machine_defaults()
        default_output = saved["output_folder"] or defaults["output_folder"] or DEFAULT_OUTPUT_FOLDER
        try:
            ok, _, _ = validate_output_path(default_output)
            if not ok:
                default_output = ensure_default_output_folder()
        except (OSError, PermissionError):
            default_output = ensure_default_output_folder()
        self.output_var = tk.StringVar(value=default_output)

        self._snapshot: InventorySnapshot | None = None
        self._report_paths: dict[str, str] = {}
        self._scanning = False
        self._engine = ScanEngine(
            on_progress=self._on_progress,
            on_complete=self._on_complete,
            on_error=self._on_error,
        )

        self._build_read_only_banner()
        self._build_inputs(saved, defaults)
        self._build_notebook()
        self._build_status()
        self._refresh_validation()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        if self._auto_scan:
            self.root.after(250, self._maybe_auto_start)

    def _maybe_auto_start(self) -> None:
        self._refresh_validation()
        if self.scan_button.cget("state") == "normal":
            self._start_scan()

    def _build_read_only_banner(self) -> None:
        banner = tk.Frame(self.root, bg="#e8f5e9", padx=16, pady=12)
        banner.pack(fill="x")

        tk.Label(
            banner,
            text="READ ONLY MODE",
            font=("Segoe UI", 14, "bold"),
            fg="#1b5e20",
            bg="#e8f5e9",
            anchor="w",
        ).pack(fill="x")

        tk.Label(
            banner,
            text="This application does not modify your computers. It only inventories and reports.",
            font=("Segoe UI", 10),
            fg="#2e7d32",
            bg="#e8f5e9",
            anchor="w",
        ).pack(fill="x", pady=(4, 0))

    def _build_inputs(self, saved: dict, defaults: dict) -> None:
        frame = ttk.Frame(self.root, padding=12)
        frame.pack(fill="x", padx=12, pady=12)

        ttk.Label(
            frame,
            text="Scan only the folders you select. Administrative shares (C$, D$, E$) are never used.",
            foreground="#444444",
            wraplength=1050,
        ).pack(anchor="w", pady=(0, 8))

        self.office_panel = FolderListPanel(
            frame,
            title="Office PC Folders to Scan",
            settings_key="office_pc_folders",
            required=True,
            initial_folders=saved.get("office_pc_folders") or defaults["office_pc_folders"],
            on_change=self._refresh_validation,
        )
        self.office_panel.frame.pack(fill="x", pady=(0, 10))

        self.radio_panel = FolderListPanel(
            frame,
            title="Radio PC Folders to Scan",
            settings_key="radio_pc_folders",
            required=False,
            initial_folders=saved.get("radio_pc_folders") or defaults["radio_pc_folders"],
            on_change=self._refresh_validation,
        )
        self.radio_panel.frame.pack(fill="x", pady=(0, 10))

        output_frame = ttk.LabelFrame(frame, text="Output Folder", padding=8)
        output_frame.pack(fill="x", pady=(0, 10))

        self.output_var.trace_add("write", lambda *_args: self._refresh_validation())
        ttk.Entry(output_frame, textvariable=self.output_var, width=90).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        actions = ttk.Frame(output_frame)
        actions.grid(row=0, column=1, sticky="w")
        ttk.Button(actions, text="Browse...", command=self._browse_output).pack(side="left")
        ttk.Button(actions, text="Enter Path", command=self._enter_output).pack(side="left", padx=6)
        self.output_status = ttk.Label(output_frame, text="", wraplength=900)
        self.output_status.grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))
        output_frame.columnconfigure(0, weight=1)

        actions = ttk.Frame(frame)
        actions.pack(fill="x", pady=(4, 0))
        self.scan_button = ttk.Button(actions, text="Scan", command=self._start_scan, state="disabled")
        self.scan_button.pack(side="left")
        ttk.Button(actions, text="Cancel", command=self._cancel_scan).pack(side="left", padx=8)

        self.progress = ttk.Progressbar(frame, maximum=100)
        self.progress.pack(fill="x", pady=(12, 4))
        self.progress_label = ttk.Label(frame, text="Confirm folders and output path to enable Scan.")
        self.progress_label.pack(anchor="w")

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
        host = current_machine_name()
        role = "Office PC" if is_office_pc() else "this machine"
        self.status = ttk.Label(
            self.root,
            text=f"Mo's Place Inventory is ready on {host} ({role}). Folder lists are saved per machine.",
            anchor="w",
        )
        self.status.pack(fill="x", padx=12, pady=(0, 12))

    def _current_settings(self) -> dict:
        return {
            "office_pc_folders": self.office_panel.get_folders(),
            "radio_pc_folders": self.radio_panel.get_folders(),
            "output_folder": self.output_var.get().strip() or DEFAULT_OUTPUT_FOLDER,
        }

    def _save_settings(self) -> None:
        save_settings(self._current_settings())

    def _browse_output(self) -> None:
        current = self.output_var.get().strip()
        selected = filedialog.askdirectory(
            parent=self.root,
            title="Browse for Output Folder",
            initialdir=browse_initial_dir("output_folder", current),
            mustexist=False,
        )
        if selected:
            self.output_var.set(selected)
            self._save_settings()

    def _enter_output(self) -> None:
        entered = simpledialog.askstring(
            "Enter Path",
            "Enter the full output folder path:",
            initialvalue=self.output_var.get().strip(),
            parent=self.root,
        )
        if entered is not None:
            self.output_var.set(entered.strip())
            self._save_settings()

    def _refresh_validation(self) -> None:
        try:
            office_ok, office_msg, office_warn = self.office_panel.validate()
            radio_ok, radio_msg, radio_warn = self.radio_panel.validate()
            output_ok, output_msg, output_warn = validate_output_path(self.output_var.get().strip())

            self.office_panel.set_status(office_ok, office_msg, warning=office_warn)
            self.radio_panel.set_status(radio_ok, radio_msg, warning=radio_warn)
            if output_ok and output_warn:
                self.output_status.configure(text=f"⚠ {output_msg}", foreground="#8a4b08")
            elif output_ok:
                self.output_status.configure(text=f"✓ {output_msg}", foreground="#0f7b0f")
            else:
                self.output_status.configure(text=f"✗ {output_msg}", foreground="#b00020")

            all_ok = office_ok and radio_ok and output_ok
            if self._scanning:
                self.scan_button.configure(state="disabled")
            elif all_ok:
                self.scan_button.configure(state="normal")
                self.progress_label.configure(text="Folders are ready. You can start the inventory scan.")
            else:
                self.scan_button.configure(state="disabled")
                self.progress_label.configure(text="Fix the items marked with ✗ before scanning.")
        except (OSError, PermissionError, Exception) as exc:
            self.scan_button.configure(state="disabled")
            self.progress_label.configure(text=f"Validation issue: {exc}")

    def _start_scan(self) -> None:
        self._refresh_validation()
        if self.scan_button.cget("state") == "disabled":
            messagebox.showwarning("Paths Required", "Office folders and output path must be valid before scanning.")
            return

        settings = self._current_settings()
        self._save_settings()
        self._scanning = True
        self.scan_button.configure(state="disabled")
        self.progress["value"] = 0
        self.status.configure(text="Scan started...")
        self._engine.start(
            office_folders=settings["office_pc_folders"],
            radio_folders=settings["radio_pc_folders"],
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
            status = snapshot.status or "complete"
            self.progress_label.configure(text=f"Scan finished ({status})")
            self.status.configure(text=f"{status.title()} · reports in {snapshot.output_folder}")
            self._populate_tabs()
            self._refresh_validation()

        self.root.after(0, update)

    def _on_error(self, error: Exception) -> None:
        def update() -> None:
            self._scanning = False
            self.status.configure(text=f"Scan issue recorded: {error}")
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
                f"Office PC folders: {snap.office_pc}",
                f"Radio PC folders: {snap.radio_pc}",
                f"Platform reference: {snap.platform_folder}",
                f"Output Folder: {snap.output_folder}",
                f"Status: {snap.status}",
                f"Scan errors: {len(snap.scan_errors):,}",
                f"Files: {len(snap.files):,}",
                f"Folders: {len(snap.folders):,}",
                f"Drives: {len(snap.drives):,}",
                f"Tasks: {len(snap.tasks):,}",
                f"Processes: {len(snap.processes):,}",
                f"Services: {len(snap.services):,}",
                f"Components: {len(snap.components):,}",
                f"Duplicates: {len(snap.duplicates):,}",
                f"Recommendations: {len(snap.recommendations):,}",
                "",
                "Scan Errors:",
                *[
                    f"{err.computer} | {err.phase} | {err.path} | {err.error}"
                    for err in snap.scan_errors[:200]
                ],
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

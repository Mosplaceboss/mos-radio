"""Base class for Studio content pages."""

from __future__ import annotations

import tkinter as tk
from abc import ABC, abstractmethod
from copy import deepcopy
from typing import TYPE_CHECKING, Any, Callable

import ttkbootstrap as ttk
from ttkbootstrap.dialogs import Messagebox

from app.core.background_tasks import run_in_background
from app.core.config_io import write_json

if TYPE_CHECKING:
    from app.core.config_manager import ConfigManager


class BasePage(ttk.Frame, ABC):
    """Shared lifecycle for modular Studio pages."""

    page_id: str = "base"
    page_title: str = "Page"
    page_subtitle: str = ""
    page_help: str = ""

    def __init__(
        self,
        parent: tk.Misc,
        config_manager: ConfigManager,
        on_status: Callable[[str], None],
        on_navigate: Callable[[str], None] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(parent, style="Studio.TFrame", **kwargs)
        self.config_manager = config_manager
        self.on_status = on_status
        self.on_navigate = on_navigate
        self._task_generation = 0
        self._busy_depth = 0
        self._header = ttk.Frame(self, style="Studio.TFrame")
        self._header.pack(fill="x", padx=24, pady=(20, 12))
        self._title = ttk.Label(
            self._header,
            text=self.page_title,
            style="StudioHeading.TLabel",
        )
        self._title.pack(anchor="w")
        if self.page_subtitle:
            ttk.Label(
                self._header,
                text=self.page_subtitle,
                style="StudioSubheading.TLabel",
            ).pack(anchor="w", pady=(4, 0))
        if self.page_help:
            ttk.Label(
                self._header,
                text=self.page_help,
                style="StudioHelp.TLabel",
                wraplength=900,
                justify="left",
            ).pack(anchor="w", pady=(8, 0))
        self._body = ttk.Frame(self, style="Studio.TFrame")
        self._body.pack(fill="both", expand=True, padx=24, pady=(0, 20))
        self.build()

    @abstractmethod
    def build(self) -> None:
        """Construct page widgets."""

    def on_show(self) -> None:
        """Called when the page becomes visible."""

    def set_status(self, message: str) -> None:
        self.on_status(message)

    def _reset_busy_cursor(self) -> None:
        self._busy_depth = 0
        try:
            top = self.winfo_toplevel()
            top.configure(cursor="")
            self.configure(cursor="")
        except tk.TclError:
            pass

    def _show_busy_cursor(self, active: bool) -> None:
        if active:
            self._busy_depth += 1
        else:
            self._busy_depth = max(0, self._busy_depth - 1)
        cursor = "watch" if self._busy_depth > 0 else ""
        try:
            top = self.winfo_toplevel()
            top.configure(cursor=cursor)
            self.configure(cursor=cursor)
        except tk.TclError:
            pass

    def _show_error_dialog(self, title: str, message: str) -> None:
        Messagebox.show_error(message, title)
        self.set_status(message)

    def _run_async_task(
        self,
        work: Callable[[], Any],
        on_success: Callable[[Any], None],
        *,
        loading_message: str = "",
        error_title: str | None = None,
        use_busy_cursor: bool = True,
        generation: int | None = None,
    ) -> int:
        if generation is None:
            self._task_generation += 1
            generation = self._task_generation
        else:
            self._task_generation = generation

        if loading_message:
            self.set_status(loading_message)
        if use_busy_cursor:
            self._show_busy_cursor(True)

        title = error_title or self.page_title

        def complete(result: Any) -> None:
            if generation != self._task_generation:
                return
            if use_busy_cursor:
                self._show_busy_cursor(False)
            try:
                on_success(result)
            except Exception as exc:
                self._show_error_dialog(title, str(exc))

        def failed(error: Exception) -> None:
            if generation != self._task_generation:
                return
            if use_busy_cursor:
                self._show_busy_cursor(False)
            self._show_error_dialog(title, str(error))

        run_in_background(self, work, complete, on_error=failed)
        return generation

    def _persist_config_async(
        self,
        config_name: str,
        data: dict[str, Any],
        *,
        on_complete: Callable[[], None] | None = None,
        status_message: str = "",
        error_title: str | None = None,
        use_busy_cursor: bool = True,
    ) -> None:
        path = self.config_manager.path_for(config_name)
        payload = deepcopy(data)

        def work() -> dict[str, Any]:
            write_json(path, payload)
            return payload

        def success(saved: dict[str, Any]) -> None:
            self.config_manager._cache[config_name] = deepcopy(saved)
            if status_message:
                self.set_status(status_message)
            if on_complete:
                on_complete()

        self._run_async_task(
            work,
            success,
            error_title=error_title or f"Save {self.page_title}",
            use_busy_cursor=use_busy_cursor,
        )

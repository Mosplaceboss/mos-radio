"""Run blocking work off the Tkinter main thread."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import TypeVar

import tkinter as tk

T = TypeVar("T")


def run_in_background(
    widget: tk.Misc,
    work: Callable[[], T],
    on_complete: Callable[[T], None],
    on_error: Callable[[Exception], None] | None = None,
) -> None:
    """Execute work on a daemon thread and deliver results via widget.after()."""

    def _deliver_complete(value: T) -> None:
        try:
            if not widget.winfo_exists():
                return
        except tk.TclError:
            return
        on_complete(value)

    def _deliver_error(error: Exception) -> None:
        if on_error is None:
            return
        try:
            if not widget.winfo_exists():
                return
        except tk.TclError:
            return
        on_error(error)

    def _runner() -> None:
        try:
            result = work()
        except Exception as exc:
            try:
                widget.after(0, lambda error=exc: _deliver_error(error))
            except (RuntimeError, tk.TclError):
                pass
            return
        try:
            widget.after(0, lambda value=result: _deliver_complete(value))
        except (RuntimeError, tk.TclError):
            pass

    threading.Thread(target=_runner, daemon=True).start()

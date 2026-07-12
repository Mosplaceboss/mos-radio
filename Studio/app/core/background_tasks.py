"""Run blocking work off the Tkinter main thread."""

from __future__ import annotations

import queue
import threading
import weakref
from collections.abc import Callable
from typing import Any, TypeVar

import tkinter as tk

T = TypeVar("T")

_RESULT_QUEUE: queue.Queue[tuple[str, str, Any, Callable[..., None] | None, Callable[..., None] | None]] = (
    queue.Queue()
)
_POLLER_ROOTS: weakref.WeakKeyDictionary[tk.Misc, bool] = weakref.WeakKeyDictionary()
_POLLER_LOCK = threading.Lock()


def _widget_alive(widget: tk.Misc) -> bool:
    try:
        return bool(widget.winfo_exists())
    except tk.TclError:
        return False


def _resolve_widget(root: tk.Misc, widget_path: str) -> tk.Misc | None:
    try:
        return root.nametowidget(widget_path)
    except (KeyError, tk.TclError):
        return None


def _start_poller(root: tk.Misc) -> None:
    with _POLLER_LOCK:
        if root in _POLLER_ROOTS:
            return
        _POLLER_ROOTS[root] = True

    root_ref = weakref.ref(root)

    def _poll() -> None:
        root_widget = root_ref()
        if root_widget is None or not _widget_alive(root_widget):
            return

        while True:
            try:
                widget_path, kind, payload, on_complete, on_error = _RESULT_QUEUE.get_nowait()
            except queue.Empty:
                break

            widget = _resolve_widget(root_widget, widget_path)
            if widget is None or not _widget_alive(widget):
                continue
            try:
                if kind == "ok" and on_complete is not None:
                    on_complete(payload)
                elif kind == "err" and on_error is not None:
                    on_error(payload)
            except Exception:
                continue

        if _widget_alive(root_widget):
            root_widget.after(50, _poll)

    root.after(50, _poll)


def run_in_background(
    widget: tk.Misc,
    work: Callable[[], T],
    on_complete: Callable[[T], None],
    on_error: Callable[[Exception], None] | None = None,
) -> None:
    """Execute work on a daemon thread and deliver results on the Tk main thread."""

    try:
        root = widget.winfo_toplevel()
        widget_path = str(widget)
        _start_poller(root)
    except (RuntimeError, tk.TclError):
        return

    def _runner() -> None:
        try:
            result = work()
            _RESULT_QUEUE.put((widget_path, "ok", result, on_complete, on_error))
        except Exception as exc:
            _RESULT_QUEUE.put((widget_path, "err", exc, on_complete, on_error))

    threading.Thread(target=_runner, daemon=True, name="studio-background").start()

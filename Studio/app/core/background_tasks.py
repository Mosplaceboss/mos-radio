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
_POLLER_JOBS: weakref.WeakKeyDictionary[tk.Misc, str] = weakref.WeakKeyDictionary()
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
            except Exception as exc:
                if on_error is not None:
                    try:
                        on_error(exc)
                    except Exception:
                        pass

        try:
            if _widget_alive(root_widget):
                job = root_widget.after(50, _poll)
                _POLLER_JOBS[root_widget] = job
        except tk.TclError:
            return

    try:
        job = root.after(50, _poll)
        _POLLER_JOBS[root] = job
    except tk.TclError:
        return


def cancel_background_tasks(root: tk.Misc) -> None:
    """Stop queued callbacks for a window that is closing."""
    job = _POLLER_JOBS.pop(root, None)
    if job:
        try:
            root.after_cancel(job)
        except tk.TclError:
            pass
    with _POLLER_LOCK:
        _POLLER_ROOTS.pop(root, None)


def drain_background_results() -> None:
    """Drop pending thread results after a window closes."""
    while True:
        try:
            _RESULT_QUEUE.get_nowait()
        except queue.Empty:
            return


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

"""Hidden subprocess helpers and timeouts for Windows desktop checks."""

from __future__ import annotations

import logging
import subprocess
import sys
import threading
from pathlib import Path
from typing import Sequence

logger = logging.getLogger("moplace.studio.hidden_process")

PROCESS_CHECK_TIMEOUT = 3
NETWORK_TIMEOUT = 3
GIT_READ_TIMEOUT = 1
SCRIPT_LAUNCH_TIMEOUT = 2

_PROCESS_CACHE: list[str] | None = None


def _windows_hidden_kwargs() -> dict:
    if sys.platform != "win32":
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return {"startupinfo": startupinfo, "creationflags": flags}


def run_hidden(
    args: Sequence[str],
    *,
    cwd: str | Path | None = None,
    timeout: float = PROCESS_CHECK_TIMEOUT,
    text: bool = True,
) -> subprocess.CompletedProcess[str]:
    kwargs: dict = {
        "capture_output": True,
        "timeout": timeout,
        "check": False,
        "text": text,
    }
    if cwd is not None:
        kwargs["cwd"] = str(cwd)
    kwargs.update(_windows_hidden_kwargs())
    return subprocess.run(list(args), **kwargs)


def popen_hidden(
    args: Sequence[str],
    *,
    cwd: str | Path | None = None,
) -> subprocess.Popen[str]:
    kwargs: dict = {
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "stdin": subprocess.DEVNULL,
    }
    if cwd is not None:
        kwargs["cwd"] = str(cwd)
    kwargs.update(_windows_hidden_kwargs())
    return subprocess.Popen(list(args), **kwargs)


def read_git_commit_short(repo: Path) -> str:
    git_dir = repo / ".git"
    head_file = git_dir / "HEAD"
    if not head_file.exists():
        return "unknown"
    try:
        head = head_file.read_text(encoding="utf-8", errors="ignore").strip()
        if head.startswith("ref: "):
            ref_path = git_dir / head[5:].strip()
            if ref_path.exists():
                commit = ref_path.read_text(encoding="utf-8", errors="ignore").strip()
                return commit[:7] if commit else "unknown"
            packed = git_dir / "packed-refs"
            if packed.exists():
                ref_name = head[5:].strip()
                for line in packed.read_text(encoding="utf-8", errors="ignore").splitlines():
                    if line.startswith("#") or " " not in line:
                        continue
                    commit, name = line.split(" ", 1)
                    if name.strip() == ref_name:
                        return commit.strip()[:7]
        if len(head) >= 7:
            return head[:7]
    except OSError as exc:
        logger.debug("Git commit read failed: %s", exc)
    return "unknown"


def list_windows_process_lines(*, force_refresh: bool = False) -> list[str]:
    global _PROCESS_CACHE
    if _PROCESS_CACHE is not None and not force_refresh:
        return _PROCESS_CACHE
    if sys.platform != "win32":
        _PROCESS_CACHE = []
        return _PROCESS_CACHE
    try:
        result = run_hidden(
            ["tasklist", "/FO", "CSV", "/NH"],
            timeout=PROCESS_CHECK_TIMEOUT,
        )
        if result.returncode != 0:
            _PROCESS_CACHE = []
            return _PROCESS_CACHE
        _PROCESS_CACHE = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    except (OSError, subprocess.SubprocessError, TimeoutError) as exc:
        logger.debug("Process list check failed: %s", exc)
        _PROCESS_CACHE = []
    return _PROCESS_CACHE


def clear_process_cache() -> None:
    global _PROCESS_CACHE
    _PROCESS_CACHE = None


def path_is_accessible(path: Path, *, timeout: float = 2.0) -> bool:
    """Check path existence without blocking indefinitely on slow network shares."""
    result = {"value": False}

    def worker() -> None:
        try:
            result["value"] = path.exists()
        except OSError:
            result["value"] = False

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join(timeout)
    return bool(result["value"])

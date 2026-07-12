"""Verify hidden subprocess usage and background health checks."""

from __future__ import annotations

import sys
import time
from pathlib import Path

STUDIO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(STUDIO_ROOT))

from app.core.config_manager import ConfigManager
from app.core.dashboard_model import build_dashboard_snapshot
from app.core.hidden_process import list_windows_process_lines, run_hidden
from app.core.studio_info import git_commit_short
from app.core.system_status import build_live_system_status


def main() -> int:
    errors: list[str] = []

    if sys.platform == "win32":
        flags = run_hidden.__defaults__  # noqa: SLF001
        result = run_hidden(["cmd", "/c", "echo ok"], timeout=2)
        if result.returncode != 0 or "ok" not in result.stdout.lower():
            errors.append("Hidden cmd execution failed")
    else:
        print("Skipping Windows-only hidden cmd test")

    processes = list_windows_process_lines(force_refresh=True)
    if sys.platform == "win32" and not processes:
        errors.append("Hidden process list returned no data on Windows")

    commit = git_commit_short()
    if commit == "":
        errors.append("Git commit lookup returned empty string")

    settings = ConfigManager().load("settings", {})
    start = time.perf_counter()
    status = build_live_system_status(settings)
    elapsed = time.perf_counter() - start
    if elapsed > 15:
        errors.append(f"Live system status exceeded timeout budget ({elapsed:.1f}s)")
    if len(status.services) < 5:
        errors.append("Live system status missing services")

    start = time.perf_counter()
    snapshot = build_dashboard_snapshot(ConfigManager())
    elapsed = time.perf_counter() - start
    if elapsed > 20:
        errors.append(f"Dashboard snapshot exceeded timeout budget ({elapsed:.1f}s)")
    if len(snapshot.station_lights) != 7:
        errors.append("Dashboard snapshot missing station lights")

    if errors:
        print("HIDDEN CHECK FAILURES:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("Hidden background checks verified.")
    print(f"Git: {commit}")
    print(f"Processes sampled: {len(processes)}")
    print(f"Services: {len(status.services)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

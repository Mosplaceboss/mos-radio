"""Mo's Place Studio v2 integration verification."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

STUDIO_ROOT = Path(__file__).resolve().parent
REPO_ROOT = STUDIO_ROOT.parent


def main() -> int:
    scripts = (
        STUDIO_ROOT / "verify_pages.py",
        STUDIO_ROOT / "verify_ui_stability.py",
    )
    for script in scripts:
        print(f"\n=== Running {script.name} ===")
        result = subprocess.run([sys.executable, str(script)], cwd=STUDIO_ROOT)
        if result.returncode != 0:
            print(f"\nFAILED: {script.name}")
            return result.returncode

    settings_path = STUDIO_ROOT / "config" / "settings.json"
    if settings_path.exists():
        import json

        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        mode = settings.get("operation_mode", "development")
        if mode != "development":
            print(f"FAILED: expected development mode, got {mode!r}")
            return 1
        print("OK: Development Mode default confirmed")

    from app.core.studio_info import APP_VERSION_LABEL

    if "v2.0" not in APP_VERSION_LABEL:
        print(f"FAILED: unexpected version label {APP_VERSION_LABEL!r}")
        return 1
    print(f"OK: Version label {APP_VERSION_LABEL}")

    print("\nAll v2 integration checks passed.")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(STUDIO_ROOT))
    raise SystemExit(main())

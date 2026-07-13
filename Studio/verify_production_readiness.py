"""Production readiness verification for Mo's Place Studio v2 RC."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

STUDIO_ROOT = Path(__file__).resolve().parent
REPO_ROOT = STUDIO_ROOT.parent
os.environ["STUDIO_VERIFY"] = "1"


def main() -> int:
    scripts = (
        STUDIO_ROOT / "verify_pages.py",
        STUDIO_ROOT / "verify_ui_stability.py",
    )
    for script in scripts:
        print(f"\n=== Running {script.name} ===")
        result = subprocess.run([sys.executable, str(script)], cwd=STUDIO_ROOT)
        if result.returncode != 0:
            print(f"FAILED: {script.name}")
            return result.returncode

    sys.path.insert(0, str(STUDIO_ROOT))
    from app.core.setup_wizard_model import SetupWizardData, setup_required, test_setup
    from app.core.studio_info import APP_VERSION_LABEL
    from app.core.update_manager import create_pre_update_backup
    from app.core.user_modes import USER_MODE_ADVANCED, USER_MODE_OWNER, USER_MODE_STAFF, page_allowed

    if "Release Candidate" not in APP_VERSION_LABEL:
        print(f"FAILED: expected RC label, got {APP_VERSION_LABEL!r}")
        return 1
    print(f"OK: {APP_VERSION_LABEL}")

    for mode, page, expected in (
        ({"user_mode": USER_MODE_STAFF}, "daily_operations", True),
        ({"user_mode": USER_MODE_STAFF}, "platform_manager", False),
        ({"user_mode": USER_MODE_OWNER}, "broadcasting_manager", True),
        ({"user_mode": USER_MODE_OWNER}, "platform_manager", False),
        ({"user_mode": USER_MODE_ADVANCED}, "platform_manager", True),
    ):
        if page_allowed(page, mode) != expected:
            print(f"FAILED: mode {mode['user_mode']} page {page} expected {expected}")
            return 1
    print("OK: operating mode page access")

    if not setup_required({"setup_complete": False}):
        print("FAILED: setup_required should be true when incomplete")
        return 1
    if setup_required({"setup_complete": True}):
        print("FAILED: setup_required should be false when complete")
        return 1
    print("OK: setup_required flag")

    backup = create_pre_update_backup()
    if not backup.exists():
        print("FAILED: pre-update backup not created")
        return 1
    print(f"OK: pre-update backup at {backup}")

    docs_dir = REPO_ROOT / "Docs"
    if not docs_dir.exists():
        docs_dir = REPO_ROOT / "docs"
    docs = (
        docs_dir / "Quick_Start_Guide.md",
        docs_dir / "Daily_Operations_Guide.md",
        docs_dir / "Staff_Guide.md",
        docs_dir / "Backup_and_Restore_Guide.md",
        docs_dir / "Emergency_Recovery_Guide.md",
        docs_dir / "Production_Map.md",
        docs_dir / "Folder_Map.md",
    )
    for doc in docs:
        if not doc.exists():
            print(f"FAILED: missing documentation {doc}")
            return 1
    print("OK: documentation present")

    installer = REPO_ROOT / "Tools" / "Install_Studio.ps1"
    if not installer.exists():
        print("FAILED: installer script missing")
        return 1
    print("OK: installer script present")

    print("\nAll production readiness checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

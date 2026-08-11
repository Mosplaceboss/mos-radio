"""Rewrite a live requests.json so every TTS URL points at Piper, not Voicebox."""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

PIPER_URL = "http://127.0.0.1:5000"
PIPER_HEALTH = "/voices"


def _is_voicebox(url: str) -> bool:
    lowered = url.lower()
    return "7860" in lowered or "voicebox" in lowered


def repair(path: Path) -> None:
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise SystemExit(f"Unexpected JSON in {path}")

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = path.with_suffix(path.suffix + f".voicebox-backup-{stamp}")
    shutil.copy2(path, backup)

    piper_fields = {
        "tts_provider": "piper",
        "tts_api_url": PIPER_URL,
        "tts_health_path": PIPER_HEALTH,
        "voice_engine": "piper",
        "use_piper": True,
        "use_voicebox": False,
        "voice_api_url": PIPER_URL,
        "piper_api_url": PIPER_URL,
        "piper_health_path": PIPER_HEALTH,
        "voicebox_api_url": PIPER_URL,
        "voicebox_url": PIPER_URL,
        "voicebox_endpoint": PIPER_URL,
        "voicebox_health_path": PIPER_HEALTH,
    }
    data.update(piper_fields)
    for key, value in list(data.items()):
        if isinstance(value, str) and _is_voicebox(value):
            data[key] = PIPER_URL

    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Repaired {path}")
    print(f"Backup: {backup}")
    print(f"TTS now Piper-only at {PIPER_URL}")
    print("Restart MoRequestsWatcher now.")


def main() -> int:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("requests.json")
    if not target.exists():
        print(f"Missing {target}")
        return 1
    repair(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Rewrite a live requests.json to Piper-only TTS and remove all Voicebox fields."""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

PIPER_URL = "http://127.0.0.1:5000"
PIPER_HEALTH = "/voices"

VOICEBOX_KEYS = (
    "voicebox_api_url",
    "voicebox_url",
    "voicebox_endpoint",
    "voicebox_health_path",
    "vb_api_url",
    "vb_url",
    "use_voicebox",
)


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
        "voice_api_url": PIPER_URL,
        "piper_api_url": PIPER_URL,
        "piper_health_path": PIPER_HEALTH,
    }
    data.update(piper_fields)
    for key in list(data.keys()):
        lowered = key.lower()
        if lowered in {item.lower() for item in VOICEBOX_KEYS} or lowered.startswith("voicebox"):
            data.pop(key, None)
            continue
        value = data.get(key)
        if isinstance(value, str) and ("7860" in value or "voicebox" in value.lower()):
            if key in {"tts_api_url", "piper_api_url", "voice_api_url"}:
                data[key] = PIPER_URL
            elif "health" in key:
                data[key] = PIPER_HEALTH
            else:
                data.pop(key, None)
    data.pop("use_voicebox", None)

    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Repaired {path}")
    print(f"Backup: {backup}")
    print(f"TTS is Piper-only at {PIPER_URL}")
    print("All Voicebox fields removed.")
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

"""Rewrite a live requests.json to Piper-only TTS and remove all Voicebox fields."""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

PIPER_URL = "http://127.0.0.1:5000"
PIPER_HEALTH = "/voices"
PIPER_VOICE = "mos-place-requests-v1"


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
        "intro_engine": "piper",
        "intro_tts_provider": "piper",
        "use_piper": True,
        "forbid_voicebox": True,
        "block_voicebox": True,
        "voice_api_url": PIPER_URL,
        "piper_api_url": PIPER_URL,
        "piper_health_path": PIPER_HEALTH,
        "piper_voice": PIPER_VOICE,
        "piper_voice_id": PIPER_VOICE,
        "intro_voice_model": PIPER_VOICE,
        "intro_voice_id": PIPER_VOICE,
        "request_voice_id": PIPER_VOICE,
    }
    data.update(piper_fields)
    for key in list(data.keys()):
        lowered = key.lower()
        if "voicebox" in lowered or lowered in {"vb_api_url", "vb_url", "vb_voice_id", "use_voicebox"}:
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

    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Repaired {path}")
    print(f"Backup: {backup}")
    print(f"Request intros: Piper only ({PIPER_URL}, voice={PIPER_VOICE})")
    print("Voicebox fields removed. Restart MoRequestsWatcher now.")


def main() -> int:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("requests.json")
    if not target.exists():
        print(f"Missing {target}")
        return 1
    repair(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

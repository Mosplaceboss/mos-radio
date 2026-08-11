"""Verify requests TTS is Piper-only with no Voicebox fields."""

from __future__ import annotations

import sys
from pathlib import Path

STUDIO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(STUDIO_ROOT))

from app.core.integration_settings import DEFAULT_INTEGRATION, normalize_integration_settings
from app.core.requests_model import normalize_requests_data
from app.core.tts_settings import (
    DEFAULT_PIPER_API_URL,
    REQUEST_VOICEBOX_KEYS,
    TTS_PROVIDER_PIPER,
    remove_voicebox_from_requests,
    resolve_tts_settings,
    tts_fields_for_requests,
)


def main() -> int:
    errors: list[str] = []

    if DEFAULT_INTEGRATION.get("tts_provider") != TTS_PROVIDER_PIPER:
        errors.append("DEFAULT_INTEGRATION tts_provider is not piper")
    for key in REQUEST_VOICEBOX_KEYS:
        if key in DEFAULT_INTEGRATION:
            errors.append(f"DEFAULT_INTEGRATION still includes {key}")

    integration = normalize_integration_settings(
        {"integration": {"voicebox_api_url": "http://127.0.0.1:7860", "tts_provider": "voicebox"}}
    )
    tts = resolve_tts_settings(integration)
    if tts["provider"] != TTS_PROVIDER_PIPER:
        errors.append(f"provider={tts['provider']}, expected piper")
    if tts["api_url"] != DEFAULT_PIPER_API_URL.rstrip("/"):
        errors.append(f"api_url={tts['api_url']}, expected Piper")
    for key in REQUEST_VOICEBOX_KEYS:
        if key in integration:
            errors.append(f"apply_tts_defaults left {key} on integration")

    fields = tts_fields_for_requests(integration)
    if fields.get("tts_provider") != "piper":
        errors.append("requests TTS provider is not piper")
    for key in REQUEST_VOICEBOX_KEYS:
        if key in fields:
            errors.append(f"tts_fields_for_requests still includes {key}")
    if any("voicebox" in key.lower() for key in fields):
        errors.append("tts_fields_for_requests still has a voicebox-named key")

    requests = normalize_requests_data(
        {
            "tts_provider": "voicebox",
            "voicebox_api_url": "http://127.0.0.1:7860",
            "voicebox_url": "http://127.0.0.1:7860",
            "use_voicebox": True,
            "allowed_formats": ["Classic Rock"],
        }
    )
    if requests.get("tts_provider") != "piper":
        errors.append("normalize_requests_data did not force piper")
    for key in REQUEST_VOICEBOX_KEYS:
        if key in requests:
            errors.append(f"normalize_requests_data left {key}")
    if any(isinstance(v, str) and "7860" in v for v in requests.values()):
        errors.append("normalize_requests_data left a :7860 URL")

    scrubbed = remove_voicebox_from_requests(
        {
            "voicebox_api_url": "http://127.0.0.1:7860",
            "tts_api_url": "http://127.0.0.1:5000",
            "use_voicebox": True,
        }
    )
    if "voicebox_api_url" in scrubbed or "use_voicebox" in scrubbed:
        errors.append("remove_voicebox_from_requests did not delete Voicebox keys")

    if errors:
        print("TTS SETTINGS FAILURES:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("Piper-only request TTS verified (no Voicebox fields).")
    print(f"Default API: {DEFAULT_PIPER_API_URL}")
    print(f"Published keys: {sorted(fields)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Verify Piper is the default TTS provider for Studio and requests publish."""

from __future__ import annotations

import sys
from pathlib import Path

STUDIO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(STUDIO_ROOT))

from app.core.integration_settings import DEFAULT_INTEGRATION, normalize_integration_settings
from app.core.requests_model import normalize_requests_data
from app.core.tts_settings import (
    DEFAULT_PIPER_API_URL,
    TTS_PROVIDER_PIPER,
    resolve_tts_settings,
    tts_fields_for_requests,
)


def main() -> int:
    errors: list[str] = []

    if DEFAULT_INTEGRATION.get("tts_provider") != TTS_PROVIDER_PIPER:
        errors.append("DEFAULT_INTEGRATION tts_provider is not piper")
    if "5000" not in str(DEFAULT_INTEGRATION.get("tts_api_url", "")):
        errors.append("DEFAULT_INTEGRATION tts_api_url is not Piper port 5000")

    settings = {
        "integration": {
            # Legacy Voicebox-only config should migrate to Piper defaults.
            "voicebox_api_url": "http://127.0.0.1:7860",
        }
    }
    integration = normalize_integration_settings(settings)
    tts = resolve_tts_settings(integration)
    if tts["provider"] != TTS_PROVIDER_PIPER:
        errors.append(f"Legacy settings resolved provider={tts['provider']}, expected piper")
    if tts["api_url"] != DEFAULT_PIPER_API_URL.rstrip("/"):
        errors.append(f"Legacy settings resolved api_url={tts['api_url']}, expected {DEFAULT_PIPER_API_URL}")
    if tts["service_name"] != "Piper":
        errors.append(f"Service light name is {tts['service_name']}, expected Piper")

    # Explicit Piper URL must win over leftover Voicebox URL.
    piper_integration = normalize_integration_settings(
        {
            "integration": {
                "tts_provider": "piper",
                "tts_api_url": "http://127.0.0.1:5000",
                "voicebox_api_url": "http://127.0.0.1:7860",
            }
        }
    )
    fields = tts_fields_for_requests(piper_integration)
    if fields.get("tts_provider") != "piper":
        errors.append("Published requests TTS provider is not piper")
    if fields.get("tts_api_url") != "http://127.0.0.1:5000":
        errors.append(f"Published requests TTS URL wrong: {fields.get('tts_api_url')}")
    if fields.get("voicebox_api_url"):
        errors.append("Published requests still include a Voicebox API URL under Piper")

    requests = normalize_requests_data(
        {
            "tts_provider": "piper",
            "voicebox_api_url": "http://127.0.0.1:7860",
            "allowed_formats": ["Classic Rock"],
        }
    )
    if requests.get("tts_provider") != "piper":
        errors.append("normalize_requests_data did not keep piper provider")
    if "7860" in str(requests.get("tts_api_url", "")):
        errors.append("normalize_requests_data kept Voicebox port for Piper provider")
    if requests.get("voicebox_api_url"):
        errors.append("normalize_requests_data left voicebox_api_url set under Piper")

    if errors:
        print("TTS SETTINGS FAILURES:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("Piper TTS settings verified.")
    print(f"Default API: {DEFAULT_PIPER_API_URL}")
    print(f"Published keys: {sorted(fields)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

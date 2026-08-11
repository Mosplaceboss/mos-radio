"""Verify Piper-only TTS for Studio and requests publish (Voicebox retired)."""

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
    scrub_voicebox_endpoints,
    tts_fields_for_requests,
)


def main() -> int:
    errors: list[str] = []

    if DEFAULT_INTEGRATION.get("tts_provider") != TTS_PROVIDER_PIPER:
        errors.append("DEFAULT_INTEGRATION tts_provider is not piper")
    if "5000" not in str(DEFAULT_INTEGRATION.get("tts_api_url", "")):
        errors.append("DEFAULT_INTEGRATION tts_api_url is not Piper port 5000")
    if "7860" in str(DEFAULT_INTEGRATION.get("voicebox_api_url", "")):
        errors.append("DEFAULT_INTEGRATION still points voicebox_api_url at Voicebox :7860")

    settings = {
        "integration": {
            "tts_provider": "voicebox",
            "voicebox_api_url": "http://127.0.0.1:7860",
        }
    }
    integration = normalize_integration_settings(settings)
    tts = resolve_tts_settings(integration)
    if tts["provider"] != TTS_PROVIDER_PIPER:
        errors.append(f"Forced provider={tts['provider']}, expected piper")
    if tts["api_url"] != DEFAULT_PIPER_API_URL.rstrip("/"):
        errors.append(f"Forced api_url={tts['api_url']}, expected {DEFAULT_PIPER_API_URL}")
    if "7860" in str(integration.get("voicebox_api_url", "")):
        errors.append("apply_tts_defaults left Voicebox :7860 in voicebox_api_url")
    if integration.get("voicebox_api_url") != DEFAULT_PIPER_API_URL.rstrip("/"):
        errors.append("Legacy voicebox_api_url was not remapped to Piper")

    fields = tts_fields_for_requests(integration)
    if fields.get("tts_provider") != "piper":
        errors.append("Published requests TTS provider is not piper")
    if fields.get("use_voicebox") is not False:
        errors.append("Published requests did not disable use_voicebox")
    if "7860" in str(fields.get("voicebox_api_url", "")):
        errors.append("Published voicebox_api_url still points at Voicebox")
    if fields.get("voicebox_api_url") != fields.get("tts_api_url"):
        errors.append("Legacy voicebox_api_url was not remapped to the Piper URL")

    requests = normalize_requests_data(
        {
            "tts_provider": "voicebox",
            "voicebox_api_url": "http://127.0.0.1:7860",
            "allowed_formats": ["Classic Rock"],
        }
    )
    if requests.get("tts_provider") != "piper":
        errors.append("normalize_requests_data did not force piper")
    if "7860" in str(requests.get("tts_api_url", "")) or "7860" in str(requests.get("voicebox_api_url", "")):
        errors.append("normalize_requests_data left a Voicebox :7860 URL")

    scrubbed = scrub_voicebox_endpoints(
        {"voicebox_api_url": "http://127.0.0.1:7860", "tts_api_url": "http://127.0.0.1:7860"},
        DEFAULT_PIPER_API_URL,
    )
    if any("7860" in str(value) for value in scrubbed.values() if isinstance(value, str)):
        errors.append("scrub_voicebox_endpoints left a :7860 URL")

    if errors:
        print("TTS SETTINGS FAILURES:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("Piper-only TTS settings verified.")
    print(f"Default API: {DEFAULT_PIPER_API_URL}")
    print(f"Legacy voicebox_api_url remapped to: {fields.get('voicebox_api_url')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

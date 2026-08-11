"""Resolve station TTS provider settings (Piper by default; Voicebox legacy)."""

from __future__ import annotations

from typing import Any

TTS_PROVIDER_PIPER = "piper"
TTS_PROVIDER_VOICEBOX = "voicebox"
TTS_PROVIDERS = (TTS_PROVIDER_PIPER, TTS_PROVIDER_VOICEBOX)

DEFAULT_TTS_PROVIDER = TTS_PROVIDER_PIPER
DEFAULT_PIPER_API_URL = "http://127.0.0.1:5000"
DEFAULT_PIPER_HEALTH_PATH = "/voices"
DEFAULT_VOICEBOX_API_URL = "http://127.0.0.1:7860"
DEFAULT_VOICEBOX_HEALTH_PATH = "/"

# Service light / alert name used when Piper is active.
TTS_SERVICE_PIPER = "Piper"
TTS_SERVICE_VOICEBOX = "Voicebox"


def normalize_tts_provider(value: Any) -> str:
    provider = str(value or DEFAULT_TTS_PROVIDER).strip().lower()
    if provider in {"vb", "voice-box", "voice_box"}:
        return TTS_PROVIDER_VOICEBOX
    if provider in TTS_PROVIDERS:
        return provider
    return DEFAULT_TTS_PROVIDER


def _looks_like_legacy_voicebox_url(url: str) -> bool:
    lowered = url.lower()
    return "7860" in lowered or "voicebox" in lowered


def resolve_tts_settings(integration: dict[str, Any] | None) -> dict[str, Any]:
    """Return canonical TTS settings for monitoring, UI, and request publish."""
    data = integration if isinstance(integration, dict) else {}
    provider = normalize_tts_provider(data.get("tts_provider"))

    if provider == TTS_PROVIDER_PIPER:
        url = (
            str(data.get("tts_api_url") or data.get("piper_api_url") or "").strip()
        )
        if not url:
            legacy = str(data.get("voicebox_api_url") or "").strip()
            # Keep only non-Voicebox legacy URLs if an operator already pointed
            # the old field at Piper.
            if legacy and not _looks_like_legacy_voicebox_url(legacy):
                url = legacy
            else:
                url = DEFAULT_PIPER_API_URL
        health_path = str(
            data.get("tts_health_path")
            or data.get("piper_health_path")
            or DEFAULT_PIPER_HEALTH_PATH
        ).strip() or DEFAULT_PIPER_HEALTH_PATH
        service_name = TTS_SERVICE_PIPER
        default_port = 5000
        not_responding = "Piper API not responding"
    else:
        url = str(
            data.get("tts_api_url")
            or data.get("voicebox_api_url")
            or DEFAULT_VOICEBOX_API_URL
        ).strip() or DEFAULT_VOICEBOX_API_URL
        health_path = str(
            data.get("tts_health_path")
            or data.get("voicebox_health_path")
            or DEFAULT_VOICEBOX_HEALTH_PATH
        ).strip() or DEFAULT_VOICEBOX_HEALTH_PATH
        service_name = TTS_SERVICE_VOICEBOX
        default_port = 7860
        not_responding = "Voicebox API not responding"

    if not health_path.startswith("/"):
        health_path = f"/{health_path}"

    return {
        "provider": provider,
        "api_url": url.rstrip("/"),
        "health_path": health_path,
        "service_name": service_name,
        "default_port": default_port,
        "not_responding_detail": not_responding,
    }


def apply_tts_defaults(integration: dict[str, Any]) -> dict[str, Any]:
    """Normalize TTS fields on an integration dict in place and return it."""
    resolved = resolve_tts_settings(integration)
    integration["tts_provider"] = resolved["provider"]
    integration["tts_api_url"] = resolved["api_url"]
    integration["tts_health_path"] = resolved["health_path"]
    if resolved["provider"] == TTS_PROVIDER_PIPER:
        integration["piper_api_url"] = resolved["api_url"]
        integration["piper_health_path"] = resolved["health_path"]
    else:
        # Keep legacy Voicebox keys aligned when that provider is selected.
        integration["voicebox_api_url"] = resolved["api_url"]
        integration["voicebox_health_path"] = resolved["health_path"]
    return integration


def tts_fields_for_requests(integration: dict[str, Any] | None) -> dict[str, Any]:
    """Fields published into live requests.json for MoRequestsWatcher."""
    resolved = resolve_tts_settings(integration)
    return {
        "tts_provider": resolved["provider"],
        "tts_api_url": resolved["api_url"],
        "tts_health_path": resolved["health_path"],
        # Compatibility aliases some engines may still read.
        "voice_api_url": resolved["api_url"],
        "piper_api_url": resolved["api_url"] if resolved["provider"] == TTS_PROVIDER_PIPER else "",
        "voicebox_api_url": resolved["api_url"] if resolved["provider"] == TTS_PROVIDER_VOICEBOX else "",
    }

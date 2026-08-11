"""Resolve station TTS settings. Production uses Piper only."""

from __future__ import annotations

from typing import Any

TTS_PROVIDER_PIPER = "piper"
# Retained only so old configs that say "voicebox" can be remapped to Piper.
TTS_PROVIDER_VOICEBOX = "voicebox"
TTS_PROVIDERS = (TTS_PROVIDER_PIPER,)

DEFAULT_TTS_PROVIDER = TTS_PROVIDER_PIPER
DEFAULT_PIPER_API_URL = "http://127.0.0.1:5000"
DEFAULT_PIPER_HEALTH_PATH = "/voices"

# Service light / alert name.
TTS_SERVICE_PIPER = "Piper"
# Alias for older UI lookups that still ask for "Voicebox".
TTS_SERVICE_VOICEBOX = "Piper"

VOICEBOX_LEGACY_KEYS = (
    "voicebox_api_url",
    "voicebox_url",
    "voicebox_endpoint",
    "vb_api_url",
    "vb_url",
)


def normalize_tts_provider(value: Any) -> str:
    """Always return piper. Voicebox is retired for Mo's Place production."""
    _ = value
    return TTS_PROVIDER_PIPER


def _looks_like_legacy_voicebox_url(url: str) -> bool:
    lowered = url.lower()
    return "7860" in lowered or "voicebox" in lowered


def _first_nonempty(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def resolve_tts_settings(integration: dict[str, Any] | None) -> dict[str, Any]:
    """Return canonical Piper TTS settings for monitoring, UI, and request publish."""
    data = integration if isinstance(integration, dict) else {}
    provider = TTS_PROVIDER_PIPER

    url = _first_nonempty(
        data.get("tts_api_url"),
        data.get("piper_api_url"),
        data.get("voice_api_url"),
    )
    if not url:
        legacy = _first_nonempty(*(data.get(key) for key in VOICEBOX_LEGACY_KEYS))
        # Only reuse a legacy URL if it is already pointing at Piper (not :7860).
        if legacy and not _looks_like_legacy_voicebox_url(legacy):
            url = legacy
        else:
            url = DEFAULT_PIPER_API_URL

    # Never keep a retired Voicebox endpoint.
    if _looks_like_legacy_voicebox_url(url):
        url = DEFAULT_PIPER_API_URL

    health_path = _first_nonempty(
        data.get("tts_health_path"),
        data.get("piper_health_path"),
        DEFAULT_PIPER_HEALTH_PATH,
    ) or DEFAULT_PIPER_HEALTH_PATH
    if not health_path.startswith("/"):
        health_path = f"/{health_path}"

    return {
        "provider": provider,
        "api_url": url.rstrip("/"),
        "health_path": health_path,
        "service_name": TTS_SERVICE_PIPER,
        "default_port": 5000,
        "not_responding_detail": "Piper API not responding",
    }


def apply_tts_defaults(integration: dict[str, Any]) -> dict[str, Any]:
    """Force Piper fields on an integration dict and scrub Voicebox :7860 leftovers."""
    resolved = resolve_tts_settings(integration)
    integration["tts_provider"] = resolved["provider"]
    integration["tts_api_url"] = resolved["api_url"]
    integration["tts_health_path"] = resolved["health_path"]
    integration["piper_api_url"] = resolved["api_url"]
    integration["piper_health_path"] = resolved["health_path"]
    integration["voice_api_url"] = resolved["api_url"]
    integration["voice_engine"] = TTS_PROVIDER_PIPER
    integration["use_piper"] = True
    integration["use_voicebox"] = False
    # MoRequestsWatcher and older tools still read voicebox_api_url. Point it at
    # Piper so request intros cannot fall back to the retired Voicebox service.
    for key in VOICEBOX_LEGACY_KEYS:
        integration[key] = resolved["api_url"]
    integration["voicebox_health_path"] = resolved["health_path"]
    return integration


def tts_fields_for_requests(integration: dict[str, Any] | None) -> dict[str, Any]:
    """Fields published into live requests.json for MoRequestsWatcher.

    Includes Piper-first keys plus legacy Voicebox-named keys remapped to the
    Piper URL so engines that still look up voicebox_api_url hit Piper only.
    """
    resolved = resolve_tts_settings(integration)
    url = resolved["api_url"]
    health = resolved["health_path"]
    fields = {
        "tts_provider": TTS_PROVIDER_PIPER,
        "tts_api_url": url,
        "tts_health_path": health,
        "voice_engine": TTS_PROVIDER_PIPER,
        "use_piper": True,
        "use_voicebox": False,
        "voice_api_url": url,
        "piper_api_url": url,
        "piper_health_path": health,
        # Legacy name → Piper endpoint (do not leave empty; empty may trigger
        # hard-coded Voicebox defaults inside older watchers).
        "voicebox_api_url": url,
        "voicebox_url": url,
        "voicebox_endpoint": url,
        "voicebox_health_path": health,
    }
    return fields


def scrub_voicebox_endpoints(data: dict[str, Any], piper_url: str) -> dict[str, Any]:
    """Rewrite any Voicebox :7860 values in a config dict to the Piper URL."""
    target = piper_url.rstrip("/") or DEFAULT_PIPER_API_URL.rstrip("/")
    for key, value in list(data.items()):
        if not isinstance(value, str):
            continue
        if _looks_like_legacy_voicebox_url(value):
            data[key] = target
        elif key.lower() in {item.lower() for item in VOICEBOX_LEGACY_KEYS} and not value.strip():
            data[key] = target
    data["tts_provider"] = TTS_PROVIDER_PIPER
    data["voice_engine"] = TTS_PROVIDER_PIPER
    data["use_piper"] = True
    data["use_voicebox"] = False
    return data

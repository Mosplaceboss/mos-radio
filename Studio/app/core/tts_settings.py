"""Resolve station TTS settings. Production uses Piper only for requests."""

from __future__ import annotations

from typing import Any

TTS_PROVIDER_PIPER = "piper"
TTS_PROVIDERS = (TTS_PROVIDER_PIPER,)

DEFAULT_TTS_PROVIDER = TTS_PROVIDER_PIPER
DEFAULT_PIPER_API_URL = "http://127.0.0.1:5000"
DEFAULT_PIPER_HEALTH_PATH = "/voices"

TTS_SERVICE_PIPER = "Piper"
# Alias for older UI lookups that still ask for "Voicebox".
TTS_SERVICE_VOICEBOX = "Piper"

# Keys that must never appear on live requests.json.
REQUEST_VOICEBOX_KEYS = (
    "voicebox_api_url",
    "voicebox_url",
    "voicebox_endpoint",
    "voicebox_health_path",
    "vb_api_url",
    "vb_url",
    "use_voicebox",
)


def normalize_tts_provider(value: Any) -> str:
    """Always return piper. Voicebox is retired for request TTS."""
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

    url = _first_nonempty(
        data.get("tts_api_url"),
        data.get("piper_api_url"),
        data.get("voice_api_url"),
    )
    if not url:
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
        "provider": TTS_PROVIDER_PIPER,
        "api_url": url.rstrip("/"),
        "health_path": health_path,
        "service_name": TTS_SERVICE_PIPER,
        "default_port": 5000,
        "not_responding_detail": "Piper API not responding",
    }


def apply_tts_defaults(integration: dict[str, Any]) -> dict[str, Any]:
    """Force Piper fields on Studio integration settings."""
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
    # Do not keep a Voicebox URL around for anything request-related.
    for key in REQUEST_VOICEBOX_KEYS:
        integration.pop(key, None)
    return integration


def tts_fields_for_requests(integration: dict[str, Any] | None) -> dict[str, Any]:
    """Piper-only fields published into live requests.json.

    Voicebox keys are intentionally omitted — requests must not call Voicebox.
    """
    resolved = resolve_tts_settings(integration)
    url = resolved["api_url"]
    health = resolved["health_path"]
    return {
        "tts_provider": TTS_PROVIDER_PIPER,
        "tts_api_url": url,
        "tts_health_path": health,
        "voice_engine": TTS_PROVIDER_PIPER,
        "use_piper": True,
        "voice_api_url": url,
        "piper_api_url": url,
        "piper_health_path": health,
    }


def remove_voicebox_from_requests(data: dict[str, Any]) -> dict[str, Any]:
    """Delete every Voicebox field from a requests config dict."""
    for key in list(data.keys()):
        lowered = key.lower()
        if lowered in {item.lower() for item in REQUEST_VOICEBOX_KEYS} or lowered.startswith("voicebox"):
            data.pop(key, None)
            continue
        value = data.get(key)
        if isinstance(value, str) and _looks_like_legacy_voicebox_url(value):
            # Non-voicebox-named fields must not keep a :7860 URL either.
            if key in {"tts_api_url", "piper_api_url", "voice_api_url", "tts_health_path", "piper_health_path"}:
                data[key] = DEFAULT_PIPER_API_URL if "health" not in key else DEFAULT_PIPER_HEALTH_PATH
            else:
                data.pop(key, None)
    data["tts_provider"] = TTS_PROVIDER_PIPER
    data["voice_engine"] = TTS_PROVIDER_PIPER
    data["use_piper"] = True
    data.pop("use_voicebox", None)
    return data


def scrub_voicebox_endpoints(data: dict[str, Any], piper_url: str = "") -> dict[str, Any]:
    """Backward-compatible alias — strips Voicebox from request configs."""
    _ = piper_url
    return remove_voicebox_from_requests(data)

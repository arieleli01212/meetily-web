"""Connectivity checks for external services.

Each check returns a small dict:
    {"status": "ok" | "unreachable" | "cloud", "url": ..., ...}

log_startup_checks() runs all checks and emits structured log lines at INFO or
WARNING level so the operator can see at a glance which services are reachable.
"""
from __future__ import annotations

import logging

import httpx

logger = logging.getLogger("meetily.startup")

# Cloud providers — no sensible way to probe them without billing a real call.
_CLOUD_PROVIDERS = {"anthropic", "groq", "openrouter"}

# LLM health paths: Ollama exposes /api/version; a generic OpenAI-compatible
# server usually exposes /models (unauthenticated listing).
_LLM_PROBE_PATH: dict[str, str] = {
    "ollama": "/api/version",
    "openai": "/models",
}


def _get(url: str, path: str, timeout: float = 4.0) -> dict:
    """GET {url}{path} and return a status dict. Never raises."""
    full = url.rstrip("/") + path
    try:
        r = httpx.get(full, timeout=timeout, follow_redirects=True)
        return {"status": "ok", "http": r.status_code, "url": url}
    except httpx.ConnectError:
        return {"status": "unreachable", "error": "connection refused", "url": url}
    except httpx.TimeoutException:
        return {"status": "unreachable", "error": f"timed out after {timeout}s", "url": url}
    except Exception as exc:
        return {"status": "unreachable", "error": str(exc)[:120], "url": url}


def check_whisper(url: str) -> dict:
    """Probe the whisper.cpp HTTP server (GET /)."""
    result = _get(url, "/")
    result["service"] = "whisper"
    return result


def check_diarize(url: str) -> dict:
    """Probe the WhisperX diarization service (GET /health)."""
    result = _get(url, "/health")
    result["service"] = "diarize"
    return result


def check_llm(provider: str, base_url: str) -> dict:
    """Probe the LLM endpoint. Cloud providers are skipped (reported as 'cloud')."""
    if provider in _CLOUD_PROVIDERS:
        return {"status": "cloud", "service": "llm", "provider": provider, "url": base_url}
    path = _LLM_PROBE_PATH.get(provider, "/models")
    result = _get(base_url, path)
    result["service"] = "llm"
    result["provider"] = provider
    return result


def run_startup_checks(settings) -> dict[str, dict]:
    """Probe all three external services and log the results.

    Returns the raw check dicts keyed by service name. Intended to be called
    once at application startup — does NOT raise on failure so the backend
    boots even when external services are temporarily down.
    """
    checks = {
        "whisper": check_whisper(settings.whisper_server_url),
        "diarize": check_diarize(settings.diarize_server_url),
        "llm":     check_llm(settings.llm_provider, settings.llm_base_url),
    }

    _log_results(checks)
    return checks


# ---- logging helpers -------------------------------------------------------

def _log_results(checks: dict[str, dict]) -> None:
    logger.info("─" * 60)
    logger.info("Meetily — external service connectivity check")
    logger.info("─" * 60)
    for name, r in checks.items():
        _log_one(name, r)
    logger.info("─" * 60)


def _log_one(name: str, r: dict) -> None:
    status = r["status"]
    url = r.get("url", "")
    provider = r.get("provider", "")
    label = f"{name:<10}"

    if status == "ok":
        http = r.get("http", "")
        logger.info("  ✓  %s OK          %s  (HTTP %s)", label, url, http)
    elif status == "cloud":
        logger.info("  ~  %s CLOUD        %s  (%s — not probed)", label, url, provider)
    else:
        error = r.get("error", "")
        logger.warning("  ✗  %s UNREACHABLE  %s  — %s", label, url, error)

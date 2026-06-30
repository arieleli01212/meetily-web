"""Proxy browser-captured audio to an external whisper.cpp server."""
from __future__ import annotations

import logging
import time

import httpx

logger = logging.getLogger("meetily.transcribe")

WHISPER_TIMEOUT = 300.0


def transcribe_audio(
    audio: bytes,
    filename: str,
    content_type: str,
    whisper_url: str,
    client: httpx.Client,
    language: str = "",
) -> str:
    kb = len(audio) / 1024
    logger.info(
        "→ transcribe  file=%s  size=%.1f KB  url=%s  lang=%s",
        filename,
        kb,
        whisper_url,
        language or "auto",
    )

    files = {"file": (filename, audio, content_type or "audio/wav")}
    data: dict[str, str] = {"response_format": "json"}
    if language:
        data["language"] = language

    t0 = time.perf_counter()
    resp = client.post(
        f"{whisper_url.rstrip('/')}/inference",
        files=files,
        data=data,
        timeout=WHISPER_TIMEOUT,
    )
    elapsed = time.perf_counter() - t0
    resp.raise_for_status()

    ctype = resp.headers.get("content-type", "")
    if "application/json" in ctype:
        body = resp.json()
        text = (body.get("text") or "").strip()
    else:
        text = resp.text.strip()

    logger.info(
        "← transcribe  chars=%d  elapsed=%.2fs",
        len(text),
        elapsed,
    )
    return text

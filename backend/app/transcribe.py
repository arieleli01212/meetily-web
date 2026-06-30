"""Proxy browser-captured audio to an external whisper.cpp server.

The browser records audio and POSTs it here; we forward it to the configured
WHISPER_SERVER_URL (a whisper.cpp HTTP server exposing ``/inference``) and
return the transcript text. Keeping whisper external means the air-gapped
deployment just points at a local whisper container by URL.
"""
from __future__ import annotations

import httpx

WHISPER_TIMEOUT = 300.0


def transcribe_audio(audio: bytes, filename: str, content_type: str,
                     whisper_url: str, client: httpx.Client,
                     language: str = "") -> str:
    files = {"file": (filename, audio, content_type or "audio/wav")}
    # whisper.cpp server returns plain text or JSON depending on params; ask
    # for JSON and tolerate both.
    data = {"response_format": "json"}
    # Force a language (e.g. "he" for Hebrew) when configured; otherwise the
    # whisper server auto-detects. Forcing avoids mis-detection on short chunks.
    if language:
        data["language"] = language
    resp = client.post(
        f"{whisper_url.rstrip('/')}/inference",
        files=files, data=data, timeout=WHISPER_TIMEOUT,
    )
    resp.raise_for_status()
    ctype = resp.headers.get("content-type", "")
    if "application/json" in ctype:
        body = resp.json()
        return (body.get("text") or "").strip()
    return resp.text.strip()

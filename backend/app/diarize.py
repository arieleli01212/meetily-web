"""Proxy full-meeting audio to an external WhisperX diarization service.

Post-meeting, the browser uploads the entire recording; we forward it to the
configured DIARIZE_SERVER_URL (a WhisperX service exposing
``/transcribe-diarize``) and get back speaker-labeled segments. Like whisper
and the LLM, this engine is external and reached purely by URL so it can run
air-gapped on the operator's hardware.
"""
from __future__ import annotations

from typing import Optional

import httpx

DIARIZE_TIMEOUT = 1800.0  # diarizing a long meeting on CPU can be slow


def diarize_audio(audio: bytes, filename: str, content_type: str,
                  diarize_url: str, client: httpx.Client,
                  language: str = "",
                  min_speakers: Optional[int] = None,
                  max_speakers: Optional[int] = None) -> dict:
    files = {"file": (filename, audio, content_type or "audio/wav")}
    data: dict[str, str] = {}
    if language:
        data["language"] = language
    if min_speakers is not None:
        data["min_speakers"] = str(min_speakers)
    if max_speakers is not None:
        data["max_speakers"] = str(max_speakers)
    resp = client.post(
        f"{diarize_url.rstrip('/')}/transcribe-diarize",
        files=files, data=data, timeout=DIARIZE_TIMEOUT,
    )
    resp.raise_for_status()
    body = resp.json()
    return {
        "language": body.get("language", ""),
        "segments": body.get("segments", []),
    }

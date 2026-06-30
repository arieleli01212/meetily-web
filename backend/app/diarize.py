"""Proxy full-meeting audio to an external WhisperX diarization service."""
from __future__ import annotations

import logging
import time
from typing import Optional

import httpx

logger = logging.getLogger("meetily.diarize")

DIARIZE_TIMEOUT = 1800.0  # diarizing a long meeting on CPU can be slow


def diarize_audio(
    audio_path: str,
    filename: str,
    content_type: str,
    diarize_url: str,
    client: httpx.Client,
    language: str = "",
    min_speakers: Optional[int] = None,
    max_speakers: Optional[int] = None,
) -> dict:
    """POST the audio file at *audio_path* to the WhisperX service.

    Uses an open file handle so the multipart body is streamed from disk —
    the full audio is never loaded into Python memory.
    """
    import os

    file_size_mb = os.path.getsize(audio_path) / 1024 / 1024
    logger.info(
        "→ diarize  file=%s  size=%.1f MB  url=%s  lang=%s  speakers=%s–%s",
        filename,
        file_size_mb,
        diarize_url,
        language or "auto",
        min_speakers if min_speakers is not None else "*",
        max_speakers if max_speakers is not None else "*",
    )

    data: dict[str, str] = {}
    if language:
        data["language"] = language
    if min_speakers is not None:
        data["min_speakers"] = str(min_speakers)
    if max_speakers is not None:
        data["max_speakers"] = str(max_speakers)

    t0 = time.perf_counter()
    with open(audio_path, "rb") as fh:
        files = {"file": (filename, fh, content_type or "audio/wav")}
        resp = client.post(
            f"{diarize_url.rstrip('/')}/transcribe-diarize",
            files=files,
            data=data,
            timeout=DIARIZE_TIMEOUT,
        )
    elapsed = time.perf_counter() - t0

    resp.raise_for_status()
    body = resp.json()
    segments = body.get("segments", [])
    detected_lang = body.get("language", "?")

    logger.info(
        "← diarize  segments=%d  lang=%s  elapsed=%.1fs",
        len(segments),
        detected_lang,
        elapsed,
    )
    return {"language": detected_lang, "segments": segments}

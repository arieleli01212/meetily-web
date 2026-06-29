"""Transcript summarization.

Splits a transcript into overlapping chunks, asks the configured LLM to
summarize each into a structured object, and merges the chunk results into a
single ``{summary, action_items, key_points}`` payload — mirroring meetily's
process-transcript behaviour.
"""
from __future__ import annotations

import json
import re
import time
from typing import Optional

SYSTEM_PROMPT = (
    "You are a meeting summarization assistant. Summarize the transcript chunk "
    "and respond ONLY with a JSON object with keys: \"summary\" (string), "
    "\"action_items\" (array of strings), and \"key_points\" (array of strings)."
)


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split text into chunks of ``chunk_size`` with ``overlap`` characters
    shared between consecutive chunks."""
    if chunk_size <= 0:
        return [text]
    if len(text) <= chunk_size:
        return [text]
    step = max(1, chunk_size - max(0, overlap))
    chunks = []
    for start in range(0, len(text), step):
        chunk = text[start:start + chunk_size]
        if chunk:
            chunks.append(chunk)
        if start + chunk_size >= len(text):
            break
    return chunks


def _parse_response(raw: str) -> dict:
    """Parse an LLM response into the structured summary shape, tolerating
    plain-text or fenced-JSON responses."""
    text = raw.strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            return {
                "summary": str(data.get("summary", "")).strip(),
                "action_items": list(data.get("action_items", []) or []),
                "key_points": list(data.get("key_points", []) or []),
            }
        except (json.JSONDecodeError, AttributeError):
            pass
    return {"summary": text, "action_items": [], "key_points": []}


def summarize_transcript(text: str, provider, chunk_size: int, overlap: int,
                         custom_prompt: Optional[str] = None) -> dict:
    """Summarize ``text`` using ``provider``, returning a merged structured
    summary. ``provider`` is any object exposing ``complete(prompt, system)``."""
    chunks = chunk_text(text, chunk_size, overlap)
    summaries: list[str] = []
    action_items: list[str] = []
    key_points: list[str] = []

    for chunk in chunks:
        instruction = custom_prompt or "Summarize this meeting transcript chunk."
        prompt = f"{instruction}\n\nTranscript chunk:\n{chunk}"
        raw = provider.complete(prompt, system=SYSTEM_PROMPT)
        parsed = _parse_response(raw)
        if parsed["summary"]:
            summaries.append(parsed["summary"])
        action_items.extend(parsed["action_items"])
        key_points.extend(parsed["key_points"])

    return {
        "summary": "\n\n".join(summaries),
        "action_items": action_items,
        "key_points": key_points,
    }


def run_summary(meeting_id: str, text: str, provider, db, chunk_size: int,
                overlap: int, custom_prompt: Optional[str] = None) -> None:
    """Orchestrate a summary run, persisting status/result to summary_processes."""
    start = time.time()
    db.create_process(meeting_id)
    try:
        chunks = chunk_text(text, chunk_size, overlap)
        result = summarize_transcript(text, provider, chunk_size, overlap,
                                      custom_prompt)
        db.update_process(
            meeting_id,
            status="completed",
            result=json.dumps(result),
            chunk_count=len(chunks),
            processing_time=time.time() - start,
            end_time=None,
        )
    except Exception as exc:  # noqa: BLE001 — surface any provider/parse failure
        db.update_process(
            meeting_id,
            status="failed",
            error=str(exc),
            processing_time=time.time() - start,
        )

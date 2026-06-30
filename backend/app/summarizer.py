"""Transcript summarization with per-chunk progress logging."""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Optional

logger = logging.getLogger("meetily.summarizer")

SYSTEM_PROMPT = (
    "You are a meeting summarization assistant. Summarize the transcript chunk "
    "and respond ONLY with a JSON object with keys: \"summary\" (string), "
    "\"action_items\" (array of strings), and \"key_points\" (array of strings)."
)


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    if chunk_size <= 0:
        return [text]
    if len(text) <= chunk_size:
        return [text]
    step = max(1, chunk_size - max(0, overlap))
    chunks = []
    for start in range(0, len(text), step):
        chunk = text[start : start + chunk_size]
        if chunk:
            chunks.append(chunk)
        if start + chunk_size >= len(text):
            break
    return chunks


def _parse_response(raw: str) -> dict:
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


def summarize_transcript(
    text: str,
    provider,
    chunk_size: int,
    overlap: int,
    custom_prompt: Optional[str] = None,
) -> dict:
    chunks = chunk_text(text, chunk_size, overlap)
    total = len(chunks)
    logger.info(
        "summarize  total_chars=%d  chunks=%d  chunk_size=%d  overlap=%d",
        len(text),
        total,
        chunk_size,
        overlap,
    )

    summaries: list[str] = []
    action_items: list[str] = []
    key_points: list[str] = []

    for i, chunk in enumerate(chunks, 1):
        logger.info("  chunk %d/%d  chars=%d  → LLM …", i, total, len(chunk))
        t0 = time.perf_counter()
        instruction = custom_prompt or "Summarize this meeting transcript chunk."
        prompt = f"{instruction}\n\nTranscript chunk:\n{chunk}"
        raw = provider.complete(prompt, system=SYSTEM_PROMPT)
        parsed = _parse_response(raw)
        elapsed = time.perf_counter() - t0
        logger.info(
            "  chunk %d/%d  ✓  %.2fs  actions=%d  points=%d",
            i,
            total,
            elapsed,
            len(parsed["action_items"]),
            len(parsed["key_points"]),
        )
        if parsed["summary"]:
            summaries.append(parsed["summary"])
        action_items.extend(parsed["action_items"])
        key_points.extend(parsed["key_points"])

    return {
        "summary": "\n\n".join(summaries),
        "action_items": action_items,
        "key_points": key_points,
    }


def run_summary(
    meeting_id: str,
    text: str,
    provider,
    db,
    chunk_size: int,
    overlap: int,
    custom_prompt: Optional[str] = None,
) -> None:
    logger.info("run_summary  meeting=%s  chars=%d", meeting_id, len(text))
    start = time.time()
    db.create_process(meeting_id)
    try:
        chunks = chunk_text(text, chunk_size, overlap)
        result = summarize_transcript(text, provider, chunk_size, overlap, custom_prompt)
        elapsed = time.time() - start
        logger.info(
            "run_summary  meeting=%s  ✓  chunks=%d  elapsed=%.1fs",
            meeting_id,
            len(chunks),
            elapsed,
        )
        db.update_process(
            meeting_id,
            status="completed",
            result=json.dumps(result),
            chunk_count=len(chunks),
            processing_time=elapsed,
            end_time=None,
        )
    except Exception as exc:
        elapsed = time.time() - start
        logger.error(
            "run_summary  meeting=%s  ✗  %.1fs  error=%s",
            meeting_id,
            elapsed,
            exc,
        )
        db.update_process(
            meeting_id,
            status="failed",
            error=str(exc),
            processing_time=elapsed,
        )

"""WhisperX diarization service.

A thin FastAPI wrapper around the `whisperx` package providing one endpoint,
``POST /transcribe-diarize``, that the meetily-web backend calls with a full
meeting recording. It returns speaker-labeled segments:

    { "language": "he",
      "segments": [ {"start": 0.0, "end": 1.2, "text": "...",
                     "speaker": "SPEAKER_00"}, ... ] }

Runs air-gapped: models are downloaded once (whisper model + the gated pyannote
diarization model, which needs an HF token the first time) and cached locally;
subsequent runs need no network.

Config via env:
  WHISPERX_MODEL         whisper model size (default: medium)
  WHISPERX_DEVICE        cpu | cuda | mps (default: cpu — see README for Apple)
  WHISPERX_COMPUTE_TYPE  int8 | float16 | float32 (default: int8)
  WHISPERX_LANGUAGE      default language if request omits it (e.g. he)
  HF_TOKEN               HuggingFace token (only needed to first download pyannote)
  WHISPERX_BATCH_SIZE    transcription batch size (default: 8)
"""
from __future__ import annotations

import logging
import os
import tempfile
import time

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("whisperx-service")

app = FastAPI(title="WhisperX Diarization Service")

MODEL = os.getenv("WHISPERX_MODEL", "medium")
DEVICE = os.getenv("WHISPERX_DEVICE", "cpu")
COMPUTE_TYPE = os.getenv("WHISPERX_COMPUTE_TYPE", "int8")
DEFAULT_LANGUAGE = os.getenv("WHISPERX_LANGUAGE", "")
HF_TOKEN = os.getenv("HF_TOKEN", "")
BATCH_SIZE = int(os.getenv("WHISPERX_BATCH_SIZE", "8"))

_state: dict = {}


def _step(name: str) -> float:
    logger.info("  ┌ %s …", name)
    return time.perf_counter()


def _done(t0: float, name: str, detail: str = "") -> None:
    logger.info("  └ %s  done  %.1fs%s", name, time.perf_counter() - t0,
                f"  {detail}" if detail else "")


def _load():
    """Load the whisper + diarization models once (lazy, thread-safe enough for
    single-worker usage)."""
    if _state:
        return _state

    if not HF_TOKEN:
        raise RuntimeError(
            "HF_TOKEN is not set. "
            "The pyannote speaker-diarization model is gated — you must:\n"
            "  1. Create a token at https://hf.co/settings/tokens\n"
            "  2. Accept the model license at https://hf.co/pyannote/speaker-diarization-3.1\n"
            "  3. Accept the segmentation license at https://hf.co/pyannote/segmentation-3.0\n"
            "  4. Re-start with HF_TOKEN=hf_... set in your environment."
        )

    logger.info("Loading models (first request) …")
    logger.info("  model=%s  device=%s  compute=%s  batch=%d",
                MODEL, DEVICE, COMPUTE_TYPE, BATCH_SIZE)

    import whisperx  # imported lazily; heavy dependency

    try:
        from whisperx.diarize import DiarizationPipeline, assign_word_speakers
    except ImportError:  # pragma: no cover
        from whisperx import DiarizationPipeline, assign_word_speakers

    t0 = _step("load whisper model")
    whisper_model = whisperx.load_model(
        MODEL, DEVICE, compute_type=COMPUTE_TYPE,
        language=DEFAULT_LANGUAGE or None,
    )
    _done(t0, "load whisper model", f"model={MODEL}")

    t0 = _step("load diarization pipeline")
    pipeline = DiarizationPipeline(use_auth_token=HF_TOKEN, device=DEVICE)
    if pipeline is None or getattr(pipeline, "model", None) is None:
        _state.clear()
        raise RuntimeError(
            "pyannote pipeline failed to load (returned None). "
            "Check that your HF token is valid and that you have accepted "
            "the model license at https://hf.co/pyannote/speaker-diarization-3.1 "
            "and https://hf.co/pyannote/segmentation-3.0"
        )
    _done(t0, "load diarization pipeline")

    _state["whisperx"] = whisperx
    _state["assign_word_speakers"] = assign_word_speakers
    _state["model"] = whisper_model
    _state["diarize"] = pipeline
    logger.info("Models ready.")
    return _state


@app.get("/health")
def health():
    token_set = bool(HF_TOKEN)
    return {
        "status": "ok",
        "model": MODEL,
        "device": DEVICE,
        "loaded": bool(_state),
        "hf_token_set": token_set,
    }


@app.post("/transcribe-diarize")
async def transcribe_diarize(
    file: UploadFile = File(...),
    language: str = Form(""),
    min_speakers: int = Form(None),
    max_speakers: int = Form(None),
):
    state = _load()
    whisperx = state["whisperx"]

    suffix = os.path.splitext(file.filename or "audio.wav")[1] or ".wav"
    raw = await file.read()
    file_mb = len(raw) / 1024 / 1024
    lang = language or DEFAULT_LANGUAGE or None

    logger.info(
        "transcribe-diarize  file=%s  size=%.1f MB  lang=%s  speakers=%s–%s",
        file.filename,
        file_mb,
        lang or "auto",
        min_speakers if min_speakers is not None else "*",
        max_speakers if max_speakers is not None else "*",
    )

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(raw)
        path = tmp.name

    job_start = time.perf_counter()
    try:
        # ── Step 1: load audio ──────────────────────────────────────────────
        t0 = _step("load audio")
        audio = whisperx.load_audio(path)
        duration_s = len(audio) / 16000  # whisperx resamples to 16 kHz
        _done(t0, "load audio", f"duration={duration_s:.1f}s")

        # ── Step 2: transcribe ──────────────────────────────────────────────
        t0 = _step(f"transcribe (model={MODEL}, batch={BATCH_SIZE})")
        result = state["model"].transcribe(audio, batch_size=BATCH_SIZE, language=lang)
        detected = result.get("language", lang or "?")
        seg_count = len(result.get("segments", []))
        _done(t0, "transcribe", f"lang={detected}  segments={seg_count}")

        # ── Step 3: word-level alignment ────────────────────────────────────
        t0 = _step(f"align (lang={detected})")
        try:
            align_model, metadata = whisperx.load_align_model(
                language_code=detected, device=DEVICE
            )
            result = whisperx.align(
                result["segments"], align_model, metadata, audio, DEVICE,
                return_char_alignments=False,
            )
            _done(t0, "align")
        except Exception as align_err:
            logger.warning(
                "  align skipped (%s) — continuing with unaligned segments", align_err
            )

        # ── Step 4: speaker diarization ─────────────────────────────────────
        t0 = _step("diarize (pyannote)")
        diarize_segments = state["diarize"](
            audio, min_speakers=min_speakers, max_speakers=max_speakers
        )
        _done(t0, "diarize")

        # ── Step 5: assign speakers to segments ─────────────────────────────
        t0 = _step("assign speakers")
        result = state["assign_word_speakers"](diarize_segments, result)
        _done(t0, "assign speakers")

        segments = [
            {
                "start": seg.get("start"),
                "end": seg.get("end"),
                "text": (seg.get("text") or "").strip(),
                "speaker": seg.get("speaker", "SPEAKER_00"),
            }
            for seg in result.get("segments", [])
        ]

        total_s = time.perf_counter() - job_start
        speakers = len({s["speaker"] for s in segments})
        logger.info(
            "transcribe-diarize  ✓  segments=%d  speakers=%d  total=%.1fs",
            len(segments),
            speakers,
            total_s,
        )
        return {"language": detected, "segments": segments}

    except HTTPException:
        raise
    except Exception as exc:
        total_s = time.perf_counter() - job_start
        logger.error("transcribe-diarize  ✗  %.1fs  %s", total_s, exc)
        raise HTTPException(status_code=500, detail=f"Diarization failed: {exc}")
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass

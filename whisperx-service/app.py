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

import os
import tempfile

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

app = FastAPI(title="WhisperX Diarization Service")

MODEL = os.getenv("WHISPERX_MODEL", "medium")
DEVICE = os.getenv("WHISPERX_DEVICE", "cpu")
COMPUTE_TYPE = os.getenv("WHISPERX_COMPUTE_TYPE", "int8")
DEFAULT_LANGUAGE = os.getenv("WHISPERX_LANGUAGE", "")
HF_TOKEN = os.getenv("HF_TOKEN", "")
BATCH_SIZE = int(os.getenv("WHISPERX_BATCH_SIZE", "8"))

# Lazily-initialised heavy objects so the module imports without the models
# present (and so tests can import it). Loaded on first request.
_state: dict = {}


def _load():
    """Load the whisper + diarization models once."""
    if _state:
        return _state

    if not HF_TOKEN:
        raise RuntimeError(
            "HF_TOKEN is not set. "
            "The pyannote speaker-diarization model is gated — you must:\n"
            "  1. Create a token at https://hf.co/settings/tokens\n"
            "  2. Accept the model license at https://hf.co/pyannote/speaker-diarization-3.1\n"
            "  3. Re-start with HF_TOKEN=hf_... set in your environment."
        )

    import whisperx  # imported lazily; heavy dependency

    # DiarizationPipeline / assign_word_speakers moved under whisperx.diarize in
    # the 3.3.x line; fall back to the top-level names for older releases.
    try:
        from whisperx.diarize import DiarizationPipeline, assign_word_speakers
    except ImportError:  # pragma: no cover - depends on installed version
        from whisperx import DiarizationPipeline, assign_word_speakers

    _state["whisperx"] = whisperx
    _state["assign_word_speakers"] = assign_word_speakers
    _state["model"] = whisperx.load_model(
        MODEL, DEVICE, compute_type=COMPUTE_TYPE,
        language=DEFAULT_LANGUAGE or None,
    )
    pipeline = DiarizationPipeline(
        use_auth_token=HF_TOKEN, device=DEVICE,
    )
    if pipeline is None or getattr(pipeline, "model", None) is None:
        # Pipeline.from_pretrained can silently return None when the token is
        # wrong or the model license hasn't been accepted.
        _state.clear()
        raise RuntimeError(
            "pyannote pipeline failed to load (returned None). "
            "Check that your HF token is valid and that you have accepted "
            "the model license at https://hf.co/pyannote/speaker-diarization-3.1"
        )
    _state["diarize"] = pipeline
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
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        path = tmp.name

    try:
        audio = whisperx.load_audio(path)
        lang = language or DEFAULT_LANGUAGE or None
        result = state["model"].transcribe(
            audio, batch_size=BATCH_SIZE, language=lang,
        )
        detected = result.get("language", lang or "")

        # Word-level alignment improves speaker assignment accuracy.
        try:
            align_model, metadata = whisperx.load_align_model(
                language_code=detected, device=DEVICE,
            )
            result = whisperx.align(
                result["segments"], align_model, metadata, audio, DEVICE,
                return_char_alignments=False,
            )
        except Exception:
            # Alignment models may be unavailable for some languages; continue
            # with unaligned segments rather than failing.
            pass

        diarize_segments = state["diarize"](
            audio, min_speakers=min_speakers, max_speakers=max_speakers,
        )
        result = state["assign_word_speakers"](diarize_segments, result)

        segments = [
            {
                "start": seg.get("start"),
                "end": seg.get("end"),
                "text": (seg.get("text") or "").strip(),
                "speaker": seg.get("speaker", "SPEAKER_00"),
            }
            for seg in result.get("segments", [])
        ]
        return {"language": detected, "segments": segments}
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Diarization failed: {exc}")
    finally:
        os.unlink(path)

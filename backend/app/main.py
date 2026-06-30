"""FastAPI application — a faithful web clone of the meetily backend API."""
from contextlib import asynccontextmanager
from functools import lru_cache

import json
import logging
import os
import tempfile
import time

import httpx
from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.db import Database, new_id
from app.diarize import diarize_audio
from app.health import run_startup_checks
from app.llm import build_provider
from app.models import (
    DeleteMeetingRequest,
    GetApiKeyRequest,
    MeetingDetailsResponse,
    MeetingResponse,
    MeetingSummaryUpdate,
    MeetingTitleUpdate,
    SaveModelConfigRequest,
    SaveTranscriptConfigRequest,
    SaveTranscriptRequest,
    SearchRequest,
    Transcript,
    TranscriptRequest,
)
from app.summarizer import run_summary
from app.transcribe import transcribe_audio

logger = logging.getLogger("meetily")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    run_startup_checks(get_settings())
    yield


app = FastAPI(title="Meetily Web Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=3600,
)


# ----------------------------------------------------------------- middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    t0 = time.perf_counter()
    logger.info("→ %s %s", request.method, request.url.path)
    try:
        response = await call_next(request)
    except Exception as exc:
        logger.error("  ✗ %s %s  unhandled: %s", request.method, request.url.path, exc)
        raise
    elapsed_ms = (time.perf_counter() - t0) * 1000
    logger.info(
        "← %s %s  %d  %.0fms",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response


# ---------------------------------------------------------------- singletons
@lru_cache
def _default_db() -> Database:
    return Database(get_settings().db_path)


def get_db() -> Database:
    return _default_db()


def get_provider(db: Database = Depends(get_db)):
    s = get_settings()
    cfg = db.get_model_config()
    provider = (cfg or {}).get("provider", s.llm_provider)
    model = (cfg or {}).get("model", s.llm_model)
    api_key = db.get_api_key(provider) or s.llm_api_key
    return build_provider(
        provider=provider, base_url=s.llm_base_url, model=model, api_key=api_key
    )


@lru_cache
def _whisper_client() -> httpx.Client:
    return httpx.Client()


def get_whisper_client() -> httpx.Client:
    return _whisper_client()


@lru_cache
def _diarize_client() -> httpx.Client:
    return httpx.Client()


def get_diarize_client() -> httpx.Client:
    return _diarize_client()


# ---------------------------------------------------------------------- meetings
@app.get("/get-meetings", response_model=list[MeetingResponse])
def get_meetings(db: Database = Depends(get_db)):
    return [MeetingResponse(id=m["id"], title=m["title"]) for m in db.get_meetings()]


@app.get("/get-meeting/{meeting_id}", response_model=MeetingDetailsResponse)
def get_meeting(meeting_id: str, db: Database = Depends(get_db)):
    meeting = db.get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    transcripts = [
        Transcript(
            id=t["id"],
            text=t["transcript"],
            timestamp=t["timestamp"],
            audio_start_time=t["audio_start_time"],
            audio_end_time=t["audio_end_time"],
            duration=t["duration"],
            speaker=t["speaker"],
        )
        for t in db.get_transcripts(meeting_id)
    ]
    return MeetingDetailsResponse(
        id=meeting["id"],
        title=meeting["title"],
        created_at=meeting["created_at"],
        updated_at=meeting["updated_at"],
        transcripts=transcripts,
    )


@app.post("/save-meeting-title")
def save_meeting_title(req: MeetingTitleUpdate, db: Database = Depends(get_db)):
    if not db.get_meeting(req.meeting_id):
        raise HTTPException(status_code=404, detail="Meeting not found")
    db.update_meeting_title(req.meeting_id, req.title)
    return {"status": "success", "message": "Title updated"}


@app.post("/delete-meeting")
def delete_meeting(req: DeleteMeetingRequest, db: Database = Depends(get_db)):
    db.delete_meeting(req.meeting_id)
    return {"status": "success", "message": "Meeting deleted"}


@app.post("/save-transcript")
def save_transcript(req: SaveTranscriptRequest, db: Database = Depends(get_db)):
    meeting_id = req.meeting_id or new_id()
    db.save_meeting(meeting_id, req.meeting_title, req.folder_path)
    for t in req.transcripts:
        db.save_transcript(
            transcript_id=t.id or new_id(),
            meeting_id=meeting_id,
            transcript=t.text,
            timestamp=t.timestamp,
            audio_start_time=t.audio_start_time,
            audio_end_time=t.audio_end_time,
            duration=t.duration,
        )
    return {"status": "success", "meeting_id": meeting_id}


@app.post("/search-transcripts")
def search_transcripts(req: SearchRequest, db: Database = Depends(get_db)):
    return {"results": db.search_transcripts(req.query)}


# ------------------------------------------------------------------ model config
@app.get("/get-model-config")
def get_model_config(db: Database = Depends(get_db)):
    settings = get_settings()
    cfg = db.get_model_config()
    if cfg:
        return cfg
    return {
        "provider": settings.llm_provider,
        "model": settings.llm_model,
        "whisperModel": "base.en",
    }


@app.post("/save-model-config")
def save_model_config(req: SaveModelConfigRequest, db: Database = Depends(get_db)):
    db.save_model_config(req.provider, req.model, req.whisperModel, req.apiKey)
    return {"status": "success", "message": "Model config saved"}


@app.post("/get-api-key")
def get_api_key(req: GetApiKeyRequest, db: Database = Depends(get_db)):
    return {"apiKey": db.get_api_key(req.provider) or ""}


# -------------------------------------------------------------- transcript config
@app.get("/get-transcript-config")
def get_transcript_config(db: Database = Depends(get_db)):
    cfg = db.get_transcript_config()
    if cfg:
        return cfg
    return {"provider": "whisper", "model": "base.en"}


@app.post("/save-transcript-config")
def save_transcript_config(
    req: SaveTranscriptConfigRequest, db: Database = Depends(get_db)
):
    db.save_transcript_config(req.provider, req.model, req.apiKey)
    return {"status": "success", "message": "Transcript config saved"}


@app.post("/get-transcript-api-key")
def get_transcript_api_key(req: GetApiKeyRequest, db: Database = Depends(get_db)):
    return {"apiKey": db.get_transcript_api_key(req.provider) or ""}


# ----------------------------------------------------------- runtime config/health
@app.get("/get-config")
def get_config():
    s = get_settings()
    return {
        "backend_host": s.backend_host,
        "backend_port": s.backend_port,
        "whisper_server_url": s.whisper_server_url,
        "whisper_language": s.whisper_language,
        "diarize_server_url": s.diarize_server_url,
        "llm_provider": s.llm_provider,
        "llm_base_url": s.llm_base_url,
        "llm_model": s.llm_model,
        "chunk_size": s.chunk_size,
        "chunk_overlap": s.chunk_overlap,
    }


# ------------------------------------------------------------------- summaries
@app.post("/process-transcript")
def process_transcript(
    req: TranscriptRequest,
    background: BackgroundTasks,
    db: Database = Depends(get_db),
    provider=Depends(get_provider),
):
    if not db.get_meeting(req.meeting_id):
        raise HTTPException(status_code=404, detail="Meeting not found")
    s = get_settings()
    text = req.text or db.get_full_transcript_text(req.meeting_id)
    chunk_size = req.chunk_size or s.chunk_size
    overlap = req.overlap if req.overlap is not None else s.chunk_overlap
    db.save_transcript_chunk(
        meeting_id=req.meeting_id,
        transcript_text=text,
        model=req.model,
        model_name=req.model_name,
        chunk_size=chunk_size,
        overlap=overlap,
    )
    logger.info(
        "process_transcript  meeting=%s  chars=%d  chunks≈%d",
        req.meeting_id,
        len(text),
        max(1, len(text) // max(1, chunk_size)),
    )
    background.add_task(
        run_summary, req.meeting_id, text, provider, db, chunk_size, overlap,
        req.custom_prompt,
    )
    return {"status": "processing", "process_id": req.meeting_id}


@app.get("/get-summary/{meeting_id}")
def get_summary(meeting_id: str, db: Database = Depends(get_db)):
    proc = db.get_process(meeting_id)
    if not proc:
        raise HTTPException(status_code=404, detail="No summary process found")
    result = proc.get("result")
    return {
        "meeting_id": meeting_id,
        "status": proc["status"],
        "error": proc.get("error"),
        "result": json.loads(result) if result else None,
    }


@app.post("/save-meeting-summary")
def save_meeting_summary(req: MeetingSummaryUpdate, db: Database = Depends(get_db)):
    db.create_process(req.meeting_id)
    db.update_process(
        req.meeting_id, status="completed", result=json.dumps(req.summary)
    )
    return {"status": "success", "message": "Summary saved"}


# ---------------------------------------------------------------- transcription
@app.post("/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    client: httpx.Client = Depends(get_whisper_client),
):
    audio = await file.read()
    settings = get_settings()
    whisper_url = settings.whisper_server_url
    try:
        text = transcribe_audio(
            audio,
            file.filename or "audio.wav",
            file.content_type or "audio/wav",
            whisper_url,
            client,
            language=settings.whisper_language,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Whisper server unreachable at {whisper_url}: {exc}",
        )
    return {"text": text}


# ----------------------------------------------------------------- diarization
def _run_diarize_job(
    meeting_id: str,
    tmp_path: str,
    filename: str,
    content_type: str,
    language: str,
    min_speakers: int | None,
    max_speakers: int | None,
    diarize_url: str,
    db: Database,
    client: httpx.Client | None = None,
) -> None:
    """Runs in a background thread. Calls WhisperX, persists results to DB."""
    if client is None:
        client = httpx.Client()
    try:
        logger.info("diarize_job  meeting=%s  step=sending", meeting_id)
        db.update_diarize_job(meeting_id, status="processing", step="sending")

        result = diarize_audio(
            audio_path=tmp_path,
            filename=filename,
            content_type=content_type,
            diarize_url=diarize_url,
            client=client,
            language=language,
            min_speakers=min_speakers,
            max_speakers=max_speakers,
        )

        seg_count = len(result["segments"])
        logger.info(
            "diarize_job  meeting=%s  step=saving  segments=%d", meeting_id, seg_count
        )
        db.update_diarize_job(meeting_id, status="processing", step="saving")
        db.replace_transcripts(meeting_id, result["segments"])

        db.update_diarize_job(
            meeting_id, status="completed", step="completed", segments_count=seg_count
        )
        logger.info(
            "diarize_job  meeting=%s  ✓  segments=%d  lang=%s",
            meeting_id,
            seg_count,
            result.get("language", "?"),
        )
    except Exception as exc:
        logger.error("diarize_job  meeting=%s  ✗  %s", meeting_id, exc)
        db.update_diarize_job(meeting_id, status="failed", step="failed", error=str(exc))
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


@app.post("/transcribe-diarized")
async def transcribe_diarized(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    meeting_id: str = Form(None),
    meeting_title: str = Form("Untitled meeting"),
    min_speakers: int = Form(None),
    max_speakers: int = Form(None),
    db: Database = Depends(get_db),
    client: httpx.Client = Depends(get_diarize_client),
):
    """Accept the full recording and start a background diarization job.

    Returns immediately with {meeting_id, status: "processing"} so the
    frontend can start polling /diarize-status/{meeting_id}. The audio file
    is streamed to a temp file (no large in-memory buffer) and cleaned up
    after the job finishes.
    """
    settings = get_settings()
    filename = file.filename or "audio.wav"
    content_type = file.content_type or "audio/wav"
    suffix = os.path.splitext(filename)[1] or ".wav"

    # Stream the upload to disk in 1 MB chunks — avoids holding the entire
    # file (potentially hundreds of MB) in Python memory.
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    total_bytes = 0
    try:
        while True:
            chunk = await file.read(1 * 1024 * 1024)
            if not chunk:
                break
            tmp.write(chunk)
            total_bytes += len(chunk)
        tmp.flush()
        tmp_path = tmp.name
    finally:
        tmp.close()

    mb = total_bytes / 1024 / 1024
    logger.info(
        "transcribe_diarized  file=%s  size=%.1f MB  meeting=%s",
        filename,
        mb,
        meeting_id or "(new)",
    )

    mid = meeting_id or new_id()
    if not db.get_meeting(mid):
        db.save_meeting(mid, meeting_title)
    db.create_diarize_job(mid)

    background_tasks.add_task(
        _run_diarize_job,
        mid,
        tmp_path,
        filename,
        content_type,
        settings.whisper_language,
        min_speakers,
        max_speakers,
        settings.diarize_server_url,
        db,
        client,
    )

    logger.info("transcribe_diarized  meeting=%s  job queued", mid)
    return {"meeting_id": mid, "status": "processing"}


@app.get("/diarize-status/{meeting_id}")
def diarize_status(meeting_id: str, db: Database = Depends(get_db)):
    """Poll the status of a background diarization job."""
    job = db.get_diarize_job(meeting_id)
    if not job:
        raise HTTPException(status_code=404, detail="No diarization job found")
    return {
        "meeting_id": meeting_id,
        "status": job["status"],
        "step": job.get("step"),
        "error": job.get("error"),
        "segments_count": job.get("segments_count"),
        "created_at": job["created_at"],
        "updated_at": job["updated_at"],
    }


@app.get("/health")
def health():
    s = get_settings()
    checks = run_startup_checks(s)
    services = {
        name: {"status": r["status"], "url": r.get("url", "")}
        for name, r in checks.items()
    }
    return {
        "status": "ok",
        "whisper_server_url": s.whisper_server_url,
        "llm_base_url": s.llm_base_url,
        "services": services,
    }

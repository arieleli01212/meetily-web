"""FastAPI application — a faithful web clone of the meetily backend API."""
from functools import lru_cache

import json

import httpx
from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    HTTPException,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import Database, new_id
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

app = FastAPI(title="Meetily Web Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=3600,
)


@lru_cache
def _default_db() -> Database:
    return Database(get_settings().db_path)


def get_db() -> Database:
    """Dependency returning the database; overridable in tests."""
    return _default_db()


def get_provider(db: Database = Depends(get_db)):
    """Build the configured LLM provider, preferring saved runtime settings
    over env defaults. Overridable in tests."""
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
    """HTTP client used to reach the whisper server; overridable in tests."""
    return _whisper_client()


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
    # Fall back to env defaults so an air-gapped install works before any
    # config has been saved through the UI.
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
def save_transcript_config(req: SaveTranscriptConfigRequest,
                           db: Database = Depends(get_db)):
    db.save_transcript_config(req.provider, req.model, req.apiKey)
    return {"status": "success", "message": "Transcript config saved"}


@app.post("/get-transcript-api-key")
def get_transcript_api_key(req: GetApiKeyRequest, db: Database = Depends(get_db)):
    return {"apiKey": db.get_transcript_api_key(req.provider) or ""}


# ----------------------------------------------------------- runtime config/health
@app.get("/get-config")
def get_config():
    """Expose non-secret connection parameters for the settings UI."""
    s = get_settings()
    return {
        "backend_host": s.backend_host,
        "backend_port": s.backend_port,
        "whisper_server_url": s.whisper_server_url,
        "whisper_language": s.whisper_language,
        "llm_provider": s.llm_provider,
        "llm_base_url": s.llm_base_url,
        "llm_model": s.llm_model,
        "chunk_size": s.chunk_size,
        "chunk_overlap": s.chunk_overlap,
    }


# ------------------------------------------------------------------- summaries
@app.post("/process-transcript")
def process_transcript(req: TranscriptRequest, background: BackgroundTasks,
                       db: Database = Depends(get_db),
                       provider=Depends(get_provider)):
    if not db.get_meeting(req.meeting_id):
        raise HTTPException(status_code=404, detail="Meeting not found")
    s = get_settings()
    text = req.text or db.get_full_transcript_text(req.meeting_id)
    chunk_size = req.chunk_size or s.chunk_size
    overlap = req.overlap if req.overlap is not None else s.chunk_overlap
    db.save_transcript_chunk(
        meeting_id=req.meeting_id, transcript_text=text, model=req.model,
        model_name=req.model_name, chunk_size=chunk_size, overlap=overlap,
    )
    background.add_task(run_summary, req.meeting_id, text, provider, db,
                        chunk_size, overlap, req.custom_prompt)
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
    db.update_process(req.meeting_id, status="completed",
                      result=json.dumps(req.summary))
    return {"status": "success", "message": "Summary saved"}


# ---------------------------------------------------------------- transcription
@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...),
                     client: httpx.Client = Depends(get_whisper_client)):
    audio = await file.read()
    settings = get_settings()
    whisper_url = settings.whisper_server_url
    try:
        text = transcribe_audio(
            audio, file.filename or "audio.wav",
            file.content_type or "audio/wav", whisper_url, client,
            language=settings.whisper_language,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Whisper server unreachable at {whisper_url}: {exc}",
        )
    return {"text": text}


@app.get("/health")
def health():
    s = get_settings()
    return {
        "status": "ok",
        "whisper_server_url": s.whisper_server_url,
        "llm_base_url": s.llm_base_url,
    }

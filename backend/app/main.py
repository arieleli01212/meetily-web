"""FastAPI application — a faithful web clone of the meetily backend API."""
from functools import lru_cache

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import Database, new_id
from app.models import (
    DeleteMeetingRequest,
    GetApiKeyRequest,
    MeetingDetailsResponse,
    MeetingResponse,
    MeetingTitleUpdate,
    SaveModelConfigRequest,
    SaveTranscriptConfigRequest,
    SaveTranscriptRequest,
    SearchRequest,
    Transcript,
)

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
        "llm_provider": s.llm_provider,
        "llm_base_url": s.llm_base_url,
        "llm_model": s.llm_model,
        "chunk_size": s.chunk_size,
        "chunk_overlap": s.chunk_overlap,
    }


@app.get("/health")
def health():
    s = get_settings()
    return {
        "status": "ok",
        "whisper_server_url": s.whisper_server_url,
        "llm_base_url": s.llm_base_url,
    }

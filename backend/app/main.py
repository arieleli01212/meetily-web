"""FastAPI application — a faithful web clone of the meetily backend API."""
from functools import lru_cache

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import Database, new_id
from app.models import (
    DeleteMeetingRequest,
    MeetingDetailsResponse,
    MeetingResponse,
    MeetingTitleUpdate,
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

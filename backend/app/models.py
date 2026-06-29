"""Pydantic request/response models matching the meetily API contract."""
from typing import Any, Optional

from pydantic import BaseModel


class Transcript(BaseModel):
    id: str
    text: str
    timestamp: str
    audio_start_time: Optional[float] = None
    audio_end_time: Optional[float] = None
    duration: Optional[float] = None


class MeetingResponse(BaseModel):
    id: str
    title: str


class MeetingDetailsResponse(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    transcripts: list[Transcript]


class MeetingTitleUpdate(BaseModel):
    meeting_id: str
    title: str


class DeleteMeetingRequest(BaseModel):
    meeting_id: str


class SaveTranscriptRequest(BaseModel):
    meeting_title: str
    transcripts: list[Transcript]
    folder_path: Optional[str] = None
    meeting_id: Optional[str] = None


class SaveModelConfigRequest(BaseModel):
    provider: str
    model: str
    whisperModel: str
    apiKey: Optional[str] = None


class SaveTranscriptConfigRequest(BaseModel):
    provider: str
    model: str
    apiKey: Optional[str] = None


class TranscriptRequest(BaseModel):
    text: Optional[str] = None
    model: str
    model_name: str
    meeting_id: str
    chunk_size: Optional[int] = None
    overlap: Optional[int] = None
    custom_prompt: Optional[str] = None


class GetApiKeyRequest(BaseModel):
    provider: str


class MeetingSummaryUpdate(BaseModel):
    meeting_id: str
    summary: dict[str, Any]


class SearchRequest(BaseModel):
    query: str

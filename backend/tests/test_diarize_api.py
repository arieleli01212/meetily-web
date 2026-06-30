"""Tests for the diarization job endpoints."""
from unittest.mock import patch

import pytest

from app.db import Database
from app.main import app, get_db


# ── helpers -----------------------------------------------------------------

def _mock_diarize(segments=None, language="he"):
    """Return a mock for app.main.diarize_audio."""
    if segments is None:
        segments = [
            {"start": 0.0, "end": 1.2, "text": "שלום", "speaker": "SPEAKER_00"},
            {"start": 1.2, "end": 2.5, "text": "מה נשמע", "speaker": "SPEAKER_01"},
        ]
    return {"language": language, "segments": segments}


# ── /transcribe-diarized (POST) ---------------------------------------------

def test_diarize_returns_job_immediately(client):
    with patch("app.main.diarize_audio", return_value=_mock_diarize()):
        resp = client.post(
            "/transcribe-diarized",
            data={"meeting_title": "Hebrew chat"},
            files={"file": ("full.wav", b"RIFFaudio", "audio/wav")},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert "meeting_id" in body
    assert body["status"] == "processing"


def test_diarize_creates_meeting_and_stores_speakers(client):
    with patch("app.main.diarize_audio", return_value=_mock_diarize()):
        resp = client.post(
            "/transcribe-diarized",
            data={"meeting_title": "Hebrew chat"},
            files={"file": ("full.wav", b"RIFFaudio", "audio/wav")},
        )
    assert resp.status_code == 200
    mid = resp.json()["meeting_id"]

    # BackgroundTasks run synchronously in TestClient, so the transcript is
    # already stored by the time we query.
    detail = client.get(f"/get-meeting/{mid}").json()
    assert len(detail["transcripts"]) == 2
    assert detail["transcripts"][0]["speaker"] == "SPEAKER_00"
    assert detail["transcripts"][1]["text"] == "מה נשמע"


def test_diarize_existing_meeting_replaces_transcript(client):
    mid = client.post(
        "/save-transcript",
        json={
            "meeting_title": "M",
            "transcripts": [
                {"id": "x", "text": "live text", "timestamp": "2026-01-01T00:00:00"}
            ],
        },
    ).json()["meeting_id"]

    segments = [{"start": 0, "end": 1, "text": "diarized", "speaker": "SPEAKER_00"}]
    with patch("app.main.diarize_audio", return_value={"language": "", "segments": segments}):
        resp = client.post(
            "/transcribe-diarized",
            data={"meeting_id": mid},
            files={"file": ("full.wav", b"data", "audio/wav")},
        )
    assert resp.status_code == 200
    detail = client.get(f"/get-meeting/{mid}").json()
    assert len(detail["transcripts"]) == 1
    assert detail["transcripts"][0]["text"] == "diarized"


def test_diarize_service_error_stored_in_job(client):
    import httpx
    with patch("app.main.diarize_audio", side_effect=httpx.ConnectError("refused")):
        resp = client.post(
            "/transcribe-diarized",
            data={"meeting_title": "M"},
            files={"file": ("full.wav", b"data", "audio/wav")},
        )
    assert resp.status_code == 200
    mid = resp.json()["meeting_id"]

    # After the background task fails, the job status should reflect that.
    status_resp = client.get(f"/diarize-status/{mid}").json()
    assert status_resp["status"] == "failed"
    assert status_resp["error"] is not None


# ── /diarize-status/{meeting_id} (GET) -------------------------------------

def test_diarize_status_completed(client):
    with patch("app.main.diarize_audio", return_value=_mock_diarize()):
        mid = client.post(
            "/transcribe-diarized",
            data={"meeting_title": "M"},
            files={"file": ("full.wav", b"data", "audio/wav")},
        ).json()["meeting_id"]

    j = client.get(f"/diarize-status/{mid}").json()
    assert j["status"] == "completed"
    assert j["segments_count"] == 2
    assert j["step"] == "completed"


def test_diarize_status_missing_job(client):
    resp = client.get("/diarize-status/nonexistent-id")
    assert resp.status_code == 404

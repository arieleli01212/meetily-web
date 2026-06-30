"""Tests for the /transcribe-diarized endpoint (mocked WhisperX service)."""
import httpx

from app.main import app, get_diarize_client


def _override(handler):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    app.dependency_overrides[get_diarize_client] = lambda: client


def test_diarize_creates_meeting_and_stores_speakers(client):
    captured = {}

    def handler(request):
        captured["path"] = request.url.path
        return httpx.Response(200, json={
            "language": "he",
            "segments": [
                {"start": 0.0, "end": 1.2, "text": "שלום", "speaker": "SPEAKER_00"},
                {"start": 1.2, "end": 2.5, "text": "מה נשמע", "speaker": "SPEAKER_01"},
            ],
        })

    _override(handler)
    try:
        resp = client.post(
            "/transcribe-diarized",
            data={"meeting_title": "Hebrew chat"},
            files={"file": ("full.wav", b"RIFFaudio", "audio/wav")},
        )
        assert resp.status_code == 200
        body = resp.json()
        mid = body["meeting_id"]
        assert captured["path"].endswith("/transcribe-diarize")
        # Stored and returned with speaker labels.
        detail = client.get(f"/get-meeting/{mid}").json()
        assert len(detail["transcripts"]) == 2
        assert detail["transcripts"][0]["speaker"] == "SPEAKER_00"
        assert detail["transcripts"][1]["text"] == "מה נשמע"
    finally:
        app.dependency_overrides.pop(get_diarize_client, None)


def test_diarize_existing_meeting_replaces_transcript(client):
    mid = client.post("/save-transcript", json={
        "meeting_title": "M", "transcripts": [
            {"id": "x", "text": "live text", "timestamp": "2026-01-01T00:00:00"}],
    }).json()["meeting_id"]

    def handler(request):
        return httpx.Response(200, json={"segments": [
            {"start": 0, "end": 1, "text": "diarized", "speaker": "SPEAKER_00"}]})

    _override(handler)
    try:
        resp = client.post(
            "/transcribe-diarized",
            data={"meeting_id": mid},
            files={"file": ("full.wav", b"data", "audio/wav")},
        )
        assert resp.status_code == 200
        detail = client.get(f"/get-meeting/{mid}").json()
        assert len(detail["transcripts"]) == 1
        assert detail["transcripts"][0]["text"] == "diarized"
    finally:
        app.dependency_overrides.pop(get_diarize_client, None)


def test_diarize_service_unreachable(client):
    def handler(request):
        raise httpx.ConnectError("refused")

    _override(handler)
    try:
        resp = client.post(
            "/transcribe-diarized",
            data={"meeting_title": "M"},
            files={"file": ("full.wav", b"data", "audio/wav")},
        )
        assert resp.status_code == 502
    finally:
        app.dependency_overrides.pop(get_diarize_client, None)

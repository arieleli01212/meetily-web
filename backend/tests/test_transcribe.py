"""Tests for the /transcribe proxy to a whisper.cpp server."""
import httpx

from app.main import app, get_whisper_client
from app.transcribe import transcribe_audio


def test_transcribe_audio_forwards_language():
    captured = {}

    def handler(request):
        captured["body"] = request.content.decode("latin-1")
        return httpx.Response(200, json={"text": "שלום"})

    c = httpx.Client(transport=httpx.MockTransport(handler))
    text = transcribe_audio(b"RIFFdata", "chunk.wav", "audio/wav",
                            "http://whisper:8178", c, language="he")
    assert text == "שלום"
    # The language must be present in the multipart form forwarded to whisper.
    assert 'name="language"' in captured["body"]
    assert "he" in captured["body"]


def _override_client(handler):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    app.dependency_overrides[get_whisper_client] = lambda: client


def test_transcribe_forwards_to_whisper(client):
    captured = {}

    def handler(request):
        captured["path"] = request.url.path
        captured["has_body"] = bool(request.content)
        captured["body"] = request.content
        return httpx.Response(200, json={"text": "hello from whisper"})

    _override_client(handler)
    try:
        resp = client.post(
            "/transcribe",
            files={"file": ("chunk.wav", b"RIFFfakeaudio", "audio/wav")},
        )
        assert resp.status_code == 200
        assert resp.json()["text"] == "hello from whisper"
        assert captured["path"].endswith("/inference")
        assert captured["has_body"]
    finally:
        app.dependency_overrides.pop(get_whisper_client, None)


def test_transcribe_handles_whisper_error(client):
    def handler(request):
        raise httpx.ConnectError("connection refused")

    _override_client(handler)
    try:
        resp = client.post(
            "/transcribe",
            files={"file": ("chunk.wav", b"data", "audio/wav")},
        )
        assert resp.status_code == 502
        assert "whisper" in resp.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(get_whisper_client, None)

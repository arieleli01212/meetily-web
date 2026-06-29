"""Tests for the /transcribe proxy to a whisper.cpp server."""
import httpx

from app.main import app, get_whisper_client


def _override_client(handler):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    app.dependency_overrides[get_whisper_client] = lambda: client


def test_transcribe_forwards_to_whisper(client):
    captured = {}

    def handler(request):
        captured["path"] = request.url.path
        captured["has_body"] = bool(request.content)
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

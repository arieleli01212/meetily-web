"""Light tests that the service imports and serves health without ML models.

Real transcription/diarization requires the whisperx models and is the
operator's responsibility (large downloads, HF token). These tests only verify
the service wiring loads cleanly.
"""
from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


def test_health_ok_without_models_loaded():
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["loaded"] is False
    assert "model" in body

"""Tests for the summarization endpoints (process-transcript / get-summary)."""
import json
import uuid

from app.main import app, get_provider


class FakeProvider:
    def complete(self, prompt, system=None):
        return json.dumps({
            "summary": "A concise summary.",
            "action_items": ["Follow up with team"],
            "key_points": ["Decision made"],
        })


def _make_meeting(client):
    return client.post("/save-transcript", json={
        "meeting_title": "Sync",
        "transcripts": [{"id": str(uuid.uuid4()),
                         "text": "we talked about the plan",
                         "timestamp": "2026-01-01T00:00:00"}],
    }).json()["meeting_id"]


def test_process_and_get_summary(client):
    app.dependency_overrides[get_provider] = lambda: FakeProvider()
    try:
        mid = _make_meeting(client)
        resp = client.post("/process-transcript", json={
            "meeting_id": mid, "model": "ollama", "model_name": "llama3",
        })
        assert resp.status_code == 200
        assert resp.json()["process_id"] == mid
        # Background task runs after the response in TestClient.
        summary = client.get(f"/get-summary/{mid}").json()
        assert summary["status"] == "completed"
        assert summary["result"]["summary"] == "A concise summary."
        assert summary["result"]["action_items"] == ["Follow up with team"]
    finally:
        app.dependency_overrides.pop(get_provider, None)


def test_process_unknown_meeting(client):
    app.dependency_overrides[get_provider] = lambda: FakeProvider()
    try:
        resp = client.post("/process-transcript", json={
            "meeting_id": "nope", "model": "ollama", "model_name": "llama3",
        })
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.pop(get_provider, None)


def test_save_meeting_summary(client):
    mid = _make_meeting(client)
    resp = client.post("/save-meeting-summary", json={
        "meeting_id": mid,
        "summary": {"summary": "manual", "action_items": [], "key_points": []},
    })
    assert resp.status_code == 200
    got = client.get(f"/get-summary/{mid}").json()
    assert got["result"]["summary"] == "manual"

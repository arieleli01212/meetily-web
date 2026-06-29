"""Tests for meeting CRUD and search endpoints."""


import uuid


def _save_meeting(client, title="Standup", text="hello team"):
    resp = client.post("/save-transcript", json={
        "meeting_title": title,
        "transcripts": [
            {"id": str(uuid.uuid4()), "text": text,
             "timestamp": "2026-01-01T00:00:00"}
        ],
    })
    assert resp.status_code == 200
    return resp.json()["meeting_id"]


def test_save_transcript_creates_meeting(client):
    mid = _save_meeting(client)
    assert mid
    meetings = client.get("/get-meetings").json()
    assert any(m["id"] == mid for m in meetings)


def test_get_meeting_details(client):
    mid = _save_meeting(client, title="Planning", text="discuss roadmap")
    resp = client.get(f"/get-meeting/{mid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Planning"
    assert data["transcripts"][0]["text"] == "discuss roadmap"


def test_get_meeting_not_found(client):
    assert client.get("/get-meeting/nope").status_code == 404


def test_save_meeting_title(client):
    mid = _save_meeting(client)
    resp = client.post("/save-meeting-title",
                       json={"meeting_id": mid, "title": "Renamed"})
    assert resp.status_code == 200
    assert client.get(f"/get-meeting/{mid}").json()["title"] == "Renamed"


def test_delete_meeting(client):
    mid = _save_meeting(client)
    resp = client.post("/delete-meeting", json={"meeting_id": mid})
    assert resp.status_code == 200
    assert client.get(f"/get-meeting/{mid}").status_code == 404


def test_search_transcripts(client):
    _save_meeting(client, title="Budget", text="we reviewed the budget figures")
    _save_meeting(client, title="Retro", text="sprint went smoothly")
    results = client.post("/search-transcripts", json={"query": "budget"}).json()
    assert len(results["results"]) == 1
    assert results["results"][0]["title"] == "Budget"

"""Tests for the SQLite database layer."""
import pytest

from app.db import Database


@pytest.fixture
def db(tmp_path):
    return Database(str(tmp_path / "test.db"))


def test_save_and_get_meeting(db):
    db.save_meeting("m1", "Standup")
    meeting = db.get_meeting("m1")
    assert meeting is not None
    assert meeting["id"] == "m1"
    assert meeting["title"] == "Standup"
    assert meeting["created_at"]
    assert meeting["updated_at"]


def test_get_meetings_lists_all(db):
    db.save_meeting("m1", "A")
    db.save_meeting("m2", "B")
    meetings = db.get_meetings()
    ids = {m["id"] for m in meetings}
    assert ids == {"m1", "m2"}


def test_update_meeting_title(db):
    db.save_meeting("m1", "Old")
    db.update_meeting_title("m1", "New")
    assert db.get_meeting("m1")["title"] == "New"


def test_delete_meeting_cascades(db):
    db.save_meeting("m1", "A")
    db.save_transcript("t1", "m1", "hello world", "2026-01-01T00:00:00")
    db.delete_meeting("m1")
    assert db.get_meeting("m1") is None
    assert db.get_transcripts("m1") == []


def test_save_and_get_transcripts(db):
    db.save_meeting("m1", "A")
    db.save_transcript("t1", "m1", "line one", "2026-01-01T00:00:01",
                       audio_start_time=0.0, audio_end_time=1.5, duration=1.5)
    rows = db.get_transcripts("m1")
    assert len(rows) == 1
    assert rows[0]["transcript"] == "line one"
    assert rows[0]["duration"] == 1.5


def test_process_lifecycle(db):
    db.save_meeting("m1", "A")
    db.create_process("m1")
    proc = db.get_process("m1")
    assert proc["status"] == "processing"
    db.update_process("m1", status="completed", result='{"summary":"ok"}')
    proc = db.get_process("m1")
    assert proc["status"] == "completed"
    assert proc["result"] == '{"summary":"ok"}'


def test_model_config_roundtrip(db):
    db.save_model_config(provider="ollama", model="llama3", whisper_model="base.en",
                         api_key="secret", api_key_field="ollamaApiKey")
    cfg = db.get_model_config()
    assert cfg["provider"] == "ollama"
    assert cfg["model"] == "llama3"
    assert cfg["whisperModel"] == "base.en"
    # API key fetched separately
    assert db.get_api_key("ollama") == "secret"


def test_transcript_config_roundtrip(db):
    db.save_transcript_config(provider="whisper", model="base.en",
                              api_key="k", api_key_field="whisperApiKey")
    cfg = db.get_transcript_config()
    assert cfg["provider"] == "whisper"
    assert cfg["model"] == "base.en"
    assert db.get_transcript_api_key("whisper") == "k"


def test_search_transcripts(db):
    db.save_meeting("m1", "Planning")
    db.save_meeting("m2", "Retro")
    db.save_transcript("t1", "m1", "we discussed the budget", "2026-01-01T00:00:00")
    db.save_transcript("t2", "m2", "the sprint went well", "2026-01-02T00:00:00")
    results = db.search_transcripts("budget")
    assert len(results) == 1
    assert results[0]["meeting_id"] == "m1"

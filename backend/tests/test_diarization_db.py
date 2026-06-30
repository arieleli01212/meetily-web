"""Tests for speaker-labeled transcript storage."""
import sqlite3

import pytest

from app.db import Database


@pytest.fixture
def db(tmp_path):
    return Database(str(tmp_path / "d.db"))


def test_transcripts_has_speaker_column(db):
    rows = db.get_transcripts  # ensure attribute exists
    assert callable(rows)
    with db._connect() as conn:
        cols = [r[1] for r in conn.execute(
            "PRAGMA table_info(transcripts)").fetchall()]
    assert "speaker" in cols


def test_save_transcript_with_speaker(db):
    db.save_meeting("m1", "A")
    db.save_transcript("t1", "m1", "shalom", "2026-01-01T00:00:00",
                       speaker="SPEAKER_00")
    rows = db.get_transcripts("m1")
    assert rows[0]["speaker"] == "SPEAKER_00"


def test_replace_transcripts(db):
    db.save_meeting("m1", "A")
    db.save_transcript("t1", "m1", "old line", "2026-01-01T00:00:00")
    segments = [
        {"start": 0.0, "end": 1.0, "text": "hi", "speaker": "SPEAKER_00"},
        {"start": 1.0, "end": 2.0, "text": "hello", "speaker": "SPEAKER_01"},
    ]
    db.replace_transcripts("m1", segments)
    rows = db.get_transcripts("m1")
    assert len(rows) == 2
    assert [r["transcript"] for r in rows] == ["hi", "hello"]
    assert [r["speaker"] for r in rows] == ["SPEAKER_00", "SPEAKER_01"]
    assert rows[0]["audio_start_time"] == 0.0


def test_migration_adds_speaker_to_legacy_db(tmp_path):
    # Simulate a pre-diarization DB without the speaker column.
    path = str(tmp_path / "legacy.db")
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE meetings (id TEXT PRIMARY KEY, title TEXT NOT NULL,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL, folder_path TEXT);
        CREATE TABLE transcripts (id TEXT PRIMARY KEY, meeting_id TEXT NOT NULL,
            transcript TEXT NOT NULL, timestamp TEXT NOT NULL, summary TEXT,
            action_items TEXT, key_points TEXT, audio_start_time REAL,
            audio_end_time REAL, duration REAL);
        """
    )
    conn.commit()
    conn.close()

    db = Database(path)  # opening should migrate
    with db._connect() as c:
        cols = [r[1] for r in c.execute("PRAGMA table_info(transcripts)").fetchall()]
    assert "speaker" in cols

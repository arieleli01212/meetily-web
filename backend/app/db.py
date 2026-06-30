"""SQLite persistence layer.

Schema mirrors the legacy meetily FastAPI backend so the web clone is a
faithful drop-in: meetings, transcripts, summary_processes,
transcript_chunks, settings, transcript_settings.
"""
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# Column name per provider for the model (summary) settings table.
MODEL_API_KEY_FIELDS = {
    "groq": "groqApiKey",
    "openai": "openaiApiKey",
    "anthropic": "anthropicApiKey",
    "ollama": "ollamaApiKey",
}

# Column name per provider for the transcription settings table.
TRANSCRIPT_API_KEY_FIELDS = {
    "whisper": "whisperApiKey",
    "deepgram": "deepgramApiKey",
    "elevenlabs": "elevenLabsApiKey",
    "groq": "groqApiKey",
    "openai": "openaiApiKey",
}


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        parent = os.path.dirname(db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS meetings (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    folder_path TEXT
                );
                CREATE TABLE IF NOT EXISTS transcripts (
                    id TEXT PRIMARY KEY,
                    meeting_id TEXT NOT NULL,
                    transcript TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    summary TEXT,
                    action_items TEXT,
                    key_points TEXT,
                    audio_start_time REAL,
                    audio_end_time REAL,
                    duration REAL,
                    speaker TEXT,
                    FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS summary_processes (
                    meeting_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    error TEXT,
                    result TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    chunk_count INTEGER,
                    processing_time REAL,
                    metadata TEXT,
                    FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS transcript_chunks (
                    meeting_id TEXT PRIMARY KEY,
                    meeting_name TEXT,
                    transcript_text TEXT NOT NULL,
                    model TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    chunk_size INTEGER,
                    overlap INTEGER,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS settings (
                    id TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    whisperModel TEXT NOT NULL,
                    groqApiKey TEXT,
                    openaiApiKey TEXT,
                    anthropicApiKey TEXT,
                    ollamaApiKey TEXT
                );
                CREATE TABLE IF NOT EXISTS transcript_settings (
                    id TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    whisperApiKey TEXT,
                    deepgramApiKey TEXT,
                    elevenLabsApiKey TEXT,
                    groqApiKey TEXT,
                    openaiApiKey TEXT
                );
                CREATE TABLE IF NOT EXISTS diarize_jobs (
                    meeting_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    step TEXT,
                    error TEXT,
                    segments_count INTEGER,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
        self._migrate()

    def _migrate(self) -> None:
        """Idempotent migrations for DBs created before later columns existed."""
        with self._connect() as conn:
            cols = [r[1] for r in conn.execute(
                "PRAGMA table_info(transcripts)").fetchall()]
            if "speaker" not in cols:
                conn.execute("ALTER TABLE transcripts ADD COLUMN speaker TEXT")

    # ------------------------------------------------------------------ meetings
    def save_meeting(self, meeting_id: str, title: str,
                     folder_path: Optional[str] = None) -> None:
        now = _now()
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO meetings (id, title, created_at, updated_at, folder_path)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET title=excluded.title,
                       updated_at=excluded.updated_at,
                       folder_path=excluded.folder_path""",
                (meeting_id, title, now, now, folder_path),
            )

    def get_meeting(self, meeting_id: str) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM meetings WHERE id = ?", (meeting_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_meetings(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM meetings ORDER BY created_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    def update_meeting_title(self, meeting_id: str, title: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE meetings SET title = ?, updated_at = ? WHERE id = ?",
                (title, _now(), meeting_id),
            )

    def delete_meeting(self, meeting_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM meetings WHERE id = ?", (meeting_id,))

    # --------------------------------------------------------------- transcripts
    def save_transcript(self, transcript_id: str, meeting_id: str, transcript: str,
                        timestamp: str, summary: Optional[str] = None,
                        action_items: Optional[str] = None,
                        key_points: Optional[str] = None,
                        audio_start_time: Optional[float] = None,
                        audio_end_time: Optional[float] = None,
                        duration: Optional[float] = None,
                        speaker: Optional[str] = None) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO transcripts (id, meeting_id, transcript, timestamp,
                       summary, action_items, key_points, audio_start_time,
                       audio_end_time, duration, speaker)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (transcript_id, meeting_id, transcript, timestamp, summary,
                 action_items, key_points, audio_start_time, audio_end_time,
                 duration, speaker),
            )

    def replace_transcripts(self, meeting_id: str, segments: list[dict]) -> None:
        """Replace all transcript rows for a meeting with diarized segments.

        Each segment: {start, end, text, speaker}. Used after post-meeting
        diarization produces speaker-labeled output for the full recording.
        """
        with self._connect() as conn:
            conn.execute("DELETE FROM transcripts WHERE meeting_id = ?",
                         (meeting_id,))
            for i, seg in enumerate(segments):
                start = seg.get("start")
                end = seg.get("end")
                duration = (end - start) if (start is not None and end is not None) \
                    else None
                conn.execute(
                    """INSERT INTO transcripts (id, meeting_id, transcript,
                           timestamp, audio_start_time, audio_end_time, duration,
                           speaker)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (f"{meeting_id}-seg-{i}", meeting_id,
                     (seg.get("text") or "").strip(), _now(), start, end,
                     duration, seg.get("speaker")),
                )

    def get_transcripts(self, meeting_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM transcripts WHERE meeting_id = ? ORDER BY timestamp",
                (meeting_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_full_transcript_text(self, meeting_id: str) -> str:
        return "\n".join(r["transcript"] for r in self.get_transcripts(meeting_id))

    def search_transcripts(self, query: str) -> list[dict]:
        like = f"%{query}%"
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT t.meeting_id, t.transcript, t.timestamp, m.title
                   FROM transcripts t JOIN meetings m ON m.id = t.meeting_id
                   WHERE t.transcript LIKE ? ORDER BY t.timestamp DESC""",
                (like,),
            ).fetchall()
            return [dict(r) for r in rows]

    # --------------------------------------------------------- summary processes
    def create_process(self, meeting_id: str) -> None:
        now = _now()
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO summary_processes (meeting_id, status, created_at,
                       updated_at, start_time)
                   VALUES (?, 'processing', ?, ?, ?)
                   ON CONFLICT(meeting_id) DO UPDATE SET status='processing',
                       updated_at=excluded.updated_at, start_time=excluded.start_time,
                       error=NULL, result=NULL""",
                (meeting_id, now, now, now),
            )

    def update_process(self, meeting_id: str, **fields: Any) -> None:
        if not fields:
            return
        fields["updated_at"] = _now()
        columns = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [meeting_id]
        with self._connect() as conn:
            conn.execute(
                f"UPDATE summary_processes SET {columns} WHERE meeting_id = ?",
                values,
            )

    def get_process(self, meeting_id: str) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM summary_processes WHERE meeting_id = ?",
                (meeting_id,),
            ).fetchone()
            return dict(row) if row else None

    # ---------------------------------------------------------- transcript chunk
    def save_transcript_chunk(self, meeting_id: str, transcript_text: str,
                              model: str, model_name: str, chunk_size: int,
                              overlap: int, meeting_name: Optional[str] = None) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO transcript_chunks (meeting_id, meeting_name,
                       transcript_text, model, model_name, chunk_size, overlap,
                       created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(meeting_id) DO UPDATE SET
                       transcript_text=excluded.transcript_text,
                       model=excluded.model, model_name=excluded.model_name,
                       chunk_size=excluded.chunk_size, overlap=excluded.overlap,
                       created_at=excluded.created_at""",
                (meeting_id, meeting_name, transcript_text, model, model_name,
                 chunk_size, overlap, _now()),
            )

    # -------------------------------------------------------------- model config
    def save_model_config(self, provider: str, model: str, whisper_model: str,
                          api_key: Optional[str] = None,
                          api_key_field: Optional[str] = None) -> None:
        field = api_key_field or MODEL_API_KEY_FIELDS.get(provider)
        with self._connect() as conn:
            conn.execute("DELETE FROM settings")
            conn.execute(
                """INSERT INTO settings (id, provider, model, whisperModel)
                   VALUES ('default', ?, ?, ?)""",
                (provider, model, whisper_model),
            )
            if field and api_key is not None:
                conn.execute(
                    f"UPDATE settings SET {field} = ? WHERE id = 'default'",
                    (api_key,),
                )

    def get_model_config(self) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, provider, model, whisperModel FROM settings "
                "WHERE id = 'default'"
            ).fetchone()
            return dict(row) if row else None

    def get_api_key(self, provider: str) -> Optional[str]:
        field = MODEL_API_KEY_FIELDS.get(provider)
        if not field:
            return None
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT {field} AS key FROM settings WHERE id = 'default'"
            ).fetchone()
            return row["key"] if row else None

    # --------------------------------------------------------- transcript config
    def save_transcript_config(self, provider: str, model: str,
                               api_key: Optional[str] = None,
                               api_key_field: Optional[str] = None) -> None:
        field = api_key_field or TRANSCRIPT_API_KEY_FIELDS.get(provider)
        with self._connect() as conn:
            conn.execute("DELETE FROM transcript_settings")
            conn.execute(
                """INSERT INTO transcript_settings (id, provider, model)
                   VALUES ('default', ?, ?)""",
                (provider, model),
            )
            if field and api_key is not None:
                conn.execute(
                    f"UPDATE transcript_settings SET {field} = ? WHERE id = 'default'",
                    (api_key,),
                )

    def get_transcript_config(self) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, provider, model FROM transcript_settings "
                "WHERE id = 'default'"
            ).fetchone()
            return dict(row) if row else None

    def get_transcript_api_key(self, provider: str) -> Optional[str]:
        field = TRANSCRIPT_API_KEY_FIELDS.get(provider)
        if not field:
            return None
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT {field} AS key FROM transcript_settings WHERE id = 'default'"
            ).fetchone()
            return row["key"] if row else None


    # ----------------------------------------------------------- diarize jobs
    def create_diarize_job(self, meeting_id: str) -> None:
        now = _now()
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO diarize_jobs (meeting_id, status, step, created_at, updated_at)
                   VALUES (?, 'queued', 'queued', ?, ?)
                   ON CONFLICT(meeting_id) DO UPDATE SET status='queued', step='queued',
                       error=NULL, segments_count=NULL, updated_at=excluded.updated_at""",
                (meeting_id, now, now),
            )

    def update_diarize_job(self, meeting_id: str, **fields: Any) -> None:
        if not fields:
            return
        fields["updated_at"] = _now()
        columns = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [meeting_id]
        with self._connect() as conn:
            conn.execute(
                f"UPDATE diarize_jobs SET {columns} WHERE meeting_id = ?", values
            )

    def get_diarize_job(self, meeting_id: str) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM diarize_jobs WHERE meeting_id = ?", (meeting_id,)
            ).fetchone()
            return dict(row) if row else None


def new_id() -> str:
    return str(uuid.uuid4())

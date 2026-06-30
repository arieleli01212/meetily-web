# Diarization & Hebrew — Design Addendum

**Date:** 2026-06-30
**Builds on:** `2026-06-29-meetily-web-design.md`

## Goal
Add (1) Hebrew (multilingual) transcription and (2) speaker identification
(diarization), running air-gapped on Apple Silicon.

## Decisions (confirmed with user)
- **Engine:** WhisperX (faster-whisper + pyannote + alignment) as an external
  service reached by a configurable URL — consistent with the whisper/LLM model.
- **Timing:** post-meeting on the full recording (live transcript remains as
  instant feedback; the diarized version replaces it after Stop).
- **Hardware:** Apple Silicon. faster-whisper runs CPU int8 (no CTranslate2
  Metal backend); pyannote can use torch MPS. Device configurable.

## Hebrew (shipped separately)
- `WHISPER_LANGUAGE` config forwarded to whisper `/inference`. Requires a
  multilingual whisper model (not `*.en`). Also applies to the WhisperX service.

## Components

### WhisperX service (`whisperx-service/`)
FastAPI app wrapping the `whisperx` package.
- `POST /transcribe-diarize` (multipart `file`, optional `language`,
  `min_speakers`, `max_speakers`) → `{ "language": str, "segments":
  [ {"start": float, "end": float, "text": str, "speaker": str} ] }`.
- Model size, device, and compute type from env (`WHISPERX_MODEL`,
  `WHISPERX_DEVICE`, `WHISPERX_COMPUTE_TYPE`).
- pyannote diarization model gated on HuggingFace — downloaded once (online)
  into a cache, then runs offline. `HF_TOKEN` build/run arg documented.

### Backend
- `transcripts.speaker TEXT` column, added via idempotent migration
  (`ALTER TABLE ... ADD COLUMN` when absent) so existing DBs upgrade.
- `db.replace_transcripts(meeting_id, segments)` — wipe + insert diarized rows.
- `DIARIZE_SERVER_URL` config.
- `POST /transcribe-diarized` (multipart `file`, form `meeting_id`,
  optional `meeting_title`): create meeting if needed, forward audio to the
  WhisperX service, store speaker-labeled segments, return them. 502 if the
  service is unreachable.
- `get-meeting` transcripts include `speaker`.

### Frontend
- `Recorder` retains the full session PCM and exposes `getFullWav()`.
- Record page: "Identify speakers" toggle. On Stop → save meeting → if enabled,
  upload full WAV to `/transcribe-diarized`, then navigate to the meeting.
- Meeting page: render `Speaker N:` prefix when present.
- Meetings page: "Import audio" → upload a file to `/transcribe-diarized`
  (new meeting) for diarized transcription of existing recordings.

### Packaging
- `whisperx-service/` Dockerfile + run docs (native recommended on Apple
  Silicon). `.env.example`, `docker-compose.yml`, and README updated with
  `DIARIZE_SERVER_URL` and WhisperX setup.

## Testing
- Backend `/transcribe-diarized` proxy tested against a mocked WhisperX service
  (httpx MockTransport): segments stored with speakers; 502 on failure;
  migration adds the column.
- WhisperX service: real model runs are the operator's responsibility (large
  models, HF token); the service code is structured for a light import check.

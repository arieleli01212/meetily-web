# Meetily Web — Design Spec

**Date:** 2026-06-29
**Goal:** Re-implement [meetily](https://github.com/Zackriya-Solutions/meetily) as a **web-based** application (not a Tauri desktop app), as faithful a clone as possible, with **all connection parameters configurable** and able to run in a fully **air-gapped** environment.

## 1. Background — what meetily is

Meetily is a privacy-first AI meeting assistant. The current upstream is a Tauri desktop app (Rust + Next.js), but it ships a legacy **Python FastAPI backend** whose API contract and SQLite schema we clone here because they map cleanly to a web app.

Original pipeline:
- Capture mic + system audio locally.
- Transcribe with a local **whisper.cpp** server.
- Store meetings/transcripts in **SQLite**.
- Summarize transcripts by chunking and sending to a configurable **LLM** (Ollama local, or Anthropic/Groq/OpenAI/OpenRouter/custom OpenAI-compatible).
- Display/edit/export in a **Next.js** UI.

## 2. Goals & non-goals

**Goals**
- Web app accessible from a browser (no desktop install).
- Faithful clone of meetily's backend API contract and SQLite schema.
- Every connection parameter configurable (env var + runtime settings UI): backend host/port, whisper server URL, LLM provider/base-URL/model/api-key, chunking params.
- Runs fully offline / air-gapped: no CDN assets, no telemetry, no mandatory external API. Defaults target local whisper + local Ollama.
- Docker Compose for one-command bring-up of frontend + backend.

**Non-goals (YAGNI)**
- Not bundling whisper or the LLM inside our compose — they are external services reached via configurable URLs (per user decision).
- No Tauri/Rust desktop packaging.
- No Meetily PRO features (speaker diarization, calendar integration, team mgmt).
- No multi-tenant auth in v1 (single-instance, trusted network).

## 3. Architecture

```
┌─────────────────┐     HTTP/WS      ┌──────────────────┐
│  Browser         │ ───────────────► │  FastAPI backend │
│  (Next.js SPA)   │                  │                  │
│  - meeting list  │ ◄─────────────── │  - REST API      │
│  - live record   │                  │  - SQLite        │
│  - settings      │                  │  - summarizer    │
└─────────────────┘                  └───┬──────────┬───┘
                                          │          │
                        configurable URL  │          │  configurable URL
                                          ▼          ▼
                                 ┌──────────────┐  ┌──────────────┐
                                 │ whisper.cpp   │  │ LLM provider │
                                 │ server        │  │ (Ollama/...) │
                                 └──────────────┘  └──────────────┘
```

Three layers, with the two external ones (whisper, LLM) reached purely by configurable URL.

## 4. Components

### 4.1 Backend (FastAPI + SQLite) — `backend/`
Faithful re-implementation of meetily's endpoints. Same SQLite schema:

- **meetings**: id, title, created_at, updated_at, folder_path
- **transcripts**: id, meeting_id(FK), transcript, timestamp, summary, action_items, key_points, audio_start_time, audio_end_time, duration
- **summary_processes**: meeting_id(PK,FK), status, created_at, updated_at, error, result, start_time, end_time, chunk_count, processing_time, metadata
- **transcript_chunks**: meeting_id(PK,FK), meeting_name, transcript_text, model, model_name, chunk_size, overlap, created_at
- **settings**: id, provider, model, whisperModel, groqApiKey, openaiApiKey, anthropicApiKey, ollamaApiKey
- **transcript_settings**: id, provider, model, whisperApiKey, deepgramApiKey, elevenLabsApiKey, groqApiKey, openaiApiKey

REST endpoints (clone of upstream):
| Method | Path |
|--------|------|
| GET  | `/get-meetings` |
| GET  | `/get-meeting/{meeting_id}` |
| POST | `/save-meeting-title` |
| POST | `/delete-meeting` |
| POST | `/process-transcript` |
| GET  | `/get-summary/{meeting_id}` |
| POST | `/save-transcript` |
| GET  | `/get-model-config` |
| POST | `/save-model-config` |
| GET  | `/get-transcript-config` |
| POST | `/save-transcript-config` |
| POST | `/get-api-key` |
| POST | `/get-transcript-api-key` |
| POST | `/save-meeting-summary` |
| POST | `/search-transcripts` |

Added for the web/air-gapped model:
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/transcribe` | Receive an audio chunk from the browser, forward to the configured whisper.cpp server URL, return transcript text. |
| GET  | `/health` | Liveness + reports configured whisper/LLM URLs reachability. |
| GET  | `/get-config` | Return non-secret runtime config (URLs, ports) for the UI to display. |

**Summarization** (`/process-transcript`): chunk transcript by `chunk_size`/`overlap`, send each chunk to the configured LLM via a provider abstraction, merge into structured JSON `{ summary, action_items, key_points }`, track progress in `summary_processes`, store result. Runs as a background task; client polls `/get-summary/{meeting_id}`.

**LLM provider abstraction**: single interface, implementations for Ollama, OpenAI-compatible (covers OpenAI/Groq/OpenRouter/custom), Anthropic. Each takes base URL + model + api key from config — so air-gapped points at local Ollama.

### 4.2 Frontend (Next.js) — `frontend/`
- **Meetings list** — list/search/delete, create new.
- **Recording view** — Web Audio API mic capture (+ system audio via `getDisplayMedia` where supported), chunked upload to `/transcribe`, live transcript display.
- **Meeting detail** — transcript, generate/view summary (sections), edit title, export (Markdown/JSON).
- **Settings page** — edit every connection parameter: whisper URL, LLM provider/base-URL/model/api-key, transcription provider config, chunk size/overlap. Persisted via the config endpoints.
- All assets self-hosted (fonts, JS) — no CDN. Backend base URL configurable via `NEXT_PUBLIC_API_URL`.

### 4.3 Configuration layer
All connections configurable via env (compose) + runtime settings (DB-backed, editable in UI):
- `BACKEND_HOST`, `BACKEND_PORT`
- `WHISPER_SERVER_URL`
- `LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`
- `DB_PATH`
- `CHUNK_SIZE`, `CHUNK_OVERLAP`
- `NEXT_PUBLIC_API_URL` (frontend → backend)

Precedence: runtime DB settings override env defaults; env overrides built-in defaults.

### 4.4 Docker Compose
Two services: `frontend`, `backend`. Whisper & LLM referenced by env URL (not run by us). A `.env.example` documents all params. Images build offline from vendored deps.

## 5. Air-gapped guarantees
- No CDN/Google Fonts/analytics; fonts and JS bundled.
- No outbound calls except to the configured whisper & LLM URLs.
- Defaults target localhost services so it works with zero internet.
- pip/npm deps installable from a local mirror or pre-built images.

## 6. Error handling
- Backend validates config; `/health` surfaces unreachable whisper/LLM.
- Transcribe/summarize failures recorded (summary_processes.error) and surfaced in UI.
- Frontend shows clear states: recording, transcribing, summarizing, error.

## 7. Testing
- Backend: pytest for each endpoint (CRUD, config, search), summarizer chunking logic, provider abstraction (mocked HTTP), `/transcribe` proxy (mocked whisper).
- Frontend: component tests for settings + recording state machine.
- Integration: docker compose up, smoke test against a mock whisper + mock LLM.

## 8. Build order (high level)
1. Repo scaffold + docker-compose + config layer.
2. Backend: DB schema + CRUD endpoints + tests.
3. Backend: summarizer + LLM providers + tests.
4. Backend: `/transcribe` proxy + `/health` + tests.
5. Frontend: scaffold + meetings list + settings page.
6. Frontend: recording view + transcript + summary.
7. Air-gapped hardening + docs + integration smoke test.

Each step is committed and pushed.

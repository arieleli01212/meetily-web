# Meetily Web Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a web-based, air-gapped, fully-configurable clone of meetily (Next.js frontend + FastAPI backend + SQLite; external whisper.cpp and LLM reached via configurable URLs).

**Architecture:** Browser captures audio and calls a FastAPI backend. The backend persists meetings/transcripts/summaries in SQLite, proxies audio to a configurable whisper.cpp server, and summarizes transcripts via a configurable LLM provider. All connection parameters are env-configurable and runtime-editable.

**Tech Stack:** Python 3.11 / FastAPI / uvicorn / httpx / pytest (backend); Next.js 14 / React / TypeScript (frontend); SQLite; Docker Compose.

## Global Constraints
- Air-gapped: no CDN, no telemetry, no mandatory outbound calls except configured whisper & LLM URLs.
- Clone meetily's API paths and SQLite schema verbatim where they exist.
- Every connection parameter configurable via env var, with runtime DB override.
- TDD: failing test first; commit per task; push after each phase.

---

## Phase 1 — Backend foundation

### Task 1: Project scaffold & config layer
**Files:** `backend/app/config.py`, `backend/requirements.txt`, `backend/tests/test_config.py`, `backend/app/__init__.py`
- Pydantic `Settings` reading env: BACKEND_HOST/PORT, WHISPER_SERVER_URL, LLM_PROVIDER/BASE_URL/MODEL/API_KEY, DB_PATH, CHUNK_SIZE, CHUNK_OVERLAP.
- Test: defaults present; env override works.

### Task 2: Database layer & schema
**Files:** `backend/app/db.py`, `backend/tests/test_db.py`
- Create all 6 tables (meetings, transcripts, summary_processes, transcript_chunks, settings, transcript_settings) matching meetily schema.
- Methods: save/get/delete meeting, save transcript, create/update process, save/get config, save/get api key, search.
- Test: CRUD round-trips on a temp DB.

### Task 3: Meetings CRUD endpoints
**Files:** `backend/app/main.py`, `backend/app/models.py`, `backend/tests/test_meetings_api.py`
- Endpoints: get-meetings, get-meeting/{id}, save-meeting-title, delete-meeting, save-transcript, search-transcripts.
- Pydantic models matching upstream. CORS open.
- Test: via FastAPI TestClient.

### Task 4: Config endpoints
**Files:** `backend/app/main.py` (extend), `backend/tests/test_config_api.py`
- get/save-model-config, get/save-transcript-config, get-api-key, get-transcript-api-key, get-config, health.
- Test: round-trip config; health reports configured URLs.

## Phase 2 — Summarization

### Task 5: LLM provider abstraction
**Files:** `backend/app/llm.py`, `backend/tests/test_llm.py`
- `LLMProvider` interface; implementations: Ollama, OpenAICompatible (OpenAI/Groq/OpenRouter/custom), Anthropic. Factory from config.
- `complete(prompt) -> str`. Uses httpx; base_url/model/api_key from config.
- Test: mocked httpx for each provider returns parsed text.

### Task 6: Summarizer + process-transcript
**Files:** `backend/app/summarizer.py`, `backend/app/main.py` (extend), `backend/tests/test_summarizer.py`
- Chunk transcript by chunk_size/overlap; per-chunk LLM call; merge to `{summary, action_items, key_points}`; persist to summary_processes; background task.
- Endpoints: process-transcript, get-summary/{id}, save-meeting-summary.
- Test: chunking boundaries; end-to-end with mocked LLM; status transitions.

## Phase 3 — Transcription proxy

### Task 7: /transcribe proxy to whisper.cpp
**Files:** `backend/app/transcribe.py`, `backend/app/main.py` (extend), `backend/tests/test_transcribe.py`
- Accept multipart audio; forward to WHISPER_SERVER_URL `/inference`; return text.
- Test: mocked whisper server returns transcript; error when unreachable.

## Phase 4 — Frontend (Next.js)

### Task 8: Frontend scaffold + API client
**Files:** `frontend/package.json`, `frontend/next.config.js`, `frontend/app/*`, `frontend/lib/api.ts`
- Next.js app, self-hosted fonts, `NEXT_PUBLIC_API_URL`. Typed API client for all endpoints.

### Task 9: Meetings list + detail + settings pages
**Files:** `frontend/app/page.tsx`, `frontend/app/meeting/[id]/page.tsx`, `frontend/app/settings/page.tsx`
- List/search/delete/create; detail with transcript + summary; settings editing all connection params.

### Task 10: Recording view
**Files:** `frontend/app/record/page.tsx`, `frontend/lib/recorder.ts`
- Web Audio mic capture (+ getDisplayMedia), chunked upload to /transcribe, live transcript, save meeting.

## Phase 5 — Air-gapped packaging

### Task 11: Docker Compose + env + docs
**Files:** `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile`, `.env.example`, `README.md`
- frontend + backend services; whisper & LLM via env URLs; offline build; full README.

---

## Self-Review
- Spec coverage: all 15 upstream endpoints (Tasks 3,4,6) + transcribe/health/get-config (Tasks 4,7); schema (Task 2); providers (Task 5); air-gapped (Task 11); frontend incl. settings (Tasks 8-10). Covered.
- No placeholders in task intent; concrete code written during TDD execution.
- Type consistency: config keys reused across config.py/db settings/frontend settings.

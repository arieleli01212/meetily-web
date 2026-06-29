# Meetily Web

A **web-based**, **air-gapped**, fully-configurable clone of
[meetily](https://github.com/Zackriya-Solutions/meetily) — the privacy-first AI
meeting assistant. Where upstream meetily ships as a Tauri desktop app, this is
a browser application backed by a FastAPI server, with **every external
connection configurable** so it runs entirely on local/offline infrastructure.

## What it does

- Record meetings in the browser (microphone + optional system/tab audio).
- Transcribe audio via an **external whisper.cpp server** (configurable URL).
- Store meetings, transcripts, and summaries in **SQLite**.
- Summarize transcripts via a **configurable LLM** (Ollama / OpenAI-compatible /
  Anthropic), producing structured summary, action items, and key points.
- Browse, search, rename, delete meetings; export to Markdown.

## Architecture

```
Browser (Next.js)  ──►  FastAPI backend  ──►  whisper.cpp server   (WHISPER_SERVER_URL)
                              │           ──►  LLM provider/Ollama  (LLM_BASE_URL)
                              └──►  SQLite (volume)
```

The whisper server and the LLM are **external services reached by URL** — they
are not bundled, so you point the configuration at whatever runs on your
network. This is the core of the air-gapped design: no component requires the
public internet.

## API (cloned from meetily)

`GET /get-meetings` · `GET /get-meeting/{id}` · `POST /save-meeting-title` ·
`POST /delete-meeting` · `POST /save-transcript` · `POST /search-transcripts` ·
`POST /process-transcript` · `GET /get-summary/{id}` · `POST /save-meeting-summary` ·
`GET|POST /get|save-model-config` · `GET|POST /get|save-transcript-config` ·
`POST /get-api-key` · `POST /get-transcript-api-key`

Web/air-gapped additions: `POST /transcribe` (proxy to whisper), `GET /get-config`
(non-secret connection params for the UI), `GET /health`.

## Configuration

All connection parameters are environment variables (see `.env.example`):

| Variable | Purpose | Default |
|----------|---------|---------|
| `BACKEND_PORT` | Backend port | `5167` |
| `FRONTEND_PORT` | Frontend port | `3000` |
| `NEXT_PUBLIC_API_URL` | Backend URL the browser calls | `http://localhost:5167` |
| `WHISPER_SERVER_URL` | External whisper.cpp server | `http://localhost:8178` |
| `LLM_PROVIDER` | `ollama`/`openai`/`groq`/`openrouter`/`anthropic` | `ollama` |
| `LLM_BASE_URL` | LLM endpoint | `http://localhost:11434` |
| `LLM_MODEL` | Model name | `llama3.2` |
| `LLM_API_KEY` | API key (blank for local) | _empty_ |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | Summarization chunking | `5000` / `1000` |

The summarization provider/model and whisper model are also editable at runtime
on the **Settings** page (persisted in SQLite, overriding env defaults).

## Run with Docker Compose

```bash
cp .env.example .env       # edit URLs for your whisper + LLM
docker compose up --build
# Frontend: http://localhost:3000   Backend: http://localhost:5167
```

For a fully air-gapped host: build the images on a connected machine, `docker
save`/`docker load` them onto the target, and run with the same `.env`.

## External services

- **whisper.cpp server** — run the whisper.cpp HTTP server (`./server -m
  models/ggml-base.en.bin --host 0.0.0.0 --port 8178`) and set
  `WHISPER_SERVER_URL` to it.
- **Ollama** (recommended local LLM) — `ollama serve` then `ollama pull
  llama3.2`; set `LLM_BASE_URL=http://<host>:11434`.

Both can run on the same host or anywhere reachable on your private network.

## Local development

Backend:
```bash
cd backend
python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload --port 5167
.venv/bin/pytest          # 36 tests
```

Frontend:
```bash
cd frontend
pnpm install
NEXT_PUBLIC_API_URL=http://localhost:5167 pnpm dev
```

## Acknowledgements

API contract and feature set modeled on
[Zackriya-Solutions/meetily](https://github.com/Zackriya-Solutions/meetily)
(MIT). Transcription relies on whisper.cpp.

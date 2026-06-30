# WhisperX Diarization Service

Transcription **with speaker identification** for meetily-web. Wraps
[WhisperX](https://github.com/m-bain/whisperX) (faster-whisper + pyannote +
alignment) behind one HTTP endpoint the backend calls post-meeting.

```
POST /transcribe-diarize   (multipart: file, [language], [min_speakers], [max_speakers])
  -> { "language": "he", "segments": [ {start, end, text, speaker} ] }
GET  /health
```

## Apple Silicon (recommended: run natively, not in Docker)

CTranslate2 (faster-whisper) has **no Metal backend**, so the transcription
step runs on CPU with `int8`. pyannote can use Apple's MPS via torch. Native
execution avoids Docker's lack of GPU/MPS passthrough on macOS.

```bash
cd whisperx-service
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt    # pulls torch, pyannote, faster-whisper

# One-time, ONLINE: accept the pyannote model terms on HuggingFace and export a
# token so the diarization model can download into the local cache.
#   https://hf.co/pyannote/speaker-diarization-3.1  (Accept)
export HF_TOKEN=hf_xxx

export WHISPERX_MODEL=medium      # large-v3 = best Hebrew, slower on CPU
export WHISPERX_DEVICE=cpu        # diarization may use mps; transcription is cpu
export WHISPERX_COMPUTE_TYPE=int8
export WHISPERX_LANGUAGE=he       # force Hebrew (or leave blank to auto-detect)

.venv/bin/uvicorn app:app --host 0.0.0.0 --port 9000
```

After the first run the models are cached under `~/.cache` — unplug the network
and it keeps working (air-gapped). To move to a fully offline machine, copy the
HuggingFace cache (`~/.cache/huggingface`) and the whisper model cache along
with the venv.

Then point the backend at it:

```
DIARIZE_SERVER_URL=http://localhost:9000
WHISPER_LANGUAGE=he
```

## Docker (Linux / CUDA hosts)

```bash
docker build -t meetily-whisperx .
docker run --gpus all -p 9000:9000 \
  -e HF_TOKEN=hf_xxx -e WHISPERX_DEVICE=cuda -e WHISPERX_COMPUTE_TYPE=float16 \
  -e WHISPERX_MODEL=large-v3 -e WHISPERX_LANGUAGE=he \
  -v whisperx-cache:/root/.cache meetily-whisperx
```

(For air-gapped Docker, bake the model cache into the image or mount a
pre-populated cache volume.)

## Notes
- `min_speakers`/`max_speakers` help when you know the participant count.
- Speaker labels are `SPEAKER_00`, `SPEAKER_01`, … (consistent within a meeting).
- Hebrew alignment models may be limited; the service degrades gracefully to
  unaligned (still speaker-labeled) segments if alignment is unavailable.

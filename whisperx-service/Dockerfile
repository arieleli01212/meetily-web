# WhisperX service image (Linux/CUDA hosts). On Apple Silicon, run natively
# instead (see README) — macOS Docker has no GPU/MPS passthrough.
FROM python:3.11-slim

# ffmpeg is required by whisperx for audio decoding.
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

ENV WHISPERX_MODEL=medium \
    WHISPERX_DEVICE=cpu \
    WHISPERX_COMPUTE_TYPE=int8
EXPOSE 9000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "9000"]

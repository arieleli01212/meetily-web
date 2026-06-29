# Backend image. For air-gapped builds, pre-populate a local PyPI mirror or
# build once with network and ship the resulting image.
FROM python:3.11-slim

WORKDIR /app

# Install dependencies first for layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Persisted SQLite lives under /data (mounted volume).
ENV DB_PATH=/data/meetily.db
EXPOSE 5167

# Honour BACKEND_HOST/BACKEND_PORT at runtime.
CMD ["sh", "-c", "uvicorn app.main:app --host ${BACKEND_HOST:-0.0.0.0} --port ${BACKEND_PORT:-5167}"]

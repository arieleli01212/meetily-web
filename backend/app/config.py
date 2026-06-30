"""Centralized, env-driven configuration for the meetily web backend.

Every external connection parameter lives here so the app can run in an
air-gapped environment by pointing these at local services. Runtime DB
settings (see app.db) override these defaults at request time, but these
provide the bootstrap defaults and the values used before any DB row exists.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Server
    backend_host: str = "0.0.0.0"
    backend_port: int = 5167

    # Storage
    db_path: str = "data/meetily.db"

    # Transcription (external whisper.cpp server, reached by URL)
    whisper_server_url: str = "http://localhost:8178"
    # Force transcription language (ISO code, e.g. "he" for Hebrew). Empty =
    # let the whisper server auto-detect.
    whisper_language: str = ""

    # LLM provider (external, reached by URL)
    llm_provider: str = "ollama"  # ollama | openai | anthropic
    llm_base_url: str = "http://localhost:11434"
    llm_model: str = "llama3.2"
    llm_api_key: str = ""

    # Summarization chunking
    chunk_size: int = 5000
    chunk_overlap: int = 1000


@lru_cache
def get_settings() -> Settings:
    return Settings()

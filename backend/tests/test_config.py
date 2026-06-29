"""Tests for the configuration layer."""
import importlib

from app import config as config_module


def _fresh_settings(monkeypatch, **env):
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    importlib.reload(config_module)
    return config_module.get_settings()


def test_defaults_present(monkeypatch):
    # Clear any env that would override defaults.
    for key in [
        "WHISPER_SERVER_URL", "LLM_PROVIDER", "LLM_BASE_URL",
        "LLM_MODEL", "CHUNK_SIZE", "CHUNK_OVERLAP", "BACKEND_PORT",
    ]:
        monkeypatch.delenv(key, raising=False)
    settings = _fresh_settings(monkeypatch)
    assert settings.backend_host == "0.0.0.0"
    assert settings.backend_port == 5167
    assert settings.whisper_server_url == "http://localhost:8178"
    assert settings.llm_provider == "ollama"
    assert settings.llm_base_url == "http://localhost:11434"
    assert settings.chunk_size == 5000
    assert settings.chunk_overlap == 1000


def test_env_override(monkeypatch):
    settings = _fresh_settings(
        monkeypatch,
        WHISPER_SERVER_URL="http://whisper.internal:9000",
        LLM_PROVIDER="openai",
        LLM_BASE_URL="http://llm.internal:8080/v1",
        LLM_MODEL="llama3",
        CHUNK_SIZE="2000",
        BACKEND_PORT="6000",
    )
    assert settings.whisper_server_url == "http://whisper.internal:9000"
    assert settings.llm_provider == "openai"
    assert settings.llm_base_url == "http://llm.internal:8080/v1"
    assert settings.llm_model == "llama3"
    assert settings.chunk_size == 2000
    assert settings.backend_port == 6000

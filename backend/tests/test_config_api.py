"""Tests for configuration, health, and runtime-config endpoints."""


def test_model_config_roundtrip(client):
    resp = client.post("/save-model-config", json={
        "provider": "ollama", "model": "llama3",
        "whisperModel": "base.en", "apiKey": "secret-key",
    })
    assert resp.status_code == 200
    cfg = client.get("/get-model-config").json()
    assert cfg["provider"] == "ollama"
    assert cfg["model"] == "llama3"
    assert cfg["whisperModel"] == "base.en"
    key = client.post("/get-api-key", json={"provider": "ollama"}).json()
    assert key["apiKey"] == "secret-key"


def test_transcript_config_roundtrip(client):
    resp = client.post("/save-transcript-config", json={
        "provider": "whisper", "model": "base.en", "apiKey": "wk",
    })
    assert resp.status_code == 200
    cfg = client.get("/get-transcript-config").json()
    assert cfg["provider"] == "whisper"
    key = client.post("/get-transcript-api-key",
                      json={"provider": "whisper"}).json()
    assert key["apiKey"] == "wk"


def test_get_config_exposes_connection_params(client):
    cfg = client.get("/get-config").json()
    assert "whisper_server_url" in cfg
    assert "llm_provider" in cfg
    assert "llm_base_url" in cfg
    # Secrets must not be exposed here.
    assert "llm_api_key" not in cfg


def test_health(client):
    health = client.get("/health").json()
    assert health["status"] == "ok"
    assert "whisper_server_url" in health
    assert "llm_base_url" in health

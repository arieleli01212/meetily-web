"""Tests for app.health connectivity checks."""
from unittest.mock import patch

import httpx
import pytest

from app.health import check_diarize, check_llm, check_whisper, run_startup_checks
from app.config import Settings


# ---- individual check helpers ----------------------------------------------

def _ok_response(status_code=200):
    return httpx.Response(status_code, content=b"{}")


def test_check_whisper_ok():
    with patch("httpx.get", return_value=_ok_response(200)):
        r = check_whisper("http://localhost:8178")
    assert r["status"] == "ok"
    assert r["service"] == "whisper"
    assert r["http"] == 200


def test_check_whisper_unreachable():
    with patch("httpx.get", side_effect=httpx.ConnectError("refused")):
        r = check_whisper("http://localhost:8178")
    assert r["status"] == "unreachable"
    assert "connection refused" in r["error"]


def test_check_whisper_timeout():
    with patch("httpx.get", side_effect=httpx.TimeoutException("timeout")):
        r = check_whisper("http://localhost:8178")
    assert r["status"] == "unreachable"
    assert "timed out" in r["error"]


def test_check_diarize_ok():
    with patch("httpx.get", return_value=_ok_response(200)):
        r = check_diarize("http://localhost:9000")
    assert r["status"] == "ok"
    assert r["service"] == "diarize"


def test_check_llm_ollama_ok():
    with patch("httpx.get", return_value=_ok_response(200)):
        r = check_llm("ollama", "http://localhost:11434")
    assert r["status"] == "ok"
    assert r["provider"] == "ollama"


def test_check_llm_cloud_providers_not_probed():
    for provider in ("anthropic", "groq", "openrouter"):
        r = check_llm(provider, "https://api.example.com")
        assert r["status"] == "cloud"
        assert r["provider"] == provider


def test_check_llm_openai_compat():
    with patch("httpx.get", return_value=_ok_response(200)):
        r = check_llm("openai", "http://my-proxy:8080")
    assert r["status"] == "ok"


# ---- run_startup_checks ---------------------------------------------------

def _make_settings(**kwargs):
    defaults = dict(
        whisper_server_url="http://localhost:8178",
        diarize_server_url="http://localhost:9000",
        llm_provider="ollama",
        llm_base_url="http://localhost:11434",
    )
    defaults.update(kwargs)
    return Settings(**defaults)


def test_run_startup_checks_all_ok():
    with patch("httpx.get", return_value=_ok_response(200)):
        checks = run_startup_checks(_make_settings())
    assert checks["whisper"]["status"] == "ok"
    assert checks["diarize"]["status"] == "ok"
    assert checks["llm"]["status"] == "ok"


def test_run_startup_checks_all_down():
    with patch("httpx.get", side_effect=httpx.ConnectError("refused")):
        checks = run_startup_checks(_make_settings())
    for name in ("whisper", "diarize", "llm"):
        assert checks[name]["status"] == "unreachable"


def test_run_startup_checks_cloud_llm():
    with patch("httpx.get", return_value=_ok_response(200)):
        checks = run_startup_checks(
            _make_settings(llm_provider="anthropic", llm_base_url="https://api.anthropic.com")
        )
    assert checks["llm"]["status"] == "cloud"


def test_run_startup_checks_logs(caplog):
    with patch("httpx.get", return_value=_ok_response(200)):
        with caplog.at_level("INFO", logger="meetily.startup"):
            run_startup_checks(_make_settings())
    log = caplog.text
    assert "✓" in log
    assert "whisper" in log
    assert "diarize" in log
    assert "llm" in log


def test_run_startup_checks_logs_warning_on_unreachable(caplog):
    with patch("httpx.get", side_effect=httpx.ConnectError("refused")):
        with caplog.at_level("WARNING", logger="meetily.startup"):
            run_startup_checks(_make_settings())
    assert "UNREACHABLE" in caplog.text

"""Tests for the LLM provider abstraction (mocked HTTP)."""
import httpx

from app.llm import build_provider


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_ollama_provider(monkeypatch):
    captured = {}

    def handler(request):
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"response": "  a summary  "})

    provider = build_provider(
        provider="ollama", base_url="http://ollama:11434",
        model="llama3", api_key="", client=_client(handler),
    )
    out = provider.complete("summarize this")
    assert out == "a summary"
    assert captured["url"].endswith("/api/generate")


def test_openai_compatible_provider():
    def handler(request):
        assert request.url.path.endswith("/chat/completions")
        assert request.headers["authorization"] == "Bearer k"
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "openai out"}}]
        })

    provider = build_provider(
        provider="openai", base_url="http://llm:8080/v1",
        model="gpt", api_key="k", client=_client(handler),
    )
    assert provider.complete("hi") == "openai out"


def test_anthropic_provider():
    def handler(request):
        assert request.url.path.endswith("/v1/messages")
        assert request.headers["x-api-key"] == "ak"
        return httpx.Response(200, json={
            "content": [{"type": "text", "text": "claude out"}]
        })

    provider = build_provider(
        provider="anthropic", base_url="https://api.anthropic.com",
        model="claude", api_key="ak", client=_client(handler),
    )
    assert provider.complete("hi") == "claude out"


def test_unknown_provider_defaults_to_openai_compatible():
    def handler(request):
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "ok"}}]
        })

    provider = build_provider(
        provider="groq", base_url="http://groq/v1",
        model="m", api_key="k", client=_client(handler),
    )
    assert provider.complete("hi") == "ok"

"""LLM provider abstraction.

A single `complete(prompt)` interface with implementations for the providers
meetily supports. All providers take a base URL, model, and API key from
configuration, so an air-gapped deployment simply points at a local Ollama or
a local OpenAI-compatible server. The OpenAI-compatible implementation covers
OpenAI, Groq, OpenRouter, and any custom compatible endpoint.
"""
from __future__ import annotations

from typing import Optional

import httpx

DEFAULT_TIMEOUT = 120.0


class LLMProvider:
    def __init__(self, base_url: str, model: str, api_key: str,
                 client: Optional[httpx.Client] = None):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self._client = client or httpx.Client(timeout=DEFAULT_TIMEOUT)

    def complete(self, prompt: str, system: Optional[str] = None) -> str:
        raise NotImplementedError


class OllamaProvider(LLMProvider):
    def complete(self, prompt: str, system: Optional[str] = None) -> str:
        payload = {"model": self.model, "prompt": prompt, "stream": False}
        if system:
            payload["system"] = system
        resp = self._client.post(f"{self.base_url}/api/generate", json=payload)
        resp.raise_for_status()
        return resp.json().get("response", "").strip()


class OpenAICompatibleProvider(LLMProvider):
    def complete(self, prompt: str, system: Optional[str] = None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        resp = self._client.post(
            f"{self.base_url}/chat/completions",
            json={"model": self.model, "messages": messages},
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()


class AnthropicProvider(LLMProvider):
    def complete(self, prompt: str, system: Optional[str] = None) -> str:
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }
        payload = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system
        resp = self._client.post(
            f"{self.base_url}/v1/messages", json=payload, headers=headers
        )
        resp.raise_for_status()
        blocks = resp.json().get("content", [])
        text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        return text.strip()


def build_provider(provider: str, base_url: str, model: str, api_key: str,
                   client: Optional[httpx.Client] = None) -> LLMProvider:
    provider = (provider or "").lower()
    if provider == "ollama":
        return OllamaProvider(base_url, model, api_key, client)
    if provider == "anthropic":
        return AnthropicProvider(base_url, model, api_key, client)
    # openai, groq, openrouter, custom, and unknown -> OpenAI-compatible
    return OpenAICompatibleProvider(base_url, model, api_key, client)

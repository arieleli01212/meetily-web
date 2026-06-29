"""Tests for transcript chunking and summarization."""
import json

from app.summarizer import chunk_text, summarize_transcript


class FakeProvider:
    """Returns a canned JSON summary, recording how many chunks it saw."""

    def __init__(self, response):
        self._response = response
        self.calls = 0

    def complete(self, prompt, system=None):
        self.calls += 1
        return self._response


def test_chunk_text_no_overlap():
    chunks = chunk_text("abcdefghij", chunk_size=5, overlap=0)
    assert chunks == ["abcde", "fghij"]


def test_chunk_text_with_overlap():
    chunks = chunk_text("abcdefghij", chunk_size=5, overlap=2)
    # step = 5 - 2 = 3 -> starts 0,3,6,9
    assert chunks[0] == "abcde"
    assert chunks[1] == "defgh"
    assert chunks[-1].startswith("j") or "j" in chunks[-1]


def test_chunk_text_short_returns_single():
    assert chunk_text("hi", chunk_size=100, overlap=10) == ["hi"]


def test_summarize_single_chunk_parses_json():
    provider = FakeProvider(json.dumps({
        "summary": "We discussed the roadmap.",
        "action_items": ["Email the client"],
        "key_points": ["Q3 launch"],
    }))
    result = summarize_transcript("short text", provider,
                                  chunk_size=1000, overlap=0)
    assert provider.calls == 1
    assert result["summary"] == "We discussed the roadmap."
    assert result["action_items"] == ["Email the client"]
    assert result["key_points"] == ["Q3 launch"]


def test_summarize_merges_multiple_chunks():
    provider = FakeProvider(json.dumps({
        "summary": "part",
        "action_items": ["do x"],
        "key_points": ["point"],
    }))
    text = "a" * 25
    result = summarize_transcript(text, provider, chunk_size=10, overlap=0)
    assert provider.calls == 3  # 25/10 -> 3 chunks
    # merged action items accumulate across chunks
    assert result["action_items"].count("do x") == 3


def test_summarize_handles_non_json_response():
    provider = FakeProvider("just a plain text summary")
    result = summarize_transcript("text", provider, chunk_size=1000, overlap=0)
    assert "just a plain text summary" in result["summary"]
    assert result["action_items"] == []

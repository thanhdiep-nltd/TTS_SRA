"""Test gọi DeepSeek formatting với httpx được mock (không gọi API thật)."""

import pytest

pytest.importorskip("httpx")

from edu_pipeline import deepseek_format  # noqa: E402


class _FakeResponse:
    def __init__(self, content: str):
        self._content = content

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return {"choices": [{"message": {"content": self._content}}]}


def test_format_chunk_returns_markdown(monkeypatch):
    captured = {}

    def fake_post(url, headers, json, timeout):
        captured["url"] = url
        captured["json"] = json
        return _FakeResponse("# Bài 1\n$a^2+b^2=c^2$")

    monkeypatch.setattr(deepseek_format.httpx, "post", fake_post)

    out = deepseek_format.format_chunk("text tho", "key", "https://api.deepseek.com", "deepseek-chat")

    assert out == "# Bài 1\n$a^2+b^2=c^2$"
    assert captured["url"].endswith("/v1/chat/completions")
    assert captured["json"]["model"] == "deepseek-chat"
    assert captured["json"]["messages"][0]["content"] == deepseek_format.FORMAT_PROMPT

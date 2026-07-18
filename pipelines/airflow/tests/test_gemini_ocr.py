"""Test gọi Gemini Vision OCR (1 trang) với httpx được mock (không gọi API thật)."""

import pytest

pytest.importorskip("httpx")

from edu_pipeline import pdf_extract  # noqa: E402


class _FakeResponse:
    status_code = 200

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return {"candidates": [{"content": {"parts": [{"text": "# Bài 1\n$x^2$"}]}}]}


def test_gemini_page_parses_markdown(monkeypatch):
    captured = {}

    def fake_post(url, params, json, timeout):
        captured["url"] = url
        captured["params"] = params
        captured["json"] = json
        return _FakeResponse()

    monkeypatch.setattr("httpx.post", fake_post)

    out = pdf_extract._gemini_page("KEY", "gemini-2.0-flash", "BASE64")

    assert out == "# Bài 1\n$x^2$"
    assert captured["url"].endswith("models/gemini-2.0-flash:generateContent")
    assert captured["params"]["key"] == "KEY"
    parts = captured["json"]["contents"][0]["parts"]
    assert parts[1]["inline_data"]["data"] == "BASE64"

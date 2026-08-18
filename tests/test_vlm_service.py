"""Test offline cho src/services/vlm.py (không gọi API thật)."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest

from src.services import vlm
from src.services.vlm import VlmUnavailableError


def _settings(**overrides):
    base = dict(
        vlm_model="qwen3-vl-flash",
        vlm_api_base="https://vlm.example/v1",
        vlm_api_key="test-key",
        vlm_timeout_s=30.0,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_is_configured_requires_key():
    assert vlm.is_configured(_settings()) is True
    assert vlm.is_configured(_settings(vlm_api_key="")) is False


def test_read_image_bytes_raises_when_not_configured():
    with pytest.raises(VlmUnavailableError):
        vlm.read_image_bytes(b"fake-png", _settings(vlm_api_key=""))


def test_chat_completions_parses_text_response(monkeypatch):
    resp = MagicMock()
    resp.json.return_value = {"choices": [{"message": {"content": "Câu 1: $x^2-4=0$"}}]}
    monkeypatch.setattr(httpx, "post", lambda *a, **k: resp)

    out = vlm._chat_completions("QUJD", _settings())

    assert out == "Câu 1: $x^2-4=0$"


def test_chat_completions_retries_once_on_5xx(monkeypatch):
    """503 → retry 1 lần; lần 2 thành công thì trả text bình thường."""
    from httpx import Request, Response

    calls = {"n": 0}

    def _flaky(*_a, **_k):
        calls["n"] += 1
        if calls["n"] == 1:
            return Response(503, request=Request("POST", "http://vlm/v1/chat/completions"))
        resp = MagicMock()
        resp.json.return_value = {"choices": [{"message": {"content": "ok-after-retry"}}]}
        return resp

    monkeypatch.setattr(httpx, "post", _flaky)
    out = vlm._chat_completions("QUJD", _settings())
    assert out == "ok-after-retry"
    assert calls["n"] == 2


def test_chat_completions_raises_on_http_error(monkeypatch):
    def _boom(*_a, **_k):
        raise httpx.ConnectError("no network")

    monkeypatch.setattr(httpx, "post", _boom)
    with pytest.raises(VlmUnavailableError):
        vlm._chat_completions("QUJD", _settings())


def test_read_pdf_pages_joins_pages(monkeypatch):
    import sys

    class _Page:
        def get_pixmap(self, dpi=150):
            return SimpleNamespace(tobytes=lambda fmt="png": b"\x89PNG")

    class _Doc:
        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def __iter__(self):
            return iter([_Page(), _Page()])

    monkeypatch.setitem(sys.modules, "fitz", SimpleNamespace(open=lambda _p: _Doc()))
    monkeypatch.setattr(vlm, "is_configured", lambda *a, **k: True)
    monkeypatch.setattr(vlm, "_chat_completions", lambda b64, s: f"PAGE[{len(b64)}]")

    out = vlm.read_pdf_pages(Path("exam.pdf"))

    assert out.count("PAGE[") == 2

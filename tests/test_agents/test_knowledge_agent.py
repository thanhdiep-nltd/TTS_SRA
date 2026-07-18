"""Test offline cho luồng RAG retrieval (knowledge_agent) — mock httpx + mock retrieval.

Không chạm Qdrant/embedding-service thật.
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.agents.knowledge_agent.tools import search_textbook
from src.services import retrieval


def _fake_resp(payload: dict) -> MagicMock:
    """Giả lập httpx.Response: .json() + .raise_for_status() no-op."""
    resp = MagicMock()
    resp.json.return_value = payload
    resp.raise_for_status.return_value = None
    return resp


# ---- retrieval._build_filter ----


def test_build_filter_none():
    assert retrieval._build_filter(None, None) is None


def test_build_filter_mon_and_lop():
    flt = retrieval._build_filter("toan", 8)
    assert flt == {
        "must": [
            {"key": "mon", "match": {"value": "toan"}},
            {"key": "lop", "match": {"value": "8"}},  # lop ép về chuỗi (khớp payload)
        ]
    }


# ---- retrieval.search_textbook ----


def test_search_textbook_success():
    from src.config import Settings

    fake_settings = Settings(
        embedding_provider="local", embedding_service_url="http://embed.local", qdrant_url="http://qdrant.local"
    )
    embed_resp = _fake_resp({"vectors": [[0.1] * 1024]})
    qdrant_resp = _fake_resp(
        {
            "result": [
                {"score": 0.61, "payload": {"mon": "toan", "lop": "8", "heading": "Pythagore", "text": "..."}},
            ]
        }
    )
    with (
        patch("src.services.retrieval.get_settings", return_value=fake_settings),
        patch("src.services.retrieval.httpx.post", side_effect=[embed_resp, qdrant_resp]),
    ):
        hits = retrieval.search_textbook("định lí Pythagore", mon="toan", lop="8")
    assert len(hits) == 1
    assert hits[0]["score"] == 0.61
    assert hits[0]["mon"] == "toan"


def test_search_textbook_unavailable():
    with patch("src.services.retrieval.httpx.post", side_effect=httpx.ConnectError("down")):
        with pytest.raises(retrieval.RetrievalUnavailableError):
            retrieval.search_textbook("bất kỳ")


# ---- tool search_textbook (định dạng đầu ra) ----


def test_tool_formats_hits_with_citation():
    fake_hits = [{"score": 0.7, "mon": "cong_nghe", "lop": "6", "heading": "Bảo quản thực phẩm", "text": "Nội dung."}]
    with patch("src.agents.knowledge_agent.tools.retrieval.search_textbook", return_value=fake_hits):
        out = search_textbook.invoke({"query": "bảo quản thực phẩm", "mon": "cong_nghe", "lop": "6"})
    assert "Nguồn 1" in out
    assert "cong_nghe" in out and "Bảo quản thực phẩm" in out


def test_tool_empty_returns_not_found():
    with patch("src.agents.knowledge_agent.tools.retrieval.search_textbook", return_value=[]):
        out = search_textbook.invoke({"query": "xyz", "mon": "toan", "lop": "9"})
    assert "Không tìm thấy" in out


def test_tool_handles_unavailable():
    with patch(
        "src.agents.knowledge_agent.tools.retrieval.search_textbook",
        side_effect=retrieval.RetrievalUnavailableError("down"),
    ):
        out = search_textbook.invoke({"query": "xyz"})
    assert "không khả dụng" in out


# ---- graph: knowledge_agent đã được đăng ký ----


def test_knowledge_agent_registered_in_graph():
    from src.agents.graph import agent

    assert "knowledge_agent" in agent.nodes

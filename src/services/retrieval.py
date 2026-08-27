"""Truy xuất tri thức SGK từ Qdrant cho `knowledge_agent` (RAG).

Hai bước: (1) nhúng câu hỏi qua embedding sidecar (BGE-m3, KHỚP không gian vector
đã index); (2) tìm top-k trong collection `edu_knowledge` (Cosine), lọc theo mon/lop.

Tri thức SGK là TOÀN CỤC (không theo trường) → KHÔNG lọc `school_id` như các tool DB.
Mọi lỗi mạng/Qdrant được nâng thành `RetrievalUnavailableError` để tool xử lý mềm,
tránh làm sập endpoint `/chat`.
"""

import httpx

from src.config import Settings, get_settings
from src.observability import logger


class RetrievalUnavailableError(Exception):
    """Kho tri thức (embedding sidecar hoặc Qdrant) tạm không khả dụng."""


# subjects.code (ví dụ "TOAN", "KHTN") KHÔNG khớp slug "mon" đã index trong Qdrant khi ingest
# SGK (ví dụ "toan", "khoa_hoc_tu_nhien") — ánh xạ thủ công cho các môn đã có RAG (xem RAG_design.md).
_SUBJECT_CODE_TO_RAG_MON = {
    "TOAN": "toan",
    "KHTN": "khoa_hoc_tu_nhien",
}


def rag_mon_slug(subject_code: str) -> str:
    """Slug "mon" dùng để lọc Qdrant — KHÁC subjects.code, xem _SUBJECT_CODE_TO_RAG_MON."""
    return _SUBJECT_CODE_TO_RAG_MON.get(subject_code, subject_code.lower())


def has_rag(subject_code: str) -> bool:
    """Môn đã ingest SGK vào Qdrant chưa — chỉ các môn nằm trong _SUBJECT_CODE_TO_RAG_MON."""
    return subject_code in _SUBJECT_CODE_TO_RAG_MON


def embed_query(text: str, settings: Settings | None = None) -> list[float]:
    """Nhúng 1 câu hỏi bằng API được cấu hình (local, openai, hoặc gemini)."""
    s = settings or get_settings()
    if s.embedding_provider == "openai" and not s.openai_api_key:
        logger.warning("rag_embedding_unavailable", error="missing OPENAI_API_KEY", provider="openai")
        raise RetrievalUnavailableError("Thiếu OPENAI_API_KEY (bắt buộc khi EMBEDDING_PROVIDER=openai)")
    if s.embedding_provider == "gemini" and not s.gemini_api_key:
        logger.warning("rag_embedding_unavailable", error="missing GEMINI_API_KEY", provider="gemini")
        raise RetrievalUnavailableError("Thiếu GEMINI_API_KEY (bắt buộc khi EMBEDDING_PROVIDER=gemini)")
    try:
        if s.embedding_provider == "openai":
            base_url = s.openai_api_base.rstrip("/")
            resp = httpx.post(
                f"{base_url}/embeddings",
                headers={"Authorization": f"Bearer {s.openai_api_key}"},
                json={"model": s.openai_embed_model, "input": text, "dimensions": s.embedding_dim},
                timeout=s.retrieval_timeout_s,
            )
            resp.raise_for_status()
            return resp.json()["data"][0]["embedding"]

        elif s.embedding_provider == "gemini":
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{s.gemini_embed_model}:embedContent"
            resp = httpx.post(
                url,
                params={"key": s.gemini_api_key},
                json={
                    "model": f"models/{s.gemini_embed_model}",
                    "content": {"parts": [{"text": text}]},
                    "outputDimensionality": s.embedding_dim,
                },
                timeout=s.retrieval_timeout_s,
            )
            resp.raise_for_status()
            return resp.json()["embedding"]["values"]

        else:
            resp = httpx.post(
                f"{s.embedding_service_url.rstrip('/')}/embed",
                json={"texts": [text]},
                timeout=s.retrieval_timeout_s,
            )
            resp.raise_for_status()
            return resp.json()["vectors"][0]

    except (httpx.HTTPError, KeyError, IndexError) as exc:
        logger.warning("rag_embedding_unavailable", error=str(exc), provider=s.embedding_provider)
        raise RetrievalUnavailableError(f"Lỗi gọi embedding service ({s.embedding_provider}): {exc}") from exc


def _build_filter(mon: str | None, lop: str | None, include_lesson_plans: bool = False) -> dict | None:
    """Dựng filter payload Qdrant theo môn/lớp (lop lưu dạng chuỗi trong payload)."""
    must = []
    must_not = []
    if mon:
        must.append({"key": "mon", "match": {"value": mon}})
    if lop:
        must.append({"key": "lop", "match": {"value": str(lop)}})
    if not include_lesson_plans:
        must_not.append({"key": "source", "match": {"value": "giao_an"}})
    res = {}
    if must:
        res["must"] = must
    if must_not:
        res["must_not"] = must_not
    return res if res else None


def search_textbook(
    query: str,
    mon: str | None = None,
    lop: str | None = None,
    include_lesson_plans: bool = False,
) -> list[dict]:
    """Tìm các đoạn SGK liên quan nhất (hoặc cả SGK + giáo án). Trả list payload kèm `score`."""
    s = get_settings()
    vector = embed_query(query, s)
    body: dict = {
        "vector": vector,
        "limit": s.retrieval_top_k,
        "with_payload": ["mon", "lop", "chuong", "heading", "source_md", "text", "source", "unit_name", "lesson_name"],
        "score_threshold": s.retrieval_score_floor,
    }
    flt = _build_filter(mon, lop, include_lesson_plans=include_lesson_plans)
    if flt:
        body["filter"] = flt
    headers = {"api-key": s.qdrant_api_key} if s.qdrant_api_key else {}
    try:
        resp = httpx.post(
            f"{s.qdrant_url.rstrip('/')}/collections/{s.qdrant_collection}/points/search",
            json=body,
            headers=headers,
            timeout=s.retrieval_timeout_s,
        )
        resp.raise_for_status()
        hits = resp.json()["result"]
    except (httpx.HTTPError, KeyError) as exc:
        logger.warning("rag_qdrant_unavailable", error=str(exc), mon=mon, lop=lop)
        raise RetrievalUnavailableError(f"Lỗi truy vấn Qdrant: {exc}") from exc

    return [{"score": h["score"], **h.get("payload", {})} for h in hits]


def search_lesson_plan(query: str, mon: str | None = None, lop: str | None = None) -> list[dict]:
    """Tìm kiếm chuyên biệt trong kho Giáo án (source = 'giao_an')."""
    s = get_settings()
    vector = embed_query(query, s)
    must = [{"key": "source", "match": {"value": "giao_an"}}]
    if mon:
        must.append({"key": "mon", "match": {"value": mon}})
    if lop:
        must.append({"key": "lop", "match": {"value": str(lop)}})
    body: dict = {
        "vector": vector,
        "limit": s.retrieval_top_k,
        "with_payload": ["mon", "lop", "chuong", "heading", "source_md", "text", "source", "unit_name", "lesson_name"],
        "score_threshold": s.retrieval_score_floor,
        "filter": {"must": must},
    }
    headers = {"api-key": s.qdrant_api_key} if s.qdrant_api_key else {}
    try:
        resp = httpx.post(
            f"{s.qdrant_url.rstrip('/')}/collections/{s.qdrant_collection}/points/search",
            json=body,
            headers=headers,
            timeout=s.retrieval_timeout_s,
        )
        resp.raise_for_status()
        hits = resp.json()["result"]
    except (httpx.HTTPError, KeyError) as exc:
        logger.warning("rag_qdrant_unavailable", error=str(exc), mon=mon, lop=lop)
        raise RetrievalUnavailableError(f"Lỗi truy vấn Qdrant: {exc}") from exc

    return [{"score": h["score"], **h.get("payload", {})} for h in hits]

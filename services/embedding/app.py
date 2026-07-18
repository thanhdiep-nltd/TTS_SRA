"""Embedding microservice (sidecar) — BGE-m3 dùng chung cho luồng RAG retrieval.

Tách riêng khỏi backend FastAPI để API nghiệp vụ giữ nhẹ (không kéo torch).
Dùng CHÍNH model + tham số như pipeline ingestion
(`pipelines/airflow/plugins/edu_pipeline/embedding.py::embed_with_local`):
`SentenceTransformer(BAAI/bge-m3).encode(..., normalize_embeddings=True)` → vector
1024 chiều, chuẩn hóa L2, KHỚP TUYỆT ĐỐI không gian vector đã index trong Qdrant.
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel, Field

_MODEL_NAME = os.getenv("LOCAL_EMBED_MODEL", "BAAI/bge-m3")
_EXPECTED_DIM = int(os.getenv("EMBEDDING_DIM", "1024"))
_BATCH_SIZE = int(os.getenv("EMBED_BATCH_SIZE", "12"))

_state: dict = {}


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Nạp model 1 lần lúc khởi động (cache trên đĩa qua HF_HOME) — tránh cold-load mỗi request."""
    from sentence_transformers import SentenceTransformer

    _state["model"] = SentenceTransformer(_MODEL_NAME)
    yield
    _state.clear()


app = FastAPI(title="Edu-Knowledge Embedding Service", version="1.0.0", lifespan=lifespan)


class EmbedRequest(BaseModel):
    texts: list[str] = Field(..., min_length=1, description="Danh sách văn bản cần nhúng.")


class EmbedResponse(BaseModel):
    model: str
    dim: int
    vectors: list[list[float]]


@app.get("/health")
async def health() -> dict:
    """Ping: 'ready' khi model đã nạp xong."""
    return {"status": "ready" if _state.get("model") is not None else "loading", "model": _MODEL_NAME}


@app.post("/embed", response_model=EmbedResponse)
async def embed(req: EmbedRequest) -> EmbedResponse:
    """Nhúng văn bản → vector chuẩn hóa L2 (khớp pipeline ingestion)."""
    model = _state["model"]
    vectors = model.encode(
        req.texts, batch_size=_BATCH_SIZE, normalize_embeddings=True, show_progress_bar=False
    )
    out = [v.tolist() for v in vectors]
    return EmbedResponse(model=_MODEL_NAME, dim=len(out[0]) if out else _EXPECTED_DIM, vectors=out)

"""Khởi tạo collection Qdrant và upsert vector + metadata (idempotent theo point ID)."""

from typing import Any

from edu_pipeline.hashing import content_point_id

_PAYLOAD_INDEXES = ("mon", "lop", "chuong")


def get_client(url: str, api_key: str = ""):
    """Tạo QdrantClient. Hỗ trợ `:memory:` cho unit test."""
    from qdrant_client import QdrantClient

    if url == ":memory:":
        return QdrantClient(location=":memory:")
    return QdrantClient(url=url, api_key=api_key or None)


def init_collection(client: Any, collection: str, dim: int) -> None:
    """Tạo collection (Cosine, `dim` chiều) + payload index nếu chưa tồn tại."""
    from qdrant_client import models

    if client.collection_exists(collection):
        return
    client.create_collection(
        collection_name=collection,
        vectors_config=models.VectorParams(size=dim, distance=models.Distance.COSINE),
    )
    for field in _PAYLOAD_INDEXES:
        client.create_payload_index(
            collection_name=collection,
            field_name=field,
            field_schema=models.PayloadSchemaType.KEYWORD,
        )


def upsert_chunks(client: Any, collection: str, chunks: list[dict]) -> int:
    """Upsert các chunk {text, vector, payload}. ID = hash(text) → chạy lại không trùng.

    Trả về số point đã upsert.
    """
    from qdrant_client import models

    points = [
        models.PointStruct(
            id=content_point_id(chunk["text"]),
            vector=chunk["vector"],
            payload=chunk["payload"],
        )
        for chunk in chunks
    ]
    if points:
        client.upsert(collection_name=collection, points=points)
    return len(points)

"""Test init collection + upsert idempotent với Qdrant in-memory."""

import pytest

pytest.importorskip("qdrant_client")

from edu_pipeline import qdrant_io  # noqa: E402

_COLLECTION = "test_edu"
_DIM = 8


def _chunk(text: str) -> dict:
    return {"text": text, "vector": [0.1] * _DIM, "payload": {"mon": "toan", "text": text}}


def test_init_collection_idempotent():
    client = qdrant_io.get_client(":memory:")
    qdrant_io.init_collection(client, _COLLECTION, _DIM)
    qdrant_io.init_collection(client, _COLLECTION, _DIM)  # gọi lần 2 không lỗi
    assert client.collection_exists(_COLLECTION)


def test_upsert_is_idempotent():
    client = qdrant_io.get_client(":memory:")
    qdrant_io.init_collection(client, _COLLECTION, _DIM)
    chunks = [_chunk("Định lý Pytago")]

    qdrant_io.upsert_chunks(client, _COLLECTION, chunks)
    qdrant_io.upsert_chunks(client, _COLLECTION, chunks)  # cùng text -> cùng ID

    assert client.count(_COLLECTION).count == 1


def test_distinct_texts_distinct_points():
    client = qdrant_io.get_client(":memory:")
    qdrant_io.init_collection(client, _COLLECTION, _DIM)
    qdrant_io.upsert_chunks(client, _COLLECTION, [_chunk("Bài 1"), _chunk("Bài 2")])
    assert client.count(_COLLECTION).count == 2

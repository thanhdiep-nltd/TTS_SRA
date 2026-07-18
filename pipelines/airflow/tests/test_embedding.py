"""Test embedding theo lô với OpenAI client được mock (không gọi API thật)."""

import pytest

pytest.importorskip("openai")

from edu_pipeline import embedding  # noqa: E402


class _FakeEmbeddings:
    def __init__(self, recorder: list):
        self._recorder = recorder

    def create(self, model: str, input: list[str]):
        self._recorder.append(input)
        data = [type("E", (), {"embedding": [float(len(t))]}) for t in input]
        return type("R", (), {"data": data})


class _FakeClient:
    def __init__(self, recorder: list):
        self.embeddings = _FakeEmbeddings(recorder)


def test_embed_with_openai_preserves_order_and_batches(monkeypatch):
    recorder: list = []
    monkeypatch.setattr("openai.OpenAI", lambda **kwargs: _FakeClient(recorder))
    # _BATCH_SIZE=100 -> 250 phần tử chia thành 3 lô
    texts = [f"t{i}" for i in range(250)]

    vectors = embedding.embed_with_openai(texts, "key")

    assert len(vectors) == 250
    assert len(recorder) == 3  # 100 + 100 + 50
    assert vectors[0] == [float(len("t0"))]


class _FakeGeminiResp:
    status_code = 200

    def __init__(self, n: int, dim: int):
        self._n, self._dim = n, dim

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return {"embeddings": [{"values": [0.0] * self._dim} for _ in range(self._n)]}


class _FakeST:
    """Giả lập SentenceTransformer: trả vector dim chiều, chuẩn hóa bỏ qua."""

    def __init__(self, name: str):
        self.name = name

    def encode(self, texts, batch_size, normalize_embeddings, show_progress_bar):
        import numpy as np

        return np.array([[1.0 / 1024] * 1024 for _ in texts])


def test_embed_with_local_returns_correct_dim(monkeypatch):
    import sys
    import types

    fake_mod = types.ModuleType("sentence_transformers")
    fake_mod.SentenceTransformer = _FakeST
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_mod)

    vectors = embedding.embed_with_local(["a", "b", "c"], "BAAI/bge-m3", 1024)

    assert len(vectors) == 3 and len(vectors[0]) == 1024


def test_embed_with_local_raises_on_dim_mismatch(monkeypatch):
    import sys
    import types

    fake_mod = types.ModuleType("sentence_transformers")
    fake_mod.SentenceTransformer = _FakeST
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_mod)

    with pytest.raises(ValueError, match="khác EMBEDDING_DIM"):
        embedding.embed_with_local(["a"], "BAAI/bge-m3", 768)


def test_embed_with_gemini_batches_and_dim(monkeypatch):
    calls: list = []

    def fake_post(url, params, json, timeout):
        calls.append(json)
        return _FakeGeminiResp(len(json["requests"]), 768)

    monkeypatch.setattr("httpx.post", fake_post)
    monkeypatch.setattr("time.sleep", lambda *_: None)  # bỏ throttle khi test
    texts = [f"t{i}" for i in range(45)]

    vectors = embedding.embed_with_gemini(texts, "key", "gemini-embedding-001", 768)

    assert len(vectors) == 45 and len(vectors[0]) == 768
    assert len(calls) == 5  # _GEMINI_BATCH=10 -> 10*4 + 5
    assert calls[0]["requests"][0]["outputDimensionality"] == 768

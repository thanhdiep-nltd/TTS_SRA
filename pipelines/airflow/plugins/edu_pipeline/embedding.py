"""Nhúng ngữ nghĩa: OpenAI (text-embedding-3-small) hoặc Gemini (gemini-embedding-001).

Xử lý theo lô (batch) để chia khối lượng lớn thành nhiều chunk, tránh tràn giới hạn API.
"""

_BATCH_SIZE = 100
_GEMINI_BATCH = 10  # free tier 30k TPM -> lô nhỏ
_GEMINI_THROTTLE = 12  # giây giữa các lô để giữ dưới TPM (time không quan trọng)
_GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"


def _batches(items: list, size: int = _BATCH_SIZE):
    """Chia danh sách thành các lô <= size phần tử."""
    for start in range(0, len(items), size):
        yield items[start : start + size]


def embed_with_local(texts: list[str], model_name: str, dim: int, batch_size: int = 12) -> list[list[float]]:
    """Embed cục bộ bằng sentence-transformers (BGE-m3) — $0, không quota, chạy offline trên CPU.

    Vector được chuẩn hóa L2 (hợp với Cosine). Model nạp 1 lần/tiến trình; cache trên đĩa.
    """
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(model_name)
    vectors = model.encode(texts, batch_size=batch_size, normalize_embeddings=True, show_progress_bar=False)
    out = [v.tolist() for v in vectors]
    if out and len(out[0]) != dim:
        raise ValueError(f"Model {model_name} trả {len(out[0])} chiều, khác EMBEDDING_DIM={dim}")
    return out


def embed_with_openai(texts: list[str], api_key: str, model: str = "text-embedding-3-small") -> list[list[float]]:
    """Embed theo lô bằng OpenAI; giữ nguyên thứ tự đầu vào."""
    from openai import OpenAI

    client = OpenAI(api_key=api_key, max_retries=8)
    vectors: list[list[float]] = []
    for batch in _batches(texts):
        resp = client.embeddings.create(model=model, input=batch)
        vectors.extend(item.embedding for item in resp.data)
    return vectors


def _gemini_batch(url: str, api_key: str, reqs: list[dict], retries: int = 8) -> list[list[float]]:
    """Gửi 1 lô batchEmbedContents; backoff khi 429/503 (free tier RPM/TPM thấp)."""
    import time

    import httpx

    for attempt in range(retries + 1):
        resp = httpx.post(url, params={"key": api_key}, json={"requests": reqs}, timeout=httpx.Timeout(180.0))
        if resp.status_code in (429, 503) and attempt < retries:
            time.sleep(min(70, 8 * 2**attempt))
            continue
        resp.raise_for_status()
        return [e["values"] for e in resp.json()["embeddings"]]
    return []


def embed_with_gemini(texts: list[str], api_key: str, model: str, dim: int) -> list[list[float]]:
    """Embed theo lô nhỏ bằng Gemini batchEmbedContents (REST) + throttle; cắt vector về `dim` chiều."""
    import time

    name = f"models/{model}"
    url = f"{_GEMINI_BASE}/{name}:batchEmbedContents"
    vectors: list[list[float]] = []
    for batch in _batches(texts, _GEMINI_BATCH):
        reqs = [
            {"model": name, "content": {"parts": [{"text": t}]}, "outputDimensionality": dim}
            for t in batch
        ]
        vectors.extend(_gemini_batch(url, api_key, reqs))
        time.sleep(_GEMINI_THROTTLE)  # giãn nhịp giữ dưới TPM free tier
    return vectors

"""Re-embed toàn bộ collection Qdrant hiện có (BGE-m3 1024D) sang OpenAI text-embedding-3-small (1536D).

Đọc text+payload từ collection nguồn qua scroll API (không cần OCR/Airflow lại), nhúng lại
bằng OpenAI, rồi upsert vào collection ĐÍCH mới (giữ collection cũ nguyên vẹn để rollback).
Idempotent theo điểm id (giữ nguyên id khi re-run không tốn thêm).

Ví dụ:
  python scripts/reembed_openai.py --dst-collection edu_knowledge_openai
"""

import argparse
import sys

import httpx
import tiktoken
from openai import OpenAI

from src.config import get_settings

_TIMEOUT = httpx.Timeout(120.0)
_EMBED_BATCH = 100
_MAX_TOKENS = 8000  # giới hạn OpenAI là 8192 token/input, chừa biên an toàn


def _truncate(text: str, encoding: tiktoken.Encoding) -> str:
    """Cắt text về tối đa _MAX_TOKENS token (OpenAI từ chối input >8192 token)."""
    tokens = encoding.encode(text)
    if len(tokens) <= _MAX_TOKENS:
        return text
    return encoding.decode(tokens[:_MAX_TOKENS])


def _headers(key: str) -> dict:
    return {"api-key": key} if key else {}


def ensure_collection(url: str, key: str, coll: str, dim: int) -> None:
    """Tạo collection đích (Cosine, `dim` chiều) nếu chưa có — idempotent."""
    existing = httpx.get(f"{url}/collections/{coll}", headers=_headers(key), timeout=_TIMEOUT)
    if existing.status_code == 200:
        return
    body = {"vectors": {"size": dim, "distance": "Cosine"}}
    r = httpx.put(f"{url}/collections/{coll}", headers=_headers(key), json=body, timeout=_TIMEOUT)
    r.raise_for_status()


def copy_payload_indexes(url: str, key: str, src_coll: str, dst_coll: str) -> list[str]:
    """Tái tạo payload index (mon/lop/chuong...) ở collection đích — bắt buộc để filter hoạt động."""
    r = httpx.get(f"{url}/collections/{src_coll}", headers=_headers(key), timeout=_TIMEOUT)
    r.raise_for_status()
    schema = r.json()["result"].get("payload_schema", {})
    created = []
    for field, info in schema.items():
        body = {"field_name": field, "field_schema": info["data_type"]}
        resp = httpx.put(
            f"{url}/collections/{dst_coll}/index?wait=true", headers=_headers(key), json=body, timeout=_TIMEOUT
        )
        resp.raise_for_status()
        created.append(f"{field}:{info['data_type']}")
    return created


def scroll_points(url: str, key: str, coll: str, offset, limit: int) -> tuple[list, object]:
    """Lấy 1 trang point kèm payload (KHÔNG cần vector cũ — sẽ nhúng lại)."""
    body = {"limit": limit, "with_payload": True, "with_vector": False, "offset": offset}
    r = httpx.post(f"{url}/collections/{coll}/points/scroll", headers=_headers(key), json=body, timeout=_TIMEOUT)
    r.raise_for_status()
    res = r.json()["result"]
    return res["points"], res.get("next_page_offset")


def embed_batch(client: OpenAI, texts: list[str], model: str, dim: int) -> list[list[float]]:
    """Nhúng 1 lô text bằng OpenAI, giữ nguyên thứ tự. `dim` cắt vector kiểu Matryoshka (model 3-large/3-small)."""
    resp = client.embeddings.create(model=model, input=texts, dimensions=dim)
    return [item.embedding for item in resp.data]


def upsert_points(url: str, key: str, coll: str, ids: list, vectors: list, payloads: list) -> None:
    """Upsert 1 lô point (id giữ nguyên từ collection nguồn, payload không đổi)."""
    points = [{"id": i, "vector": v, "payload": p} for i, v, p in zip(ids, vectors, payloads)]
    r = httpx.put(f"{url}/collections/{coll}/points?wait=true", headers=_headers(key), json={"points": points}, timeout=_TIMEOUT)
    r.raise_for_status()


def count(url: str, key: str, coll: str) -> int:
    r = httpx.get(f"{url}/collections/{coll}", headers=_headers(key), timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()["result"]["points_count"]


def reembed(args: argparse.Namespace) -> int:
    """Chạy toàn bộ luồng re-embed; trả số point đã chuyển."""
    s = get_settings()
    if not s.openai_api_key:
        print("Thiếu OPENAI_API_KEY trong .env", file=sys.stderr)
        return 1

    client = OpenAI(api_key=s.openai_api_key, base_url=s.openai_api_base, max_retries=8)
    encoding = tiktoken.encoding_for_model(args.model)
    src_total = count(s.qdrant_url, s.qdrant_api_key, args.src_collection)
    print(f"[src] {args.src_collection}: points={src_total}")

    ensure_collection(s.qdrant_url, s.qdrant_api_key, args.dst_collection, args.dim)
    idx = copy_payload_indexes(s.qdrant_url, s.qdrant_api_key, args.src_collection, args.dst_collection)
    print(f"[dst] payload index: {idx or '(không có)'}")

    moved, offset = 0, None
    while True:
        points, offset = scroll_points(s.qdrant_url, s.qdrant_api_key, args.src_collection, offset, args.batch)
        if not points:
            break
        ids = [p["id"] for p in points]
        payloads = [p.get("payload", {}) for p in points]
        texts = [_truncate(p["text"], encoding) for p in payloads]
        vectors = embed_batch(client, texts, args.model, args.dim)
        upsert_points(s.qdrant_url, s.qdrant_api_key, args.dst_collection, ids, vectors, payloads)
        moved += len(points)
        print(f"  ... đã re-embed {moved}/{src_total}", flush=True)
        if offset is None:
            break

    dst_total = count(s.qdrant_url, s.qdrant_api_key, args.dst_collection)
    print(f"[dst] {args.dst_collection}: points={dst_total} (đã upsert {moved})")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Re-embed Qdrant collection sang OpenAI text-embedding-3-small")
    p.add_argument("--src-collection", default="edu_knowledge")
    p.add_argument("--dst-collection", default="edu_knowledge_openai")
    p.add_argument("--model", default="text-embedding-3-small")
    p.add_argument("--dim", type=int, default=1536)
    p.add_argument("--batch", type=int, default=_EMBED_BATCH)
    return reembed(p.parse_args())


if __name__ == "__main__":
    sys.exit(main())

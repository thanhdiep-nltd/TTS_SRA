"""Di chuyển một collection Qdrant từ nguồn (local) sang đích (cloud).

Đọc toàn bộ point (id + vector + payload) từ Qdrant nguồn qua scroll API, tạo
collection ở đích với CÙNG số chiều/độ đo, rồi upsert theo lô. Idempotent: point ID
giữ nguyên nên chạy lại không trùng. Dùng httpx REST (không cần qdrant-client).

Ví dụ:
  python scripts/migrate_qdrant.py \
    --src-url http://localhost:6333 --src-key "$LOCAL_KEY" \
    --dst-url https://xxx.cloud.qdrant.io:6333 --dst-key "$CLOUD_KEY" \
    --collection edu_knowledge
"""

import argparse
import sys

import httpx

_TIMEOUT = httpx.Timeout(120.0)


def _headers(key: str) -> dict:
    return {"api-key": key} if key else {}


def get_vectors_config(url: str, key: str, coll: str) -> dict:
    """Lấy cấu hình vector (size, distance) của collection nguồn."""
    r = httpx.get(f"{url}/collections/{coll}", headers=_headers(key), timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()["result"]["config"]["params"]["vectors"]


def ensure_collection(url: str, key: str, coll: str, vectors_cfg: dict) -> None:
    """Tạo collection đích với cùng size/distance nếu CHƯA có (idempotent — re-run an toàn)."""
    existing = httpx.get(f"{url}/collections/{coll}", headers=_headers(key), timeout=_TIMEOUT)
    if existing.status_code == 200:
        return  # đã tồn tại — giữ nguyên, chỉ upsert thêm
    body = {"vectors": {"size": vectors_cfg["size"], "distance": vectors_cfg["distance"]}}
    r = httpx.put(f"{url}/collections/{coll}", headers=_headers(key), json=body, timeout=_TIMEOUT)
    r.raise_for_status()


def copy_payload_indexes(src_url: str, src_key: str, dst_url: str, dst_key: str, coll: str) -> list[str]:
    """Tái tạo payload index (mon/lop/chuong...) ở đích — BẮT BUỘC để filter hoạt động trên cloud."""
    r = httpx.get(f"{src_url}/collections/{coll}", headers=_headers(src_key), timeout=_TIMEOUT)
    r.raise_for_status()
    schema = r.json()["result"].get("payload_schema", {})
    created = []
    for field, info in schema.items():
        body = {"field_name": field, "field_schema": info["data_type"]}
        resp = httpx.put(
            f"{dst_url}/collections/{coll}/index?wait=true", headers=_headers(dst_key), json=body, timeout=_TIMEOUT
        )
        resp.raise_for_status()
        created.append(f"{field}:{info['data_type']}")
    return created


def scroll_points(url: str, key: str, coll: str, offset, limit: int) -> tuple[list, object]:
    """Lấy 1 trang point kèm vector + payload; trả (points, next_offset)."""
    body = {"limit": limit, "with_payload": True, "with_vector": True, "offset": offset}
    r = httpx.post(f"{url}/collections/{coll}/points/scroll", headers=_headers(key), json=body, timeout=_TIMEOUT)
    r.raise_for_status()
    res = r.json()["result"]
    return res["points"], res.get("next_page_offset")


def upsert_points(url: str, key: str, coll: str, points: list) -> None:
    """Upsert 1 lô point (giữ nguyên id/vector/payload)."""
    payload = {"points": [{"id": p["id"], "vector": p["vector"], "payload": p.get("payload", {})} for p in points]}
    r = httpx.put(f"{url}/collections/{coll}/points?wait=true", headers=_headers(key), json=payload, timeout=_TIMEOUT)
    r.raise_for_status()


def count(url: str, key: str, coll: str) -> int:
    """Đếm số point trong collection."""
    r = httpx.get(f"{url}/collections/{coll}", headers=_headers(key), timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()["result"]["points_count"]


def migrate(args: argparse.Namespace) -> int:
    """Chạy toàn bộ luồng migrate; trả số point đã chuyển."""
    cfg = get_vectors_config(args.src_url, args.src_key, args.collection)
    print(f"[src] {args.collection}: dim={cfg['size']} distance={cfg['distance']} points={count(args.src_url, args.src_key, args.collection)}")
    ensure_collection(args.dst_url, args.dst_key, args.collection, cfg)
    idx = copy_payload_indexes(args.src_url, args.src_key, args.dst_url, args.dst_key, args.collection)
    print(f"[dst] payload index: {idx or '(không có)'}")
    moved, offset = 0, None
    while True:
        points, offset = scroll_points(args.src_url, args.src_key, args.collection, offset, args.batch)
        if not points:
            break
        upsert_points(args.dst_url, args.dst_key, args.collection, points)
        moved += len(points)
        print(f"  ... đã chuyển {moved} point", flush=True)
        if offset is None:
            break
    dst_total = count(args.dst_url, args.dst_key, args.collection)
    print(f"[dst] {args.collection}: points={dst_total} (đã upsert {moved})")
    return moved


def main() -> int:
    p = argparse.ArgumentParser(description="Migrate Qdrant collection (local -> cloud)")
    p.add_argument("--src-url", required=True)
    p.add_argument("--src-key", default="")
    p.add_argument("--dst-url", required=True)
    p.add_argument("--dst-key", default="")
    p.add_argument("--collection", default="edu_knowledge")
    p.add_argument("--batch", type=int, default=256)
    migrate(p.parse_args())
    return 0


if __name__ == "__main__":
    sys.exit(main())

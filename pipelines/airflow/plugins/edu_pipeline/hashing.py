"""Sinh ID điểm (point ID) cho Qdrant từ nội dung text — đảm bảo idempotent."""

import hashlib
import uuid


def content_point_id(text: str) -> str:
    """Trả về UUID xác định (deterministic) từ SHA-256 của text đã chuẩn hóa.

    Cùng một đoạn text luôn cho cùng ID → upsert lại không tạo bản trùng.
    Qdrant yêu cầu point ID là UUID hoặc số nguyên, nên ta gói hash vào UUIDv5.
    """
    normalized = " ".join(text.split())
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return str(uuid.UUID(digest[:32]))

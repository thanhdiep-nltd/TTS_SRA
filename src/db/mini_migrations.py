"""Mini-migrations idempotent — dev KHÔNG dùng Alembic, data dev sửa thẳng SQL.

Thay thế alembic cho các thay đổi schema nhỏ: chạy lúc startup (src/main.py lifespan),
mỗi câu lệnh là ``ALTER TABLE ... ADD COLUMN IF NOT EXISTS`` (Postgres) và được bọc
try/except riêng để không crash nếu cột đã có hoặc bảng chưa tồn tại.
"""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# (câu lệnh, mô tả) — chạy theo thứ tự, idempotent với Postgres.
_MINI_MIGRATIONS: list[tuple[str, str]] = [
    (
        "ALTER TABLE public.curriculum_units ADD COLUMN IF NOT EXISTS summary TEXT",
        "curriculum_units.summary (tóm tắt nội dung chương/bài)",
    ),
    (
        "ALTER TABLE public.curriculum_units ADD COLUMN IF NOT EXISTS keywords TEXT[]",
        "curriculum_units.keywords (từ khóa/khái niệm chính)",
    ),
    (
        "ALTER TABLE public.curriculum_units ADD COLUMN IF NOT EXISTS sections JSONB",
        "curriculum_units.sections (mục con trong bài theo thứ tự)",
    ),
    (
        "ALTER TABLE public.curriculum_ingest_jobs ADD COLUMN IF NOT EXISTS enrich BOOLEAN NOT NULL DEFAULT TRUE",
        "curriculum_ingest_jobs.enrich (cờ làm giàu nội dung khi nạp sách)",
    ),
]


def apply_mini_migrations(db: Session) -> int:
    """Chạy các mini-migration; trả số câu áp dụng thành công (lỗi 1 câu không crash)."""
    applied = 0
    for statement, label in _MINI_MIGRATIONS:
        try:
            db.execute(text(statement))
            db.commit()
            applied += 1
            logger.info("Mini-migration OK: %s", label)
        except Exception as exc:  # noqa: BLE001 — bảng/cột chưa tồn tại ở DB mới thì bỏ qua
            db.rollback()
            logger.warning("Mini-migration bỏ qua '%s': %s", label, exc)
    return applied

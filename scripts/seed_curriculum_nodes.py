"""Seed catalog chuẩn chương trình (curriculum_units) — Toán Cánh diều 6–9.

CLI mỏng — logic dùng chung ở src/services/curriculum_catalog.py (API admin cũng dùng).
Chạy: python scripts/seed_curriculum_nodes.py
"""

from __future__ import annotations

import sys
from pathlib import Path

if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.db.session import SessionLocal  # noqa: E402
from src.services.curriculum_catalog import (  # noqa: E402
    build_unit_specs,
    deactivate_placeholder_units,
    load_catalog,
    resolve_subject_ids,
    upsert_units,
)


def main() -> None:
    """Seed catalog Toán Cánh diều 6–9 vào curriculum_units."""
    data = load_catalog()
    grades = [int(grade["grade"]) for grade in data["grades"]]
    db = SessionLocal()
    try:
        subject_ids = resolve_subject_ids(db, data["subject_code"], grades)
        if not subject_ids:
            print("Không tìm thấy s360.dim_subject (cần chạy mock generator trước?) — bỏ qua.")
            return
        specs = build_unit_specs(data, subject_ids)
        inserted, updated = upsert_units(db, specs)
        hidden = deactivate_placeholder_units(db)
        print(
            f"curriculum_units: {len(specs)} dòng — inserted={inserted}, updated={updated}; "
            f"ẩn {hidden} unit placeholder cũ (UNIT_%)."
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()

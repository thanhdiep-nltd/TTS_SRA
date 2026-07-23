import pytest
from sqlalchemy import text

from src.db.session import SessionLocal
from src.services.entity_linker import resolve_entities
from src.services.metadata_indexer import sync_school_metadata


def setup_mock_dimensions():
    with SessionLocal() as db:
        # Seed test school year
        db.execute(
            text("""
            INSERT INTO s360.dim_school_year (id, code, fullname)
            VALUES (2025, '2025_2026', 'Năm học 2025 - 2026')
            ON CONFLICT (id) DO NOTHING;
        """)
        )

        # Seed test homeroom class
        db.execute(
            text("""
            INSERT INTO s360.dim_homeroom_class (id, so_school_id, school_year_id, grade_id, code, fullname)
            VALUES (1, 1, 2025, 7, '7A1', '7A1')
            ON CONFLICT (id) DO NOTHING;
        """)
        )

        # Seed test subject
        db.execute(
            text("""
            INSERT INTO s360.dim_subject (id, code, name)
            VALUES (16, 'TOAN_7', 'Toán học')
            ON CONFLICT (id) DO NOTHING;
        """)
        )

        # Seed test exam
        db.execute(
            text("""
            INSERT INTO s360.dim_exam (id, school_year_id, subject_id, grade_id, exam_code, exam_name, moet_semester_index)
            VALUES (29, 2025, 16, 7, 'GK1_TOAN_7', 'Kiểm tra giữa kỳ 1', 1)
            ON CONFLICT (id) DO NOTHING;
        """)
        )

        # Seed test gradebook to link exam to school 1
        db.execute(
            text("""
            INSERT INTO s360.fact_gradebooks (id, so_school_id, school_year_id, semester_index, student_code, homeroom_class_id, subject_id, so_exam_id, final_grade)
            VALUES (1, 1, 2025, 1, 'HS250001', 1, 16, 29, 8.5)
            ON CONFLICT (id) DO NOTHING;
        """)
        )

        db.commit()


def test_metadata_indexer_and_hybrid_entity_linker():
    setup_mock_dimensions()

    # 1. Sync Metadata
    count = sync_school_metadata(1)
    assert count > 0

    # 2. Test Entity Linker for standard query
    res = resolve_entities("Truy vấn danh sách điểm môn Toán giữa kỳ 1 của các học sinh thuộc lớp 7A1", 1)

    assert res.formatted_prompt_context != ""
    assert "EXACT VALUES IN DB" in res.formatted_prompt_context
    assert "homeroom_class_id = 1" in res.formatted_prompt_context
    assert "subject_id = 107" in res.formatted_prompt_context or "subject_id = 16" in res.formatted_prompt_context

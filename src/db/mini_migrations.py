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
    (
        """CREATE TABLE IF NOT EXISTS public.lms_question_bank (
            question_id BIGINT PRIMARY KEY,
            assignment_id BIGINT NOT NULL,
            so_school_id INTEGER NOT NULL,
            subject_id INTEGER NOT NULL,
            unit_id BIGINT REFERENCES public.curriculum_units(id),
            bloom_level SMALLINT DEFAULT 3,
            question_type VARCHAR(20) DEFAULT 'MCQ',
            item_weight NUMERIC(5,2),
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )""",
        "lms_question_bank (danh mục câu hỏi LMS item-level)",
    ),
    (
        "ALTER TABLE public.lms_question_bank ADD COLUMN IF NOT EXISTS lesson_id BIGINT REFERENCES public.curriculum_units(id)",
        "lms_question_bank.lesson_id (bài con trong chương — khớp pipeline test câu hỏi)",
    ),
    (
        "CREATE INDEX IF NOT EXISTS idx_lqb_lesson ON public.lms_question_bank(lesson_id)",
        "lms_question_bank (lesson_id) index",
    ),
    (
        "ALTER TABLE public.lms_question_bank ADD COLUMN IF NOT EXISTS question_text TEXT",
        "lms_question_bank.question_text (nội dung đề bài câu hỏi)",
    ),
    (
        "CREATE INDEX IF NOT EXISTS idx_lqb_subject ON public.lms_question_bank(subject_id, unit_id)",
        "lms_question_bank (subject_id, unit_id) index",
    ),
    (
        """CREATE TABLE IF NOT EXISTS public.lms_question_unit (
            question_id BIGINT NOT NULL REFERENCES public.lms_question_bank(question_id) ON DELETE CASCADE,
            unit_id     BIGINT NOT NULL REFERENCES public.curriculum_units(id),
            weight      NUMERIC(5,3) NOT NULL DEFAULT 1.0 CHECK (weight > 0),
            PRIMARY KEY (question_id, unit_id)
        )""",
        "lms_question_unit (map câu LMS ↔ nhiều bài con, có trọng số; parent_id = chương)",
    ),
    (
        "CREATE INDEX IF NOT EXISTS idx_lqu_unit ON public.lms_question_unit(unit_id)",
        "lms_question_unit (unit_id) index",
    ),
    (
        """CREATE TABLE IF NOT EXISTS public.lms_question_response (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            so_school_id INTEGER NOT NULL,
            student_code VARCHAR(50) NOT NULL,
            assignment_id BIGINT NOT NULL,
            question_id BIGINT NOT NULL,
            unit_id BIGINT REFERENCES public.curriculum_units(id),
            bloom_level SMALLINT NOT NULL DEFAULT 3,
            question_type VARCHAR(20) DEFAULT 'MCQ',
            attempt_number SMALLINT DEFAULT 1,
            is_best_attempt BOOLEAN DEFAULT TRUE,
            is_correct BOOLEAN NOT NULL,
            score_received NUMERIC(5,2) NOT NULL,
            max_score NUMERIC(5,2) NOT NULL,
            response_time_seconds INTEGER,
            response_payload JSONB,
            integrity_flag SMALLINT DEFAULT 0,
            attempt_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )""",
        "lms_question_response (item-response từng câu học sinh)",
    ),
    (
        "CREATE INDEX IF NOT EXISTS idx_lqr_calc ON public.lms_question_response(student_code, unit_id, is_best_attempt, integrity_flag)",
        "lms_question_response (student, unit, best_attempt, integrity) index",
    ),
    (
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_lqr_attempt ON public.lms_question_response(student_code, assignment_id, question_id, attempt_number)",
        "lms_question_response unique (student, assignment, question, attempt)",
    ),
    (
        """CREATE TABLE IF NOT EXISTS public.student_unit_mastery (
            student_code VARCHAR(50) NOT NULL,
            subject_id INTEGER NOT NULL,
            so_school_id INTEGER NOT NULL,
            unit_id BIGINT NOT NULL REFERENCES public.curriculum_units(id),
            semester_index INTEGER NOT NULL,
            week_number SMALLINT DEFAULT 0 NOT NULL,
            raw_mastery NUMERIC(5,4),
            n_items INT DEFAULT 0,
            n_correct INT DEFAULT 0,
            coverage NUMERIC(4,3) DEFAULT 0,
            lm_weight NUMERIC(3,2),
            exam_weight NUMERIC(3,2),
            adjusted_mastery NUMERIC(5,4),
            confidence SMALLINT DEFAULT 1,
            evidence_source VARCHAR(20),
            integrity_status VARCHAR(20),
            evidence_detail JSONB,
            detected_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT uq_sum_mastery_week UNIQUE (so_school_id, student_code, subject_id, unit_id, semester_index, week_number)
        )""",
        "student_unit_mastery (bảng tổng hợp mastery theo chương & tuần)",
    ),
    (
        "ALTER TABLE public.student_unit_mastery ADD COLUMN IF NOT EXISTS week_number SMALLINT DEFAULT 0 NOT NULL",
        "student_unit_mastery.week_number (mặc định 0 = Mới nhất)",
    ),
    (
        "ALTER TABLE public.student_unit_mastery DROP CONSTRAINT IF EXISTS uq_sum_mastery",
        "student_unit_mastery drop legacy 5-col constraint uq_sum_mastery",
    ),
    (
        "ALTER TABLE public.student_unit_mastery ADD CONSTRAINT uq_sum_mastery_week UNIQUE (so_school_id, student_code, subject_id, unit_id, semester_index, week_number)",
        "student_unit_mastery add 6-col constraint uq_sum_mastery_week",
    ),
    (
        "CREATE INDEX IF NOT EXISTS idx_sum_std ON public.student_unit_mastery(student_code, subject_id, unit_id)",
        "student_unit_mastery (student, subject, unit) index",
    ),
    (
        "CREATE INDEX IF NOT EXISTS idx_sum_std_week ON public.student_unit_mastery(student_code, subject_id, unit_id, week_number)",
        "student_unit_mastery (student, subject, unit, week) index",
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

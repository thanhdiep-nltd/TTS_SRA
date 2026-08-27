"""Migration: Thêm teaching_schedules và trường school_year_id, is_locked vào curriculum_books."""

import sys
from pathlib import Path

if sys.platform.startswith("win"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from src.db.session import engine


def run_migration() -> None:
    print(f"[INFO] Running migration on {engine.url}...")
    with engine.begin() as conn:
        # 1. Update curriculum_books
        print(" -> Updating public.curriculum_books (school_year_id, is_locked)...")
        conn.execute(
            text("""
            ALTER TABLE public.curriculum_books 
                ADD COLUMN IF NOT EXISTS school_year_id INTEGER,
                ADD COLUMN IF NOT EXISTS is_locked BOOLEAN NOT NULL DEFAULT FALSE;
            
            CREATE INDEX IF NOT EXISTS idx_curri_book_school_year ON public.curriculum_books(school_year_id);
        """)
        )

        # 2. Create teaching_schedules table
        print(" -> Creating public.teaching_schedules table...")
        conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS public.teaching_schedules (
                id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                school_year_id  INTEGER NOT NULL,
                subject_id      INTEGER NOT NULL,
                grade_number    SMALLINT NOT NULL CHECK (grade_number BETWEEN 1 AND 12),
                semester_number SMALLINT NOT NULL CHECK (semester_number IN (1, 2)),
                week_number     SMALLINT NOT NULL CHECK (week_number BETWEEN 1 AND 52),
                unit_id         BIGINT REFERENCES public.curriculum_units(id) ON DELETE SET NULL,
                topic           VARCHAR(255),
                num_periods     SMALLINT NOT NULL DEFAULT 2 CHECK (num_periods > 0),
                notes           TEXT,
                created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                CONSTRAINT uq_teaching_schedule UNIQUE (school_year_id, subject_id, grade_number, semester_number, week_number, unit_id)
            );

            CREATE INDEX IF NOT EXISTS idx_ts_lookup ON public.teaching_schedules(school_year_id, subject_id, grade_number, week_number);
            CREATE INDEX IF NOT EXISTS idx_ts_unit   ON public.teaching_schedules(unit_id);
        """)
        )

    print("[SUCCESS] Migration completed successfully!")


if __name__ == "__main__":
    run_migration()

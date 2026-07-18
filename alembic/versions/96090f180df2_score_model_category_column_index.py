"""score model: category + column_index

Revision ID: 96090f180df2
Revises: 5b1094a3ac09
Create Date: 2026-06-14 02:16:09.831787

Chuyển scores từ score_type (enum 6 giá trị) sang score_category (ORAL/REGULAR/
MIDTERM/FINAL) + column_index, để chứa Miệng×3, TX×4, GK×2, CK×1. Cập nhật
calc_subject_average theo công thức có hệ số mới và dựng lại các view đo lường.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "96090f180df2"
down_revision: Union[str, Sequence[str], None] = "5b1094a3ac09"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CATEGORY_ENUM = sa.Enum("ORAL", "REGULAR", "MIDTERM", "FINAL", name="score_category_enum", create_type=False)

_CALC_FN = """
CREATE OR REPLACE FUNCTION calc_subject_average(
    p_student_id UUID, p_subject_id UUID, p_semester_id UUID
) RETURNS NUMERIC(4,2) AS $$
DECLARE
    v_num NUMERIC := 0;
    v_den INT := 0;
BEGIN
    SELECT
        COALESCE(SUM(CASE score_category
            WHEN 'ORAL' THEN value WHEN 'REGULAR' THEN value
            WHEN 'MIDTERM' THEN 2*value WHEN 'FINAL' THEN 3*value END), 0),
        COALESCE(SUM(CASE score_category
            WHEN 'ORAL' THEN 1 WHEN 'REGULAR' THEN 1
            WHEN 'MIDTERM' THEN 2 WHEN 'FINAL' THEN 3 END), 0)
      INTO v_num, v_den
      FROM scores
     WHERE student_id = p_student_id AND subject_id = p_subject_id
       AND semester_id = p_semester_id AND status = 'APPROVED';
    IF v_den = 0 THEN RETURN NULL; END IF;
    RETURN ROUND(v_num / v_den, 2);
END;
$$ LANGUAGE plpgsql;
"""

_MV = """
CREATE MATERIALIZED VIEW mv_exam_difficulty AS
SELECT s.subject_id, s.semester_id, s.score_category, c.grade_id,
       COUNT(*) AS n,
       ROUND(AVG(s.value), 2) AS mean_score,
       ROUND(COALESCE(STDDEV_SAMP(s.value), 0), 2) AS stddev_score,
       ROUND(AVG((s.value < 5.0)::int)::numeric, 4) AS pct_below_5,
       ROUND(AVG(s.value) / 10.0, 4) AS facility_index
FROM scores s JOIN classes c ON c.id = s.class_id
WHERE s.status = 'APPROVED' AND s.score_category IN ('MIDTERM', 'FINAL')
GROUP BY s.subject_id, s.semester_id, s.score_category, c.grade_id;
"""

_VIEW = """
CREATE VIEW v_normalized_scores AS
SELECT s.id AS score_id, s.student_id, s.subject_id, s.semester_id, s.class_id, c.grade_id,
       s.score_category, s.column_index, s.value AS raw_value,
       d.mean_score, d.stddev_score, d.facility_index,
       CASE WHEN d.stddev_score > 0 THEN ROUND((s.value - d.mean_score) / d.stddev_score, 2) ELSE 0 END AS z_score,
       CASE WHEN d.stddev_score > 0
            THEN GREATEST(0, LEAST(10, ROUND(7.0 + (s.value - d.mean_score) / d.stddev_score * 1.5, 2)))
            ELSE s.value END AS context_adjusted_value
FROM scores s JOIN classes c ON c.id = s.class_id
JOIN mv_exam_difficulty d
  ON d.subject_id = s.subject_id AND d.semester_id = s.semester_id
 AND d.score_category = s.score_category AND d.grade_id = c.grade_id
WHERE s.status = 'APPROVED' AND s.score_category IN ('MIDTERM', 'FINAL');
"""


def upgrade() -> None:
    op.execute("CREATE TYPE score_category_enum AS ENUM ('ORAL','REGULAR','MIDTERM','FINAL')")
    # View/MV phụ thuộc scores.score_type -> drop trước khi đổi cột
    op.execute("DROP VIEW IF EXISTS v_normalized_scores")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_exam_difficulty")

    op.drop_index("idx_scores_type", table_name="scores")
    op.drop_index("idx_scores_compound", table_name="scores")
    op.drop_constraint("uq_score_unique", "scores", type_="unique")
    op.drop_column("scores", "score_type")

    op.add_column("scores", sa.Column("score_category", _CATEGORY_ENUM, nullable=False))
    op.add_column("scores", sa.Column("column_index", sa.SmallInteger(), nullable=False, server_default="1"))
    op.alter_column("scores", "column_index", server_default=None)
    op.create_check_constraint("ck_scores_column_index_valid", "scores", "column_index >= 1")
    op.create_unique_constraint(
        "uq_score_unique", "scores",
        ["student_id", "subject_id", "semester_id", "score_category", "column_index"],
    )
    op.create_index("idx_scores_category", "scores", ["score_category"])
    op.create_index("idx_scores_compound", "scores", ["subject_id", "semester_id", "score_category", "column_index"])

    op.execute(_CALC_FN)
    op.execute(_MV)
    op.execute("CREATE UNIQUE INDEX idx_mv_diff ON mv_exam_difficulty(subject_id, semester_id, score_category, grade_id)")
    op.execute(_VIEW)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS v_normalized_scores")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_exam_difficulty")

    op.drop_index("idx_scores_compound", table_name="scores")
    op.drop_index("idx_scores_category", table_name="scores")
    op.drop_constraint("uq_score_unique", "scores", type_="unique")
    op.drop_constraint("ck_scores_column_index_valid", "scores", type_="check")
    op.drop_column("scores", "column_index")
    op.drop_column("scores", "score_category")

    op.add_column("scores", sa.Column(
        "score_type",
        sa.Enum("TX1", "TX2", "TX3", "TX4", "GK", "CK", name="score_type_enum", create_type=False),
        nullable=False, server_default="CK",
    ))
    op.alter_column("scores", "score_type", server_default=None)
    op.create_unique_constraint(
        "uq_score_unique", "scores", ["student_id", "subject_id", "semester_id", "score_type"]
    )
    op.create_index("idx_scores_type", "scores", ["score_type"])
    op.create_index("idx_scores_compound", "scores", ["subject_id", "semester_id", "score_type"])
    op.execute("DROP TYPE IF EXISTS score_category_enum")

    # Khôi phục calc + view bản cũ (TT22 cơ bản)
    op.execute("""
        CREATE OR REPLACE FUNCTION calc_subject_average(p_student_id UUID, p_subject_id UUID, p_semester_id UUID)
        RETURNS NUMERIC(4,2) AS $$
        DECLARE v_tx_sum NUMERIC := 0; v_tx_count INT := 0; v_gk NUMERIC; v_ck NUMERIC;
        BEGIN
            SELECT COALESCE(SUM(value),0), COUNT(*) INTO v_tx_sum, v_tx_count FROM scores
             WHERE student_id=p_student_id AND subject_id=p_subject_id AND semester_id=p_semester_id
               AND status='APPROVED' AND score_type IN ('TX1','TX2','TX3','TX4');
            SELECT value INTO v_gk FROM scores WHERE student_id=p_student_id AND subject_id=p_subject_id
               AND semester_id=p_semester_id AND score_type='GK' AND status='APPROVED';
            SELECT value INTO v_ck FROM scores WHERE student_id=p_student_id AND subject_id=p_subject_id
               AND semester_id=p_semester_id AND score_type='CK' AND status='APPROVED';
            IF v_gk IS NULL OR v_ck IS NULL OR v_tx_count = 0 THEN RETURN NULL; END IF;
            RETURN ROUND((v_tx_sum + 2*v_gk + 3*v_ck) / (v_tx_count + 5), 2);
        END; $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE MATERIALIZED VIEW mv_exam_difficulty AS
        SELECT s.subject_id, s.semester_id, s.score_type, c.grade_id, COUNT(*) AS n,
               ROUND(AVG(s.value),2) AS mean_score, ROUND(COALESCE(STDDEV_SAMP(s.value),0),2) AS stddev_score,
               ROUND(AVG((s.value<5.0)::int)::numeric,4) AS pct_below_5, ROUND(AVG(s.value)/10.0,4) AS facility_index
        FROM scores s JOIN classes c ON c.id=s.class_id
        WHERE s.status='APPROVED' AND s.score_type IN ('GK','CK')
        GROUP BY s.subject_id, s.semester_id, s.score_type, c.grade_id;
    """)
    op.execute("CREATE UNIQUE INDEX idx_mv_diff ON mv_exam_difficulty(subject_id, semester_id, score_type, grade_id)")
    op.execute("""
        CREATE VIEW v_normalized_scores AS
        SELECT s.id AS score_id, s.student_id, s.subject_id, s.semester_id, s.class_id, c.grade_id,
               s.score_type, s.value AS raw_value, d.mean_score, d.stddev_score, d.facility_index,
               CASE WHEN d.stddev_score>0 THEN ROUND((s.value-d.mean_score)/d.stddev_score,2) ELSE 0 END AS z_score,
               CASE WHEN d.stddev_score>0 THEN GREATEST(0,LEAST(10,ROUND(7.0+(s.value-d.mean_score)/d.stddev_score*1.5,2)))
                    ELSE s.value END AS context_adjusted_value
        FROM scores s JOIN classes c ON c.id=s.class_id
        JOIN mv_exam_difficulty d ON d.subject_id=s.subject_id AND d.semester_id=s.semester_id
          AND d.score_type=s.score_type AND d.grade_id=c.grade_id
        WHERE s.status='APPROVED' AND s.score_type IN ('GK','CK');
    """)

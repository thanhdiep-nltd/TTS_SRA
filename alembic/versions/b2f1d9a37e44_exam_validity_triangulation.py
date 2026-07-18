"""exam validity triangulation (TEVI): content_difficulty cols + v_exam_validity

Revision ID: b2f1d9a37e44
Revises: 71ec940cfa9c
Create Date: 2026-06-27 00:00:00.000000

Thêm cột phân tích nội dung đề (CDI) trên exam_papers + view tam giác hóa
v_exam_validity (EDI thực nghiệm vs CDI nội dung vs DDI khai báo) để phát hiện
phân kỳ điểm số (lạm phát/lỗ hổng dạy-học). Xem docs/exam_triangulation_design.md.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b2f1d9a37e44"
down_revision: Union[str, Sequence[str], None] = "71ec940cfa9c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FILE_TYPE_ENUM = sa.Enum("PDF", "WORD", "IMAGE", "OTHER", name="file_type_enum", create_type=False)

_VIEW = """
CREATE VIEW v_exam_validity AS
SELECT
  d.subject_id, d.semester_id, d.score_category, d.grade_id,
  d.n, d.mean_score, d.stddev_score, d.pct_below_5,
  (1 - d.facility_index)                               AS edi,
  ep.content_difficulty                                AS cdi,
  CASE ep.difficulty WHEN 'EASY' THEN 0.25 WHEN 'MEDIUM' THEN 0.5
                     WHEN 'HARD' THEN 0.75 END          AS ddi,
  ((1 - d.facility_index) - ep.content_difficulty)      AS divergence,
  ep.id                                                 AS exam_paper_id,
  ep.school_id                                          AS school_id,
  CASE
    WHEN ep.content_difficulty IS NULL THEN 'NO_CONTENT'
    WHEN d.n < 30 THEN 'LOW_SAMPLE'
    WHEN ((1 - d.facility_index) - ep.content_difficulty) <= -0.25 THEN 'INFLATION_OR_LEAK'
    WHEN ((1 - d.facility_index) - ep.content_difficulty) >=  0.25 THEN 'LEARNING_GAP'
    ELSE 'VALID'
  END                                                   AS flag
FROM mv_exam_difficulty d
JOIN exam_column_mappings m
  ON m.subject_id = d.subject_id AND m.semester_id = d.semester_id
 AND m.score_category = d.score_category AND m.grade_id = d.grade_id
JOIN exam_papers ep ON ep.id = m.exam_paper_id;
"""


def upgrade() -> None:
    op.add_column("exam_papers", sa.Column("content_difficulty", sa.Numeric(4, 3)))
    op.add_column("exam_papers", sa.Column("content_analyzed_at", sa.DateTime(timezone=True)))
    op.add_column("exam_papers", sa.Column("content_source", _FILE_TYPE_ENUM))
    op.execute(_VIEW)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS v_exam_validity")
    op.drop_column("exam_papers", "content_source")
    op.drop_column("exam_papers", "content_analyzed_at")
    op.drop_column("exam_papers", "content_difficulty")

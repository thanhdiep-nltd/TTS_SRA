"""exam validity triangulation: bỏ cột DDI (khai báo chủ quan của GV) khỏi v_exam_validity

Revision ID: d3a6f0a9c1b7
Revises: b2f1d9a37e44
Create Date: 2026-06-27 00:00:00.000000

DDI (CASE ep.difficulty ...) chưa từng tham gia công thức divergence/flag (chỉ EDI vs CDI) —
bỏ hẳn khỏi view vì là đánh giá chủ quan của người ra đề, không cần thiết cho tam giác hóa.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "d3a6f0a9c1b7"
down_revision: Union[str, Sequence[str], None] = "b2f1d9a37e44"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_VIEW_NO_DDI = """
CREATE VIEW v_exam_validity AS
SELECT
  d.subject_id, d.semester_id, d.score_category, d.grade_id,
  d.n, d.mean_score, d.stddev_score, d.pct_below_5,
  (1 - d.facility_index)                               AS edi,
  ep.content_difficulty                                AS cdi,
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

_VIEW_WITH_DDI = """
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
    op.execute("DROP VIEW IF EXISTS v_exam_validity")
    op.execute(_VIEW_NO_DDI)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS v_exam_validity")
    op.execute(_VIEW_WITH_DDI)

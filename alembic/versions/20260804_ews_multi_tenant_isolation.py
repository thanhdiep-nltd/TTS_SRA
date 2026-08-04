"""EWS Multi-Tenant Isolation: add so_school_id to prediction & training tables.

Revision ID: 20260804_ews_multi_tenant_isolation
Revises:
Create Date: 2026-08-04

Thêm cột ``so_school_id`` vào:
  - s360.fact_student_subject_risk_predictions
  - s360.train_student_subject_risk_dataset

Kèm backfill từ ``dim_homeroom_class_student`` (trước khi đặt NOT NULL), cập nhật
UNIQUE constraint ``uq_fssrp_checkpoint`` để bao gồm ``so_school_id``, và thêm index
``idx_fssrp_school`` / ``idx_tssrd_school``.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260804_ews_multi_tenant_isolation"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Backfill: lấy so_school_id từ dim_homeroom_class_student theo (student_code, school_year_id),
# ưu tiên dòng is_active=1 (khớp logic DISTINCT ON trong feature_extractor / ews.py).
_BACKFILL_PREDICTIONS = """
UPDATE s360.fact_student_subject_risk_predictions rp
SET so_school_id = sub.so_school_id
FROM (
    SELECT DISTINCT ON (student_code, school_year_id)
        student_code, school_year_id, so_school_id
    FROM s360.dim_homeroom_class_student
    ORDER BY student_code, school_year_id, is_active DESC, homeroom_class_id
) sub
WHERE rp.student_code = sub.student_code
  AND rp.school_year_id = sub.school_year_id;
"""

_BACKFILL_TRAIN = """
UPDATE s360.train_student_subject_risk_dataset tr
SET so_school_id = sub.so_school_id
FROM (
    SELECT DISTINCT ON (student_code, school_year_id)
        student_code, school_year_id, so_school_id
    FROM s360.dim_homeroom_class_student
    ORDER BY student_code, school_year_id, is_active DESC, homeroom_class_id
) sub
WHERE tr.student_code = sub.student_code
  AND tr.school_year_id = sub.school_year_id;
"""


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Thêm cột so_school_id (nullable trước để backfill)
    op.add_column(
        "fact_student_subject_risk_predictions",
        sa.Column("so_school_id", sa.Integer(), nullable=True),
        schema="s360",
    )
    op.add_column(
        "train_student_subject_risk_dataset",
        sa.Column("so_school_id", sa.Integer(), nullable=True),
        schema="s360",
    )

    # 2. Backfill từ dim_homeroom_class_student
    op.execute(_BACKFILL_PREDICTIONS)
    op.execute(_BACKFILL_TRAIN)

    # 3. Đặt NOT NULL
    op.alter_column(
        "fact_student_subject_risk_predictions",
        "so_school_id",
        existing_type=sa.Integer(),
        nullable=False,
        schema="s360",
    )
    op.alter_column(
        "train_student_subject_risk_dataset",
        "so_school_id",
        existing_type=sa.Integer(),
        nullable=False,
        schema="s360",
    )

    # 4. Cập nhật UNIQUE constraint để bao gồm so_school_id
    op.drop_constraint(
        "uq_fssrp_checkpoint",
        "fact_student_subject_risk_predictions",
        type_="unique",
        schema="s360",
    )
    op.create_unique_constraint(
        "uq_fssrp_checkpoint",
        "fact_student_subject_risk_predictions",
        [
            "so_school_id",
            "student_code",
            "subject_id",
            "school_year_id",
            "semester_index",
            "evaluated_at_week",
            "model_version",
        ],
        schema="s360",
    )

    # 5. Index theo trường
    op.create_index(
        "idx_fssrp_school",
        "fact_student_subject_risk_predictions",
        ["so_school_id"],
        schema="s360",
    )
    op.create_index(
        "idx_tssrd_school",
        "train_student_subject_risk_dataset",
        ["so_school_id"],
        schema="s360",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_tssrd_school", table_name="train_student_subject_risk_dataset", schema="s360")
    op.drop_index("idx_fssrp_school", table_name="fact_student_subject_risk_predictions", schema="s360")

    op.drop_constraint(
        "uq_fssrp_checkpoint",
        "fact_student_subject_risk_predictions",
        type_="unique",
        schema="s360",
    )
    op.create_unique_constraint(
        "uq_fssrp_checkpoint",
        "fact_student_subject_risk_predictions",
        [
            "student_code",
            "subject_id",
            "school_year_id",
            "semester_index",
            "evaluated_at_week",
            "model_version",
        ],
        schema="s360",
    )

    op.drop_column("train_student_subject_risk_dataset", "so_school_id", schema="s360")
    op.drop_column("fact_student_subject_risk_predictions", "so_school_id", schema="s360")

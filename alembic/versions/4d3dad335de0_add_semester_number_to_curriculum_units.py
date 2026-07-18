"""add semester_number to curriculum_units

Revision ID: 4d3dad335de0
Revises: 8180b7030cd6
Create Date: 2026-07-08 01:36:23.080955

Chương/chủ đề có thể chỉ dạy ở 1 học kỳ (SGK tách "tập 1"/"tập 2", vd Toán) hoặc dạy cả năm
(SGK 1 tập, vd KHTN — không tách). NULL = không hạn chế học kỳ (hiện ở cả 2 kỳ khi chọn ma
trận đề); 1/2 = chỉ chương đó thuộc học kỳ tương ứng. Dùng để lọc checklist chọn chương ở
wizard tạo đề (frontend/src/app/(app)/exam-builder/page.tsx) theo học kỳ GV đã chọn.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4d3dad335de0'
down_revision: Union[str, Sequence[str], None] = '8180b7030cd6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("curriculum_units", sa.Column("semester_number", sa.SmallInteger(), nullable=True))
    op.create_check_constraint(
        "curri_semester_number_valid", "curriculum_units", "semester_number IN (1, 2)"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("curri_semester_number_valid", "curriculum_units", type_="check")
    op.drop_column("curriculum_units", "semester_number")

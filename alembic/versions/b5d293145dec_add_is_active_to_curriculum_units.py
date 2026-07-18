"""add is_active to curriculum_units

Revision ID: b5d293145dec
Revises: 4d3dad335de0
Create Date: 2026-07-08 02:50:34.356291

Ẩn các chương/chủ đề RÁC (tàn dư phân mảnh taxonomy từ lỗi pipeline CDI cũ — LLM tự đặt tên
chủ đề tự do trước khi có RAG-anchored CDI) khỏi picker chọn chương, KHÔNG xóa vì vẫn còn bị
exam_competencies tham chiếu thật (phân tích đề đã upload trước đây) — xóa sẽ vỡ FK hoặc mất
dữ liệu phân tích lịch sử.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b5d293145dec'
down_revision: Union[str, Sequence[str], None] = '4d3dad335de0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "curriculum_units",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("curriculum_units", "is_active")

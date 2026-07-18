"""thong bao: notification_type_enum + bang notifications

Revision ID: b8d4f1e6a293
Revises: a7c3e9f12b40
Create Date: 2026-06-28 00:00:00.000000

Thong bao su kien he thong (cau hoi moi cho duyet, da duyet/tu choi, de da chot)
+ thong bao chu dong do BGH/Truong bo mon soan gui (broadcast theo pham vi:
toan truong / 1 bo mon / 1 ca nhan). Xem docs/exam_generation_ui_design.md muc C.6.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "b8d4f1e6a293"
down_revision: str | Sequence[str] | None = "a7c3e9f12b40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NOTIFICATION_TYPE = postgresql.ENUM(
    "QUESTION_SUBMITTED", "ITEM_REVIEWED", "EXAM_FINALIZED", "ANNOUNCEMENT", name="notification_type_enum"
)
# Biến thể dùng cho Column: postgresql.ENUM trực tiếp + create_type=False (KHÔNG dùng sa.Enum
# chung — xem ghi chú trong a7c3e9f12b40: sa.Enum mất cờ create_type khi adapt sang dialect PG).
_NOTIFICATION_TYPE_COL = postgresql.ENUM(
    "QUESTION_SUBMITTED", "ITEM_REVIEWED", "EXAM_FINALIZED", "ANNOUNCEMENT",
    name="notification_type_enum", create_type=False,
)


def upgrade() -> None:
    _NOTIFICATION_TYPE.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "notifications",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuid_generate_v4()"), nullable=False),
        sa.Column("school_id", sa.UUID(), nullable=False),
        sa.Column("recipient_id", sa.UUID(), nullable=False),
        sa.Column("sender_id", sa.UUID(), nullable=True),
        sa.Column("type", _NOTIFICATION_TYPE_COL, nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=True),
        sa.Column("entity_id", sa.UUID(), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recipient_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_notif_recipient", "notifications", ["recipient_id", "read_at"])
    op.create_index("idx_notif_school", "notifications", ["school_id"])


def downgrade() -> None:
    op.drop_table("notifications")
    _NOTIFICATION_TYPE.drop(op.get_bind(), checkfirst=True)

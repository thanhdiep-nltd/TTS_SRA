"""ai session attachments

Revision ID: 27ad79ec7477
Revises: c01ef1812742
Create Date: 2026-06-30 03:25:39.604917

Bang luu file dinh kem trong chat (AI doc noi dung), gan theo session_id.
file_type_enum da ton tai (dung chung voi exam_papers) - bat buoc create_type=False
de tranh loi "type already exists" khi upgrade.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "27ad79ec7477"
down_revision: str | Sequence[str] | None = "c01ef1812742"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Tao bang ai_session_attachments."""
    op.create_table(
        "ai_session_attachments",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuid_generate_v4()"), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("uploaded_by", sa.UUID(), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("stored_name", sa.String(length=255), nullable=False),
        sa.Column(
            "file_type",
            postgresql.ENUM("PDF", "WORD", "IMAGE", "OTHER", name="file_type_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("char_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("truncated", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["ai_sessions.id"],
            name=op.f("fk_ai_session_attachments_session_id_ai_sessions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by"], ["users.id"], name=op.f("fk_ai_session_attachments_uploaded_by_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_session_attachments")),
    )
    op.create_index("idx_attachment_session", "ai_session_attachments", ["session_id"], unique=False)


def downgrade() -> None:
    """Xoa bang ai_session_attachments."""
    op.drop_index("idx_attachment_session", table_name="ai_session_attachments")
    op.drop_table("ai_session_attachments")

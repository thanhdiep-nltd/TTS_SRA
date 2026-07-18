"""ai observability snapshots

Revision ID: c01ef1812742
Revises: 7c2a4e9f0d31
Create Date: 2026-06-29 14:16:48.422641

Bang snapshot dinh ky (background job ghi moi 15-30 phut) cho trend chart
"Tinh trang he thong AI" trong app - doc gia tri tu Prometheus REGISTRY trong
process, khong phai du lieu nghiep vu theo truong (khong co school_id).
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c01ef1812742"
down_revision: str | Sequence[str] | None = "7c2a4e9f0d31"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Tao bang ai_observability_snapshots."""
    op.create_table(
        "ai_observability_snapshots",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuid_generate_v4()"), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("daily_cost_usd", sa.Numeric(precision=10, scale=6), server_default=sa.text("0"), nullable=False),
        sa.Column("daily_budget_usd", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("latency_p95_ms", sa.Integer(), nullable=True),
        sa.Column("ttft_p95_ms", sa.Integer(), nullable=True),
        sa.Column("faithfulness_avg", sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column("tool_success_rate", sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column("total_requests", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("total_tokens_in", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("total_tokens_out", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_observability_snapshots")),
    )
    op.create_index("idx_observability_captured_at", "ai_observability_snapshots", ["captured_at"], unique=False)


def downgrade() -> None:
    """Xoa bang ai_observability_snapshots."""
    op.drop_index("idx_observability_captured_at", table_name="ai_observability_snapshots")
    op.drop_table("ai_observability_snapshots")

"""add groundedness_avg to ai observability snapshots

Revision ID: 7e041ad02d53
Revises: 27ad79ec7477
Create Date: 2026-06-30 12:07:11.240375

Them cot groundedness_avg (Eval-as-a-Metric cho data_agent/stat_agent/sql_agent, tuong tu
faithfulness_avg da co cho knowledge_agent/RAG) de ve trend chart lich su trong UI.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7e041ad02d53"
down_revision: str | Sequence[str] | None = "27ad79ec7477"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Them cot groundedness_avg vao ai_observability_snapshots."""
    op.add_column(
        "ai_observability_snapshots",
        sa.Column("groundedness_avg", sa.Numeric(precision=4, scale=3), nullable=True),
    )


def downgrade() -> None:
    """Xoa cot groundedness_avg."""
    op.drop_column("ai_observability_snapshots", "groundedness_avg")

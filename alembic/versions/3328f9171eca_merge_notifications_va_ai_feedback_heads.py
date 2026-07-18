"""merge notifications va ai feedback heads

Revision ID: 3328f9171eca
Revises: b8d4f1e6a293, dfd758473722
Create Date: 2026-06-28 14:21:44.309437

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = '3328f9171eca'
down_revision: str | Sequence[str] | None = ('b8d4f1e6a293', 'dfd758473722')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass

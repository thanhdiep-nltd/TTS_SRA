"""add exam_format to exam_blueprints

Revision ID: f3a8c1d92b56
Revises: b5d293145dec
Create Date: 2026-07-08 04:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f3a8c1d92b56'
down_revision: Union[str, Sequence[str], None] = 'b5d293145dec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

exam_format_enum = postgresql.ENUM('MCQ_ONLY', 'ESSAY_ONLY', 'MIXED', name='exam_format_enum', create_type=False)


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    exam_format_enum.create(bind, checkfirst=True)
    op.add_column('exam_blueprints', sa.Column('exam_format', exam_format_enum, nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('exam_blueprints', 'exam_format')
    op.execute("DROP TYPE IF EXISTS exam_format_enum")

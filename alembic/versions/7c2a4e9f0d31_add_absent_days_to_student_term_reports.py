"""add absent_days to student_term_reports

Revision ID: 7c2a4e9f0d31
Revises: 3328f9171eca
Create Date: 2026-06-28 00:00:00.000000

Cot absent_days (so ngay nghi, do GV chu nhiem nhap) cho trang /homeroom.
Cot da duoc them thu cong len Neon truoc khi migration nay duoc commit -
dung op.add_column voi checkfirst-safe IF NOT EXISTS de an toan ca 2 truong hop.
"""
from collections.abc import Sequence

from alembic import op

revision: str = "7c2a4e9f0d31"
down_revision: str | Sequence[str] | None = "3328f9171eca"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE student_term_reports ADD COLUMN IF NOT EXISTS absent_days INTEGER DEFAULT 0"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE student_term_reports DROP COLUMN IF EXISTS absent_days")

"""Add start_page, end_page to curriculum_units and create curriculum_chunks for RAG.

Revision ID: 20260825_add_curriculum_chunks
Revises: 20260804_ews_multi_tenant_isolation
Create Date: 2026-08-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "20260825_add_curriculum_chunks"
down_revision: Union[str, Sequence[str], None] = "20260804_ews_multi_tenant_isolation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Đảm bảo pgvector extension đã được kích hoạt
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # 2. Thêm start_page và end_page vào curriculum_units
    op.add_column("curriculum_units", sa.Column("start_page", sa.Integer(), nullable=True))
    op.add_column("curriculum_units", sa.Column("end_page", sa.Integer(), nullable=True))

    # 3. Tạo bảng curriculum_chunks
    op.create_table(
        "curriculum_chunks",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, primary_key=True),
        sa.Column("book_id", sa.BigInteger(), sa.ForeignKey("curriculum_books.id", ondelete="CASCADE"), nullable=False),
        sa.Column("unit_id", sa.BigInteger(), sa.ForeignKey("curriculum_units.id", ondelete="CASCADE"), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("heading", sa.String(length=255), nullable=True),
        sa.Column("context_path", sa.String(length=500), nullable=True),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # 4. Indexes cho lookup và HNSW vector search
    op.create_index("idx_curri_chunk_book", "curriculum_chunks", ["book_id"])
    op.create_index("idx_curri_chunk_unit", "curriculum_chunks", ["unit_id"])
    op.create_index("idx_curri_chunk_page", "curriculum_chunks", ["page_number"])
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_curri_chunk_embedding 
        ON public.curriculum_chunks USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 200);
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_curri_chunk_embedding;")
    op.drop_index("idx_curri_chunk_page", table_name="curriculum_chunks")
    op.drop_index("idx_curri_chunk_unit", table_name="curriculum_chunks")
    op.drop_index("idx_curri_chunk_book", table_name="curriculum_chunks")
    op.drop_table("curriculum_chunks")
    op.drop_column("curriculum_units", "end_page")
    op.drop_column("curriculum_units", "start_page")

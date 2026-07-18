"""exam generation: question bank + blueprint + assembled exams

Revision ID: a7c3e9f12b40
Revises: d3a6f0a9c1b7
Create Date: 2026-06-28 00:00:00.000000

Tính năng tạo đề chính thức từ ngân hàng câu hỏi (AI Exam Generation).
Thêm 4 enum + 4 bảng: question_items (ngân hàng câu hỏi, nguồn sự thật),
exam_blueprints (ma trận đề), generated_exams (lần ráp) + generated_exam_items
(câu trong từng mã đề). Xem docs/exam_generation_design.md.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a7c3e9f12b40"
down_revision: str | Sequence[str] | None = "d3a6f0a9c1b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Enum mới (tạo thủ công để kiểm soát thứ tự DDL — score_category_enum đã tồn tại, không tạo lại).
_QUESTION_TYPE = postgresql.ENUM("MCQ", "TRUE_FALSE", "SHORT_ANSWER", "ESSAY", name="question_type_enum")
_ITEM_STATUS = postgresql.ENUM("DRAFT", "REVIEW", "APPROVED", "REJECTED", "RETIRED", name="item_status_enum")
_ITEM_SOURCE = postgresql.ENUM("AI_GENERATED", "MANUAL", "IMPORTED", name="item_source_enum")
_GEN_EXAM_STATUS = postgresql.ENUM("DRAFT", "FINALIZED", "PUBLISHED", name="gen_exam_status_enum")


def _new_enums() -> list:
    return [_QUESTION_TYPE, _ITEM_STATUS, _ITEM_SOURCE, _GEN_EXAM_STATUS]


# Biến thể dùng cho Column: PHẢI dùng postgresql.ENUM (dialect-specific), KHÔNG dùng sa.Enum
# chung — sa.Enum(create_type=False) bị mất cờ create_type khi SQLAlchemy adapt sang dialect
# PG (xem sqltypes.Enum._make_enum_kw, không forward create_type), khiến op.create_table vẫn
# cố CREATE TYPE lại và đụng DuplicateObject với type đã tạo ở bước trên.
def _col_enum(name: str, *values: str) -> postgresql.ENUM:
    return postgresql.ENUM(*values, name=name, create_type=False)


_QUESTION_TYPE_COL = _col_enum("question_type_enum", "MCQ", "TRUE_FALSE", "SHORT_ANSWER", "ESSAY")
_ITEM_STATUS_COL = _col_enum("item_status_enum", "DRAFT", "REVIEW", "APPROVED", "REJECTED", "RETIRED")
_ITEM_SOURCE_COL = _col_enum("item_source_enum", "AI_GENERATED", "MANUAL", "IMPORTED")
_GEN_EXAM_STATUS_COL = _col_enum("gen_exam_status_enum", "DRAFT", "FINALIZED", "PUBLISHED")
# Tham chiếu enum đã có (không tạo lại type).
_SCORE_CATEGORY = _col_enum("score_category_enum", "ORAL", "REGULAR", "MIDTERM", "FINAL")


def upgrade() -> None:
    bind = op.get_bind()
    for e in _new_enums():
        e.create(bind, checkfirst=True)

    op.create_table(
        "question_items",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuid_generate_v4()"), nullable=False),
        sa.Column("school_id", sa.UUID(), nullable=False),
        sa.Column("subject_id", sa.UUID(), nullable=False),
        sa.Column("grade_number", sa.SmallInteger(), nullable=False),
        sa.Column("unit_id", sa.UUID(), nullable=False),
        sa.Column("bloom_level", sa.SmallInteger(), nullable=False),
        sa.Column("question_type", _QUESTION_TYPE_COL, nullable=False),
        sa.Column("stem", sa.Text(), nullable=False),
        sa.Column("options", postgresql.JSONB(), nullable=True),
        sa.Column("answer_key", postgresql.JSONB(), nullable=False),
        sa.Column("solution", sa.Text(), nullable=True),
        sa.Column("default_points", sa.Numeric(4, 2), server_default=sa.text("1.0"), nullable=False),
        sa.Column("status", _ITEM_STATUS_COL, server_default=sa.text("'DRAFT'"), nullable=False),
        sa.Column("source", _ITEM_SOURCE_COL, server_default=sa.text("'AI_GENERATED'"), nullable=False),
        sa.Column("provenance", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("times_used", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("p_value", sa.Numeric(4, 3), nullable=True),
        sa.Column("discrimination", sa.Numeric(4, 3), nullable=True),
        sa.Column("exposure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("reviewed_by", sa.UUID(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("grade_number BETWEEN 1 AND 12", name="qi_grade_number_valid"),
        sa.CheckConstraint("bloom_level BETWEEN 1 AND 6", name="qi_bloom_level_valid"),
        sa.CheckConstraint("default_points > 0", name="qi_points_positive"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["unit_id"], ["curriculum_units.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_qi_pick", "question_items",
                    ["subject_id", "grade_number", "unit_id", "bloom_level", "status"])
    op.create_index("idx_qi_school", "question_items", ["school_id"])

    op.create_table(
        "exam_blueprints",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuid_generate_v4()"), nullable=False),
        sa.Column("school_id", sa.UUID(), nullable=False),
        sa.Column("subject_id", sa.UUID(), nullable=False),
        sa.Column("grade_number", sa.SmallInteger(), nullable=False),
        sa.Column("score_category", _SCORE_CATEGORY, nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("total_points", sa.Numeric(5, 2), server_default=sa.text("10.0"), nullable=False),
        sa.Column("duration_min", sa.SmallInteger(), nullable=True),
        sa.Column("target_difficulty", sa.Numeric(4, 3), nullable=True),
        sa.Column("cells", postgresql.JSONB(), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("grade_number BETWEEN 1 AND 12", name="bp_grade_number_valid"),
        sa.CheckConstraint("total_points > 0", name="bp_total_points_positive"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_bp_subject", "exam_blueprints", ["subject_id", "grade_number"])
    op.create_index("idx_bp_school", "exam_blueprints", ["school_id"])

    op.create_table(
        "generated_exams",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuid_generate_v4()"), nullable=False),
        sa.Column("school_id", sa.UUID(), nullable=False),
        sa.Column("blueprint_id", sa.UUID(), nullable=False),
        sa.Column("semester_id", sa.UUID(), nullable=False),
        sa.Column("grade_id", sa.UUID(), nullable=True),
        sa.Column("num_variants", sa.SmallInteger(), server_default=sa.text("1"), nullable=False),
        sa.Column("status", _GEN_EXAM_STATUS_COL, server_default=sa.text("'DRAFT'"), nullable=False),
        sa.Column("exam_paper_id", sa.UUID(), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("num_variants BETWEEN 1 AND 20", name="ge_num_variants_valid"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["blueprint_id"], ["exam_blueprints.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["semester_id"], ["semesters.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["grade_id"], ["grades.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["exam_paper_id"], ["exam_papers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_ge_blueprint", "generated_exams", ["blueprint_id"])
    op.create_index("idx_ge_school", "generated_exams", ["school_id"])

    op.create_table(
        "generated_exam_items",
        sa.Column("generated_exam_id", sa.UUID(), nullable=False),
        sa.Column("variant_code", sa.String(8), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("item_id", sa.UUID(), nullable=False),
        sa.Column("points", sa.Numeric(4, 2), nullable=False),
        sa.Column("option_order", postgresql.JSONB(), nullable=True),
        sa.CheckConstraint("position >= 1", name="gei_position_valid"),
        sa.ForeignKeyConstraint(["generated_exam_id"], ["generated_exams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["item_id"], ["question_items.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("generated_exam_id", "variant_code", "position"),
    )
    op.create_index("idx_gei_item", "generated_exam_items", ["item_id"])


def downgrade() -> None:
    op.drop_table("generated_exam_items")
    op.drop_table("generated_exams")
    op.drop_table("exam_blueprints")
    op.drop_table("question_items")
    bind = op.get_bind()
    for e in _new_enums():
        e.drop(bind, checkfirst=True)

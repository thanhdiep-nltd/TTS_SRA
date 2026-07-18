"""add assessment_type + subject_evaluations + student_term_reports

Revision ID: 71ec940cfa9c
Revises: c5add4571b15
Create Date: 2026-06-14 17:09:03.822312

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '71ec940cfa9c'
down_revision: Union[str, Sequence[str], None] = 'c5add4571b15'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Enum types (tạo tường minh; create_type=False để không tạo lại khi dùng trong cột).
conduct_enum = postgresql.ENUM('TOT', 'KHA', 'TRUNG_BINH', 'YEU', name='conduct_enum', create_type=False)
pass_fail_enum = postgresql.ENUM('DAT', 'CHUA_DAT', name='pass_fail_enum', create_type=False)
assessment_type_enum = postgresql.ENUM('SCORED', 'REMARK', name='assessment_type_enum', create_type=False)


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    conduct_enum.create(bind, checkfirst=True)
    pass_fail_enum.create(bind, checkfirst=True)
    assessment_type_enum.create(bind, checkfirst=True)

    op.create_table('student_term_reports',
    sa.Column('id', sa.UUID(), server_default=sa.text('uuid_generate_v4()'), nullable=False),
    sa.Column('student_id', sa.UUID(), nullable=False),
    sa.Column('class_id', sa.UUID(), nullable=False),
    sa.Column('semester_id', sa.UUID(), nullable=False),
    sa.Column('conduct', conduct_enum, nullable=True),
    sa.Column('general_comment', sa.Text(), nullable=True),
    sa.Column('evaluated_by', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['class_id'], ['classes.id'], name=op.f('fk_student_term_reports_class_id_classes'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['evaluated_by'], ['users.id'], name=op.f('fk_student_term_reports_evaluated_by_users'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['semester_id'], ['semesters.id'], name=op.f('fk_student_term_reports_semester_id_semesters'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['student_id'], ['students.id'], name=op.f('fk_student_term_reports_student_id_students'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_student_term_reports')),
    sa.UniqueConstraint('student_id', 'class_id', 'semester_id', name='uq_term_report')
    )
    op.create_index('idx_termreport_class_sem', 'student_term_reports', ['class_id', 'semester_id'], unique=False)
    op.create_table('subject_evaluations',
    sa.Column('id', sa.UUID(), server_default=sa.text('uuid_generate_v4()'), nullable=False),
    sa.Column('student_id', sa.UUID(), nullable=False),
    sa.Column('subject_id', sa.UUID(), nullable=False),
    sa.Column('class_id', sa.UUID(), nullable=False),
    sa.Column('semester_id', sa.UUID(), nullable=False),
    sa.Column('result', pass_fail_enum, nullable=True),
    sa.Column('comment', sa.Text(), nullable=True),
    sa.Column('evaluated_by', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['class_id'], ['classes.id'], name=op.f('fk_subject_evaluations_class_id_classes'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['evaluated_by'], ['users.id'], name=op.f('fk_subject_evaluations_evaluated_by_users'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['semester_id'], ['semesters.id'], name=op.f('fk_subject_evaluations_semester_id_semesters'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['student_id'], ['students.id'], name=op.f('fk_subject_evaluations_student_id_students'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], name=op.f('fk_subject_evaluations_subject_id_subjects'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_subject_evaluations')),
    sa.UniqueConstraint('student_id', 'subject_id', 'semester_id', name='uq_subject_eval')
    )
    op.create_index('idx_subjeval_class_sem', 'subject_evaluations', ['class_id', 'semester_id'], unique=False)
    op.create_index('idx_subjeval_subject', 'subject_evaluations', ['subject_id'], unique=False)
    op.add_column('subjects', sa.Column('assessment_type', assessment_type_enum, server_default=sa.text("'SCORED'"), nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('subjects', 'assessment_type')
    op.drop_index('idx_subjeval_subject', table_name='subject_evaluations')
    op.drop_index('idx_subjeval_class_sem', table_name='subject_evaluations')
    op.drop_table('subject_evaluations')
    op.drop_index('idx_termreport_class_sem', table_name='student_term_reports')
    op.drop_table('student_term_reports')
    op.execute("DROP TYPE IF EXISTS assessment_type_enum")
    op.execute("DROP TYPE IF EXISTS pass_fail_enum")
    op.execute("DROP TYPE IF EXISTS conduct_enum")

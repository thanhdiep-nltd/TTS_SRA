"""SQLAlchemy ORM models — phản ánh docs/schema.sql (v2.0).

Enum được tạo/xóa thủ công trong migration (create_type=False) để kiểm soát
chính xác thứ tự DDL và tránh lỗi "type already exists" với enum dùng chung.
"""

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import ARRAY, INET, JSONB, UUID

from src.db.base import Base
from src.models import enums

_UUID_PK = text("uuid_generate_v4()")
_NOW = text("now()")


def pg_enum(py_enum, name: str) -> SAEnum:
    """Map Python enum sang PG enum, lưu theo .value, không tự tạo type."""
    return SAEnum(
        py_enum,
        name=name,
        values_callable=lambda e: [m.value for m in e],
        create_type=False,
    )


# ============================================================
# SCHOOLS
# ============================================================


class School(Base):
    __tablename__ = "schools"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=_UUID_PK)
    name = Column(String(255), nullable=False)
    code = Column(String(50), unique=True, nullable=False)
    address = Column(Text)
    phone = Column(String(20))
    logo_url = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=_NOW)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=_NOW)


# ============================================================
# USERS & AUTHENTICATION
# ============================================================


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("idx_users_school", "so_school_id"),
        Index("idx_users_role", "role"),
        Index("idx_users_email", "email"),
        Index("idx_users_tcode", "teacher_code"),
        Index("idx_users_scode", "student_code"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    so_school_id = Column(Integer, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    phone = Column(String(20))
    avatar_url = Column(Text)
    role = Column(pg_enum(enums.UserRole, "user_role_enum"), nullable=False)
    school_level = Column(pg_enum(enums.SchoolLevel, "school_level_enum"), nullable=False, server_default=text("'ALL'"))
    subject_id = Column(Integer)
    teacher_code = Column(String(50))
    student_code = Column(String(50))
    so_student_id = Column(BigInteger)
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    last_login_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=_NOW)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=_NOW)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(String(255), nullable=False, unique=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=_NOW)



# ============================================================
# CORE SCHOOL STRUCTURE
# ============================================================


class AcademicYear(Base):
    __tablename__ = "academic_years"
    __table_args__ = (UniqueConstraint("school_id", "name", name="uq_academic_year_school_name"),)

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=_UUID_PK)
    school_id = Column(UUID(as_uuid=True), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(20), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    is_current = Column(Boolean, nullable=False, server_default=text("false"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=_NOW)


class Semester(Base):
    __tablename__ = "semesters"
    __table_args__ = (
        CheckConstraint("number IN (1, 2)", name="number_valid"),
        UniqueConstraint("academic_year_id", "number", name="uq_semester_year_number"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=_UUID_PK)
    academic_year_id = Column(UUID(as_uuid=True), ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(10), nullable=False)
    number = Column(SmallInteger, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    is_current = Column(Boolean, nullable=False, server_default=text("false"))


class Grade(Base):
    __tablename__ = "grades"
    __table_args__ = (
        CheckConstraint("grade_number BETWEEN 1 AND 12", name="grade_number_valid"),
        UniqueConstraint("school_id", "grade_number", name="uq_grade_school_number"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=_UUID_PK)
    school_id = Column(UUID(as_uuid=True), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(20), nullable=False)
    grade_number = Column(SmallInteger, nullable=False)
    school_level = Column(pg_enum(enums.SchoolLevel, "school_level_enum"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=_NOW)


class Class(Base):
    __tablename__ = "classes"
    __table_args__ = (
        UniqueConstraint("grade_id", "name", "academic_year_id", name="uq_class_grade_name_year"),
        Index("idx_classes_grade", "grade_id"),
        Index("idx_classes_year", "academic_year_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=_UUID_PK)
    grade_id = Column(UUID(as_uuid=True), ForeignKey("grades.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(20), nullable=False)
    academic_year_id = Column(UUID(as_uuid=True), ForeignKey("academic_years.id"), nullable=False)
    student_count = Column(SmallInteger, server_default=text("0"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=_NOW)


class Subject(Base):
    __tablename__ = "subjects"
    __table_args__ = (UniqueConstraint("school_id", "code", name="uq_subject_school_code"),)

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=_UUID_PK)
    school_id = Column(UUID(as_uuid=True), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    code = Column(String(20), nullable=False)
    applicable_level = Column(
        pg_enum(enums.SchoolLevel, "school_level_enum"), nullable=False, server_default=text("'ALL'")
    )
    # SCORED = cho điểm 0–10 (tính ĐTB); REMARK = đánh giá Đạt/Chưa đạt (không tính ĐTB).
    assessment_type = Column(
        pg_enum(enums.AssessmentType, "assessment_type_enum"), nullable=False, server_default=text("'SCORED'")
    )
    subject_head_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=_NOW)


# ============================================================
# TEACHER ASSIGNMENTS
# ============================================================

_ASSIGNMENT_CHECK = """
    (role_context = 'HOMEROOM_PRIMARY'   AND class_id IS NOT NULL AND subject_id IS NULL     AND grade_id IS NULL) OR
    (role_context = 'GRADE_HEAD'         AND grade_id IS NOT NULL AND class_id IS NULL       AND subject_id IS NULL) OR
    (role_context = 'SUBJECT_TEACHER'    AND class_id IS NOT NULL AND subject_id IS NOT NULL AND grade_id IS NULL) OR
    (role_context = 'HOMEROOM_SECONDARY' AND class_id IS NOT NULL AND subject_id IS NULL     AND grade_id IS NULL) OR
    (role_context = 'SUBJECT_HEAD'       AND subject_id IS NOT NULL AND class_id IS NULL     AND grade_id IS NULL)
"""


class TeacherAssignment(Base):
    __tablename__ = "teacher_assignments"
    __table_args__ = (
        CheckConstraint(_ASSIGNMENT_CHECK, name="assignment_consistency"),
        UniqueConstraint(
            "user_id",
            "role_context",
            "class_id",
            "grade_id",
            "subject_id",
            "academic_year_id",
            name="uq_teacher_assignment",
            postgresql_nulls_not_distinct=True,
        ),
        Index("idx_ta_user", "user_id"),
        Index("idx_ta_class", "class_id"),
        Index("idx_ta_grade", "grade_id"),
        Index("idx_ta_subject", "subject_id"),
        Index("idx_ta_year", "academic_year_id"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    academic_year_id = Column(BigInteger, nullable=False, server_default=text("2025"))
    role_context = Column(pg_enum(enums.RoleContext, "role_context_enum"), nullable=False)
    class_id = Column(BigInteger)
    grade_id = Column(BigInteger)
    subject_id = Column(BigInteger)
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=_NOW)


# ============================================================
# STUDENTS
# ============================================================


class Student(Base):
    __tablename__ = "students"
    __table_args__ = (
        CheckConstraint("gender IN ('MALE', 'FEMALE', 'OTHER')", name="gender_valid"),
        UniqueConstraint("school_id", "student_code", name="uq_student_school_code"),
        Index("idx_students_name", "full_name", postgresql_using="gin", postgresql_ops={"full_name": "gin_trgm_ops"}),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=_UUID_PK)
    school_id = Column(UUID(as_uuid=True), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    student_code = Column(String(20), nullable=False)
    full_name = Column(String(255), nullable=False)
    date_of_birth = Column(Date)
    gender = Column(String(10))
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=_NOW)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=_NOW)


class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint("student_id", "academic_year_id", name="uq_enrollment_student_year"),
        Index("idx_enroll_student", "student_id"),
        Index("idx_enroll_class", "class_id"),
        Index("idx_enroll_year", "academic_year_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=_UUID_PK)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id", ondelete="CASCADE"), nullable=False)
    academic_year_id = Column(UUID(as_uuid=True), ForeignKey("academic_years.id"), nullable=False)
    enrolled_at = Column(Date, nullable=False, server_default=text("CURRENT_DATE"))
    is_active = Column(Boolean, nullable=False, server_default=text("true"))


# ============================================================
# EXAM PAPERS & CURRICULUM
# ============================================================


class ExamPaper(Base):
    __tablename__ = "exam_papers"
    __table_args__ = (
        CheckConstraint("difficulty_coefficient BETWEEN 0.50 AND 1.50", name="difficulty_coefficient_range"),
        Index("idx_exam_subject", "subject_id"),
        Index("idx_exam_semester", "semester_id"),
        Index("idx_exam_grade", "grade_id"),
        Index("idx_exam_type", "score_type"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=_UUID_PK)
    school_id = Column(UUID(as_uuid=True), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    subject_id = Column(UUID(as_uuid=True), ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=False)
    semester_id = Column(UUID(as_uuid=True), ForeignKey("semesters.id", ondelete="RESTRICT"), nullable=False)
    grade_id = Column(UUID(as_uuid=True), ForeignKey("grades.id"))
    score_type = Column(
        pg_enum(enums.ScoreType, "score_type_enum")
    )  # (legacy, nullable) — binding thật ở exam_column_mappings
    title = Column(String(500), nullable=False)
    description = Column(Text)
    file_url = Column(Text)
    file_type = Column(pg_enum(enums.FileType, "file_type_enum"), server_default=text("'PDF'"))
    file_size_bytes = Column(BigInteger)
    difficulty = Column(pg_enum(enums.Difficulty, "difficulty_enum"))
    difficulty_coefficient = Column(Numeric(3, 2), nullable=False, server_default=text("1.00"))
    num_questions = Column(SmallInteger)
    total_points = Column(Numeric(5, 2))
    topics = Column(ARRAY(Text))
    ai_analysis = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    # NOTE: tên cột là "metadata"; thuộc tính ORM đổi thành "meta" vì "metadata" bị Declarative chiếm dụng.
    meta = Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    # Tam giác hóa độ khó (TEVI): CDI tính từ exam_competencies (Bloom), NULL = chưa phân tích nội dung.
    content_difficulty = Column(Numeric(4, 3))
    content_analyzed_at = Column(DateTime(timezone=True))
    content_source = Column(pg_enum(enums.FileType, "file_type_enum"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=_NOW)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=_NOW)


class CurriculumUnit(Base):
    __tablename__ = "curriculum_units"
    __table_args__ = (
        CheckConstraint("grade_number BETWEEN 1 AND 12", name="grade_number_valid"),
        CheckConstraint("semester_number IN (1, 2)", name="curri_semester_number_valid"),
        UniqueConstraint("subject_id", "grade_number", "code", name="uq_curriculum_subject_grade_code"),
        Index("idx_curri_subject", "subject_id", "grade_number"),
        Index("idx_curri_parent", "parent_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=_UUID_PK)
    subject_id = Column(UUID(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    grade_number = Column(SmallInteger, nullable=False)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("curriculum_units.id", ondelete="CASCADE"))
    code = Column(String(50), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    # NULL = SGK không tách tập (dạy cả năm, vd KHTN); 1/2 = chỉ thuộc học kỳ đó (SGK tập 1/tập 2).
    semester_number = Column(SmallInteger)
    # False = ẩn khỏi picker (rác phân mảnh taxonomy cũ, còn bị exam_competencies tham chiếu
    # nên không xóa được) — KHÔNG liên quan quyền hạn, chỉ là cờ hiển thị.
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=_NOW)


class ExamCompetency(Base):
    __tablename__ = "exam_competencies"
    __table_args__ = (
        CheckConstraint("weight BETWEEN 0 AND 1", name="weight_range"),
        CheckConstraint("bloom_level BETWEEN 1 AND 6", name="bloom_level_range"),
        Index("idx_examcomp_unit", "unit_id"),
    )

    exam_paper_id = Column(UUID(as_uuid=True), ForeignKey("exam_papers.id", ondelete="CASCADE"), primary_key=True)
    unit_id = Column(UUID(as_uuid=True), ForeignKey("curriculum_units.id", ondelete="RESTRICT"), primary_key=True)
    weight = Column(Numeric(4, 3), nullable=False, server_default=text("0"))
    bloom_level = Column(SmallInteger)


# ============================================================
# NGÂN HÀNG CÂU HỎI & TẠO ĐỀ (AI Exam Generation — xem docs/exam_generation_design.md)
#   Hybrid: LLM+RAG sinh câu DRAFT -> duyệt người -> APPROVED -> ráp đề chính thức.
#   Ngân hàng (question_items) là "nguồn sự thật"; chỉ câu APPROVED mới được ráp.
# ============================================================


class QuestionItem(Base):
    __tablename__ = "question_items"
    __table_args__ = (
        CheckConstraint("grade_number BETWEEN 1 AND 12", name="qi_grade_number_valid"),
        CheckConstraint("bloom_level BETWEEN 1 AND 6", name="qi_bloom_level_valid"),
        CheckConstraint("default_points > 0", name="qi_points_positive"),
        Index("idx_qi_pick", "subject_id", "grade_number", "unit_id", "bloom_level", "status"),
        Index("idx_qi_school", "school_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=_UUID_PK)
    school_id = Column(UUID(as_uuid=True), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    subject_id = Column(UUID(as_uuid=True), ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=False)
    grade_number = Column(SmallInteger, nullable=False)
    unit_id = Column(UUID(as_uuid=True), ForeignKey("curriculum_units.id", ondelete="RESTRICT"), nullable=False)
    bloom_level = Column(SmallInteger, nullable=False)
    question_type = Column(pg_enum(enums.QuestionType, "question_type_enum"), nullable=False)
    stem = Column(Text, nullable=False)  # đề bài (Markdown/LaTeX)
    options = Column(JSONB)  # [{key:'A', text:..}]; NULL nếu tự luận
    answer_key = Column(JSONB, nullable=False)  # {correct:'B'} | {answer:.., rubric:..}
    solution = Column(Text)  # lời giải (cho người duyệt + lưu kho)
    default_points = Column(Numeric(4, 2), nullable=False, server_default=text("1.0"))
    status = Column(pg_enum(enums.ItemStatus, "item_status_enum"), nullable=False, server_default=text("'DRAFT'"))
    source = Column(
        pg_enum(enums.ItemSource, "item_source_enum"), nullable=False, server_default=text("'AI_GENERATED'")
    )
    provenance = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # {model, rag_sources, ...}
    # Thống kê thực nghiệm — cập nhật sau mỗi lần dùng (NULL = chưa dùng).
    times_used = Column(Integer, nullable=False, server_default=text("0"))
    p_value = Column(Numeric(4, 3))  # facility 0..1 (tỉ lệ làm đúng)
    discrimination = Column(Numeric(4, 3))
    exposure_at = Column(DateTime(timezone=True))  # lần cuối xuất hiện trong đề (chống lộ)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    reviewed_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=_NOW)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=_NOW)


class Misconception(Base):
    """Ngân hàng lỗi sai phổ biến của học sinh theo chủ đề — nguồn soạn distractor "trúng tim đen".

    MVP demo: seed mock (scripts/seed_misconceptions_toan.py). Tương lai: khai thác tự động từ
    thống kê bài làm (scores) — school_id NULL nghĩa là dùng chung mọi trường.
    """

    __tablename__ = "misconceptions"
    __table_args__ = (Index("idx_misconception_unit", "unit_id"),)

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=_UUID_PK)
    school_id = Column(UUID(as_uuid=True), ForeignKey("schools.id", ondelete="CASCADE"))
    subject_id = Column(UUID(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    unit_id = Column(UUID(as_uuid=True), ForeignKey("curriculum_units.id", ondelete="CASCADE"), nullable=False)
    grade_number = Column(SmallInteger, nullable=False)
    description = Column(Text, nullable=False)  # mô tả lỗi sai, vd "cộng tử với tử, mẫu với mẫu"
    example_wrong = Column(Text)  # ví dụ bài làm sai điển hình
    evidence_count = Column(Integer, nullable=False, server_default=text("0"))  # số bài làm ghi nhận lỗi
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=_NOW)


class ExamBlueprint(Base):
    __tablename__ = "exam_blueprints"
    __table_args__ = (
        CheckConstraint("grade_number BETWEEN 1 AND 12", name="bp_grade_number_valid"),
        CheckConstraint("total_points > 0", name="bp_total_points_positive"),
        Index("idx_bp_subject", "subject_id", "grade_number"),
        Index("idx_bp_school", "school_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=_UUID_PK)
    school_id = Column(UUID(as_uuid=True), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    subject_id = Column(UUID(as_uuid=True), ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=False)
    grade_number = Column(SmallInteger, nullable=False)
    score_category = Column(pg_enum(enums.ScoreCategory, "score_category_enum"), nullable=False)  # MIDTERM/FINAL
    title = Column(String(255), nullable=False)
    total_points = Column(Numeric(5, 2), nullable=False, server_default=text("10.0"))
    duration_min = Column(SmallInteger)
    target_difficulty = Column(Numeric(4, 3))  # độ khó mong muốn 0..1 (lái theo năng lực khối)
    # cells = [{unit_id, bloom_level, question_type, num_questions, points_each}, ...]
    cells = Column(JSONB, nullable=False)
    # Suy ra từ cells (question_type dùng) mỗi lần create/update — không nhận trực tiếp từ client.
    exam_format = Column(pg_enum(enums.ExamFormat, "exam_format_enum"))
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=_NOW)


class GeneratedExam(Base):
    __tablename__ = "generated_exams"
    __table_args__ = (
        CheckConstraint("num_variants BETWEEN 1 AND 20", name="ge_num_variants_valid"),
        Index("idx_ge_blueprint", "blueprint_id"),
        Index("idx_ge_school", "school_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=_UUID_PK)
    school_id = Column(UUID(as_uuid=True), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    blueprint_id = Column(UUID(as_uuid=True), ForeignKey("exam_blueprints.id", ondelete="RESTRICT"), nullable=False)
    semester_id = Column(UUID(as_uuid=True), ForeignKey("semesters.id", ondelete="RESTRICT"), nullable=False)
    grade_id = Column(UUID(as_uuid=True), ForeignKey("grades.id", ondelete="SET NULL"))
    num_variants = Column(SmallInteger, nullable=False, server_default=text("1"))
    status = Column(
        pg_enum(enums.GenExamStatus, "gen_exam_status_enum"), nullable=False, server_default=text("'DRAFT'")
    )
    # Bản ghi đề chính thức sinh ra khi FINALIZE (nối vào luồng chấm hiện có).
    exam_paper_id = Column(UUID(as_uuid=True), ForeignKey("exam_papers.id", ondelete="SET NULL"))
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=_NOW)


class GeneratedExamItem(Base):
    __tablename__ = "generated_exam_items"
    __table_args__ = (
        CheckConstraint("position >= 1", name="gei_position_valid"),
        Index("idx_gei_item", "item_id"),
    )

    generated_exam_id = Column(
        UUID(as_uuid=True), ForeignKey("generated_exams.id", ondelete="CASCADE"), primary_key=True
    )
    variant_code = Column(String(8), primary_key=True)  # mã đề: '101','102'...
    position = Column(SmallInteger, primary_key=True)
    item_id = Column(UUID(as_uuid=True), ForeignKey("question_items.id", ondelete="RESTRICT"), nullable=False)
    points = Column(Numeric(4, 2), nullable=False)
    option_order = Column(JSONB)  # thứ tự đáp án sau khi xáo (giữ map đáp án đúng)


# ============================================================
# SCORES
# ============================================================


class Score(Base):
    __tablename__ = "scores"
    __table_args__ = (
        CheckConstraint("value >= 0 AND value <= 10", name="value_range"),
        CheckConstraint("column_index >= 1", name="column_index_valid"),
        UniqueConstraint(
            "student_id",
            "subject_id",
            "semester_id",
            "score_category",
            "column_index",
            name="uq_score_unique",
        ),
        Index("idx_scores_student", "student_id"),
        Index("idx_scores_subject", "subject_id"),
        Index("idx_scores_semester", "semester_id"),
        Index("idx_scores_class", "class_id"),
        Index("idx_scores_category", "score_category"),
        Index("idx_scores_status", "status"),
        Index("idx_scores_exam", "exam_paper_id"),
        Index("idx_scores_compound", "subject_id", "semester_id", "score_category", "column_index"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=_UUID_PK)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="RESTRICT"), nullable=False)
    subject_id = Column(UUID(as_uuid=True), ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=False)
    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id", ondelete="RESTRICT"), nullable=False)
    semester_id = Column(UUID(as_uuid=True), ForeignKey("semesters.id", ondelete="RESTRICT"), nullable=False)
    score_category = Column(pg_enum(enums.ScoreCategory, "score_category_enum"), nullable=False)
    column_index = Column(SmallInteger, nullable=False)
    value = Column(Numeric(4, 2), nullable=False)
    exam_paper_id = Column(UUID(as_uuid=True), ForeignKey("exam_papers.id", ondelete="SET NULL"))
    status = Column(pg_enum(enums.ScoreStatus, "score_status_enum"), nullable=False, server_default=text("'DRAFT'"))
    note = Column(Text)
    entered_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    approved_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    approved_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=_NOW)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=_NOW)


# ============================================================
# EXAM COLUMN MAPPING (liên kết đề thi vào cột điểm)
# REGULAR (TX): map theo lớp (class_id). MIDTERM/FINAL: map theo khối (grade_id).
# ============================================================


class ExamColumnMapping(Base):
    __tablename__ = "exam_column_mappings"
    __table_args__ = (
        CheckConstraint(
            "(score_category = 'REGULAR' AND class_id IS NOT NULL AND grade_id IS NULL) OR "
            "(score_category IN ('MIDTERM','FINAL') AND grade_id IS NOT NULL AND class_id IS NULL)",
            name="mapping_scope_consistency",
        ),
        UniqueConstraint(
            "subject_id",
            "semester_id",
            "score_category",
            "column_index",
            "class_id",
            "grade_id",
            name="uq_exam_mapping",
            postgresql_nulls_not_distinct=True,
        ),
        Index("idx_mapping_subject_sem", "subject_id", "semester_id"),
        Index("idx_mapping_class", "class_id"),
        Index("idx_mapping_grade", "grade_id"),
        Index("idx_mapping_exam", "exam_paper_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=_UUID_PK)
    subject_id = Column(UUID(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    semester_id = Column(UUID(as_uuid=True), ForeignKey("semesters.id", ondelete="CASCADE"), nullable=False)
    score_category = Column(pg_enum(enums.ScoreCategory, "score_category_enum"), nullable=False)
    column_index = Column(SmallInteger, nullable=False)
    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id", ondelete="CASCADE"))
    grade_id = Column(UUID(as_uuid=True), ForeignKey("grades.id", ondelete="CASCADE"))
    exam_paper_id = Column(UUID(as_uuid=True), ForeignKey("exam_papers.id", ondelete="CASCADE"), nullable=False)
    mapped_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=_NOW)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=_NOW)


# ============================================================
# ĐÁNH GIÁ HỌC TẬP THEO MÔN (do GV bộ môn nhập)
#   - Môn SCORED: comment = nhận xét học tập của HS cho môn đó.
#   - Môn REMARK: result = Đạt/Chưa đạt (thay cho điểm số).
# ============================================================


class SubjectEvaluation(Base):
    __tablename__ = "subject_evaluations"
    __table_args__ = (
        UniqueConstraint("student_id", "subject_id", "semester_id", name="uq_subject_eval"),
        Index("idx_subjeval_class_sem", "class_id", "semester_id"),
        Index("idx_subjeval_subject", "subject_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=_UUID_PK)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    subject_id = Column(UUID(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id", ondelete="CASCADE"), nullable=False)
    semester_id = Column(UUID(as_uuid=True), ForeignKey("semesters.id", ondelete="CASCADE"), nullable=False)
    result = Column(pg_enum(enums.PassFail, "pass_fail_enum"))  # cho môn REMARK
    comment = Column(Text)  # đánh giá học tập (môn SCORED)
    evaluated_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=_NOW)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=_NOW)


# ============================================================
# PHIẾU TỔNG KẾT HỌC KỲ (do GV chủ nhiệm nhập): hạnh kiểm + đánh giá chung
# ============================================================


class StudentTermReport(Base):
    __tablename__ = "student_term_reports"
    __table_args__ = (
        UniqueConstraint("student_id", "class_id", "semester_id", name="uq_term_report"),
        Index("idx_termreport_class_sem", "class_id", "semester_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=_UUID_PK)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id", ondelete="CASCADE"), nullable=False)
    semester_id = Column(UUID(as_uuid=True), ForeignKey("semesters.id", ondelete="CASCADE"), nullable=False)
    conduct = Column(pg_enum(enums.Conduct, "conduct_enum"))  # hạnh kiểm
    general_comment = Column(Text)  # đánh giá chung của chủ nhiệm
    absent_days = Column(Integer, server_default=text("0"), default=0)  # số ngày nghỉ
    evaluated_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=_NOW)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=_NOW)


# ============================================================
# AUDIT LOG
# ============================================================


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        CheckConstraint("action IN ('INSERT', 'UPDATE', 'DELETE')", name="action_valid"),
        Index("idx_audit_table", "table_name", "record_id"),
        Index("idx_audit_time", "changed_at"),
        Index("idx_audit_user", "changed_by"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=_UUID_PK)
    table_name = Column(String(100), nullable=False)
    record_id = Column(UUID(as_uuid=True), nullable=False)
    action = Column(String(10), nullable=False)
    changed_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    old_values = Column(JSONB)
    new_values = Column(JSONB)
    ip_address = Column(INET)
    user_agent = Column(Text)
    changed_at = Column(DateTime(timezone=True), nullable=False, server_default=_NOW)


# ============================================================
# THÔNG BÁO (sự kiện hệ thống tự động + thông báo chủ động do người soạn)
# ============================================================


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("idx_notif_recipient", "recipient_id", "read_at"),
        Index("idx_notif_school", "so_school_id"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    so_school_id = Column(Integer, nullable=False)
    recipient_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    sender_id = Column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    type = Column(pg_enum(enums.NotificationType, "notification_type_enum"), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    entity_type = Column(String(50))
    entity_id = Column(BigInteger)
    read_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=_NOW)



# ============================================================
# AI CHAT SESSIONS
# ============================================================


class AiSession(Base):
    __tablename__ = "ai_sessions"
    __table_args__ = (Index("idx_session_user", "user_id"),)

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=_UUID_PK)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(500))
    context_filter = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=_NOW)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=_NOW)


class AiMessage(Base):
    __tablename__ = "ai_messages"
    __table_args__ = (
        Index("idx_message_session", "session_id"),
        CheckConstraint("rating IN (1, -1)", name="chk_aimessage_rating"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey("ai_sessions.id", ondelete="CASCADE"), nullable=False)
    role = Column(pg_enum(enums.AiSessionRole, "ai_session_role_enum"), nullable=False)
    content = Column(Text, nullable=False)
    generated_sql = Column(Text)
    guardrail_status = Column(pg_enum(enums.GuardrailStatus, "guardrail_status_enum"))
    token_count = Column(Integer)
    sources = Column(JSONB)
    model_used = Column(String(100))
    latency_ms = Column(Integer)

    # Telemetry and Feedback columns
    rating = Column(SmallInteger)
    feedback_tag = Column(String(100))
    feedback_text = Column(Text)
    feedback_at = Column(DateTime(timezone=True))
    thought_trace = Column(JSONB)
    step_trace = Column(JSONB)
    input_token_count = Column(Integer)
    output_token_count = Column(Integer)
    cost = Column(Numeric(10, 6))
    llm_provider = Column(String(50))

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=_NOW)


# ============================================================
# SCHEDULED REPORTS
# ============================================================


class ReportSchedule(Base):
    __tablename__ = "report_schedules"
    __table_args__ = (
        CheckConstraint(
            "report_type IN ('school_overview','grade','subject','class','at_risk')",
            name="report_type_valid",
        ),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    created_by = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    report_type = Column(String(50), nullable=False)
    filter_params = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    cron_expr = Column(String(100), nullable=False)
    recipients = Column(ARRAY(Text), nullable=False)
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    last_run_at = Column(DateTime(timezone=True))
    next_run_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=_NOW)


# ============================================================
# AGENTOPS OBSERVABILITY
# ============================================================


class AiObservabilitySnapshot(Base):
    __tablename__ = "ai_observability_snapshots"
    __table_args__ = (Index("idx_observability_captured_at", "captured_at"),)

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    captured_at = Column(DateTime(timezone=True), nullable=False, server_default=_NOW)
    daily_cost_usd = Column(Numeric(10, 6), nullable=False, server_default=text("0"))
    daily_budget_usd = Column(Numeric(10, 2), nullable=False)
    latency_p95_ms = Column(Integer)
    ttft_p95_ms = Column(Integer)
    faithfulness_avg = Column(Numeric(4, 3))
    groundedness_avg = Column(Numeric(4, 3))
    tool_success_rate = Column(Numeric(4, 3))
    total_requests = Column(Integer, nullable=False, server_default=text("0"))
    total_tokens_in = Column(BigInteger, nullable=False, server_default=text("0"))
    total_tokens_out = Column(BigInteger, nullable=False, server_default=text("0"))
    agent_routes = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    agent_step_p95_ms = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))



# ============================================================
# ĐÍNH KÈM FILE TRONG CHAT (AI đọc nội dung) — gắn theo session, nội dung trích xuất
# được chèn vào MỌI lượt hỏi tiếp theo trong cùng session (không phụ thuộc cửa sổ
# lịch sử 10 tin nhắn của chat_repo.get_session_messages)
# ============================================================


class AiSessionAttachment(Base):
    __tablename__ = "ai_session_attachments"
    __table_args__ = (Index("idx_attachment_session", "session_id"),)

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey("ai_sessions.id", ondelete="CASCADE"), nullable=False)
    uploaded_by = Column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    file_name = Column(String(255), nullable=False)
    stored_name = Column(String(255), nullable=False)
    file_type = Column(pg_enum(enums.FileType, "file_type_enum"), nullable=False)
    extracted_text = Column(Text)
    char_count = Column(Integer, nullable=False, server_default=text("0"))
    truncated = Column(Boolean, nullable=False, server_default=text("false"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=_NOW)



# ============================================================
# CLASSROOM RECORDINGS (Ghi âm bài giảng và đánh giá AI)
# ============================================================


class ClassroomRecording(Base):
    __tablename__ = "classroom_recordings"
    __table_args__ = (
        Index("idx_recordings_teacher", "teacher_id"),
        Index("idx_recordings_class", "class_id"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    so_school_id = Column(Integer, nullable=False)
    teacher_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    subject_id = Column(Integer, nullable=False)
    class_id = Column(Integer, nullable=False)
    semester_id = Column(Integer, nullable=False)


    lesson_name = Column(String(255), nullable=False)
    period = Column(Integer, nullable=False)  # Tiết học (ví dụ: 1, 2, 3...)
    date = Column(Date, nullable=False)  # Ngày dạy học
    week = Column(Integer, nullable=False)  # Tuần học

    audio_file_url = Column(Text, nullable=False)  # URL lưu trữ cloud trên Supabase
    status = Column(
        String(50), nullable=False, server_default=text("'pending'")
    )  # 'pending', 'processing', 'done', 'failed'
    progress = Column(Integer, nullable=False, server_default=text("0"))  # % tiến trình (0-100)

    # Kết quả phân tích AI
    score = Column(Numeric(3, 1))  # Điểm số 0.0 - 10.0
    engagement = Column(String(20))  # Tỷ lệ tương tác (ví dụ: "85%")
    rank = Column(pg_enum(enums.RecordingRank, "recording_rank_enum"))  # EXCELLENT, SATISFACTORY, NEEDS_IMPROVEMENT
    ai_report = Column(Text)  # Nhận xét chi tiết dạng Markdown
    transcript = Column(JSONB)  # Mảng các segments [{'time': 'MM:SS', 'speaker': str, 'text': str}]

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=_NOW)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=_NOW)


# ============================================================
# DYNAMIC ENTITY RESOLUTION METADATA INDEX (s360.metadata_index)
# ============================================================


class MetadataIndex(Base):
    __tablename__ = "metadata_index"
    __table_args__ = (
        Index("idx_meta_trgm", "entity_name", postgresql_using="gin", postgresql_ops={"entity_name": "gin_trgm_ops"}),
        Index("idx_meta_school", "so_school_id", "entity_type"),
        {"schema": "s360"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    so_school_id = Column(Integer, nullable=False)
    entity_type = Column(String(50), nullable=False)
    entity_name = Column(String(255), nullable=False)
    exact_code = Column(String(100))
    exact_id = Column(BigInteger, nullable=False)
    extra_metadata = Column(JSONB)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=_NOW)

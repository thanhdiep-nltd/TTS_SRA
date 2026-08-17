"""SQLAlchemy ORM models — phản ánh schema s360 (score_focused_schema.sql).

Tập trung vào các bảng DWH `s360` cho Student Risk Alert (SRA) — dùng bởi
Report Agent để tổng hợp báo cáo học đường. Tất cả PK dùng BIGINT/INTEGER
(không UUID) theo merged schema mới.
"""

from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    text,
)
from sqlalchemy import Enum as SAEnum

from src.db.base import Base
from src.models import enums

_NOW = text("now()")


def pg_enum(py_enum, name: str) -> SAEnum:
    """Map Python enum sang PG enum, lưu theo .value, không tự tạo type."""
    return SAEnum(
        py_enum,
        name=name,
        values_callable=lambda e: [m.value for m in e],
        create_type=False,
    )


class DimSchoolYear(Base):
    __tablename__ = "dim_school_year"
    __table_args__ = {"schema": "s360"}

    id = Column(Integer, primary_key=True)
    code = Column(String(50), nullable=False)
    fullname = Column(String(100), nullable=False)
    start_date = Column(Date)
    end_date = Column(Date)
    is_current = Column(Integer, default=0)
    is_locked = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=_NOW)
    updated_at = Column(DateTime(timezone=True), server_default=_NOW)
    source_system = Column(String(50), default="SCHOOL_ONLINE")


class DimHomeroomClass(Base):
    __tablename__ = "dim_homeroom_class"
    __table_args__ = {"schema": "s360"}

    id = Column(BigInteger, primary_key=True)
    so_school_id = Column(Integer, nullable=False)
    school_year_id = Column(Integer, ForeignKey("s360.dim_school_year.id"), nullable=False)
    grade_id = Column(Integer, nullable=False)
    code = Column(String(50), nullable=False)
    fullname = Column(String(100), nullable=False)
    homeroom_teacher_id = Column(BigInteger)
    teacher_code = Column(String(50))
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=_NOW)
    updated_at = Column(DateTime(timezone=True), server_default=_NOW)
    source_system = Column(String(50), default="SCHOOL_ONLINE")


class DimHomeroomClassStudent(Base):
    __tablename__ = "dim_homeroom_class_student"
    __table_args__ = {"schema": "s360"}

    id = Column(BigInteger, primary_key=True)
    so_student_id = Column(BigInteger, nullable=False)
    student_code = Column(String(50), nullable=False)
    student_name = Column(String(255), nullable=False)
    homeroom_class_id = Column(Integer, nullable=False)
    class_code = Column(String(50))
    class_name = Column(String(100))
    so_school_id = Column(Integer, nullable=False)
    school_year_id = Column(Integer, nullable=False)
    school_name = Column(String(255))
    teacher_code = Column(String(50))
    grade_id = Column(Integer, nullable=False)
    grade_name = Column(String(50))
    moet_code = Column(String(50))
    join_date = Column(Date)
    is_graduated = Column(Integer, default=0)
    status = Column(Integer, default=1)
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=_NOW)
    updated_at = Column(DateTime(timezone=True), server_default=_NOW)
    source_system = Column(String(50), default="SCHOOL_ONLINE")


class DimSubject(Base):
    __tablename__ = "dim_subject"
    __table_args__ = {"schema": "s360"}

    id = Column(Integer, primary_key=True)
    code = Column(String(50), nullable=False)
    name = Column(String(255), nullable=False)
    name_en = Column(String(255))
    subject_type = Column(String(50), default="CORE")
    subject_category = Column(String(50), default="MATH_SCIENCE")
    assessment_type = Column(
        pg_enum(enums.AssessmentType, "assessment_type_enum"),
        nullable=False,
        server_default=text("'SCORED'"),
    )
    default_scale_name = Column(String(50), nullable=False, server_default=text("'SCALE_10'"))
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=_NOW)
    updated_at = Column(DateTime(timezone=True), server_default=_NOW)
    source_system = Column(String(50), default="SCHOOL_ONLINE")


class DimExam(Base):
    __tablename__ = "dim_exam"
    __table_args__ = {"schema": "s360"}

    id = Column(BigInteger, primary_key=True)
    so_exam_id = Column(BigInteger)
    school_year_id = Column(Integer, nullable=False)
    subject_id = Column(Integer, ForeignKey("s360.dim_subject.id"), nullable=False)
    grade_id = Column(Integer, nullable=False)
    exam_code = Column(String(50))
    exam_name = Column(String(255), nullable=False)
    coefficient = Column(Numeric(10, 1), default=1.0)
    moet_semester_index = Column(Integer)
    max_grade = Column(Numeric(10, 1), default=10.0)
    is_periodic_exam = Column(Integer, default=0)
    is_moet = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=_NOW)
    updated_at = Column(DateTime(timezone=True), server_default=_NOW)


class FactGradebooks(Base):
    __tablename__ = "fact_gradebooks"
    __table_args__ = {"schema": "s360"}

    id = Column(BigInteger, primary_key=True)
    so_school_id = Column(Integer, nullable=False)
    school_year_id = Column(Integer, ForeignKey("s360.dim_school_year.id"), nullable=False)
    semester_index = Column(Integer, nullable=False)
    student_code = Column(String(50), nullable=False)
    homeroom_class_id = Column(Integer, nullable=False)
    subject_id = Column(Integer, ForeignKey("s360.dim_subject.id"), nullable=False)
    so_exam_id = Column(BigInteger, ForeignKey("s360.dim_exam.id"))
    final_grade = Column(Numeric(10, 2))
    final_grade_percent = Column(Numeric(5, 2))
    final_grade_letter = Column(String(10))
    pass_fail_status = Column(pg_enum(enums.PassFail, "pass_fail_enum"))
    scale_name_used = Column(String(50), default="SCALE_10")
    max_grade = Column(Numeric(10, 1), default=10.0)
    is_locked = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=_NOW)
    updated_at = Column(DateTime(timezone=True), server_default=_NOW)
    source_system = Column(String(50), default="SCHOOL_ONLINE")


class FactOverallAcademicRecords(Base):
    __tablename__ = "fact_overall_academic_records"
    __table_args__ = {"schema": "s360"}

    id = Column(BigInteger, primary_key=True)
    so_school_id = Column(Integer, nullable=False)
    school_year_id = Column(Integer, ForeignKey("s360.dim_school_year.id"), nullable=False)
    grade_id = Column(Integer, nullable=False)
    homeroom_class_id = Column(Integer, nullable=False)
    student_id = Column(BigInteger, nullable=False)
    student_code = Column(String(50), nullable=False)
    final_grade = Column(Numeric(10, 1))
    s1_final_grade = Column(Numeric(10, 1))
    s2_final_grade = Column(Numeric(10, 1))
    conduct = Column(pg_enum(enums.Conduct, "conduct_enum"))
    s1_conduct = Column(pg_enum(enums.Conduct, "conduct_enum"))
    s2_conduct = Column(pg_enum(enums.Conduct, "conduct_enum"))
    learning_capacity = Column(String(50))
    s1_learning_capacity = Column(String(50))
    s2_learning_capacity = Column(String(50))
    final_behavior_point = Column(Integer)
    day_of_absent = Column(Integer, default=0)
    s1_day_of_absent = Column(Integer, default=0)
    s2_day_of_absent = Column(Integer, default=0)
    homeroom_teacher_comment = Column(Text)
    principal_comment = Column(Text)
    is_passed_no_conditional = Column(Integer, default=1)
    is_graduated = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=_NOW)
    updated_at = Column(DateTime(timezone=True), server_default=_NOW)


class FactSubjectAcademicRecords(Base):
    __tablename__ = "fact_subject_academic_records"
    __table_args__ = {"schema": "s360"}

    id = Column(BigInteger, primary_key=True)
    overall_record_id = Column(BigInteger)
    subject_id = Column(Integer, ForeignKey("s360.dim_subject.id"), nullable=False)
    student_code = Column(String(50), nullable=False)
    final_grade = Column(Numeric(10, 1))
    s1_final_grade = Column(Numeric(10, 1))
    s2_final_grade = Column(Numeric(10, 1))
    final_grade_after_summer = Column(Numeric(10, 1))
    created_at = Column(DateTime(timezone=True), server_default=_NOW)
    updated_at = Column(DateTime(timezone=True), server_default=_NOW)


class DimSoAssignment(Base):
    """Danh mục bài tập / nhiệm vụ học tập LMS (s360.dim_so_assignment)."""

    __tablename__ = "dim_so_assignment"
    __table_args__ = {"schema": "s360"}

    assignment_id = Column(BigInteger, primary_key=True)
    so_school_id = Column(Integer, nullable=False)
    grade_id = Column(Integer, nullable=False)
    semester_index = Column(Integer)
    subject_id = Column(Integer, ForeignKey("s360.dim_subject.id"), nullable=False)
    code = Column(String(50))
    fullname = Column(String(255), nullable=False)
    max_grade = Column(Numeric(10, 1), default=10.0)
    due_date = Column(Date)
    date_assigned = Column(Date)
    gradebook_type_item_id = Column(BigInteger)
    # M0.1: bổ sung cấu hình thời gian cho lọc nhiễu off-task/rapid-guess.
    allow_attempts = Column(Integer, default=1)
    time_limit_sec = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=_NOW)
    updated_at = Column(DateTime(timezone=True), server_default=_NOW)
    source_system = Column(String(50), default="LMS")


class FactSoAssignmentGrade(Base):
    """Điểm bài tập LMS chi tiết (s360.fact_so_assignment_grade)."""

    __tablename__ = "fact_so_assignment_grade"
    __table_args__ = {"schema": "s360"}

    id = Column(BigInteger, primary_key=True)
    so_school_id = Column(Integer, nullable=False)
    assignment_id = Column(BigInteger, ForeignKey("s360.dim_so_assignment.assignment_id"), nullable=False)
    user_id = Column(BigInteger)
    student_code = Column(String(50), nullable=False)
    final_grade = Column(Numeric(10, 1))
    comment = Column(Text)
    is_locked = Column(Integer, default=0)
    # M0.1: hành vi làm bài LMS (lọc nhiễu off-task/rapid-guess).
    started_at = Column(DateTime(timezone=True))
    submitted_at = Column(DateTime(timezone=True))
    attempt_count = Column(Integer, default=1)
    time_spent_sec = Column(Integer)  # tổng thời gian (thô)
    active_time_sec = Column(Integer)  # thời gian tương tác THỰC (đã loại treo máy)
    tab_hidden_count = Column(Integer, default=0)
    idle_sec = Column(Integer, default=0)
    rte = Column(SmallInteger)  # Response Time Effort: 1=effortful, 0=rapid-guess/off-task
    created_at = Column(DateTime(timezone=True), server_default=_NOW)
    updated_at = Column(DateTime(timezone=True), server_default=_NOW)
    source_system = Column(String(50), default="LMS")

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from src.models import enums
from src.schemas.common import ORMBase

# ============================================================
# AcademicYear
# ============================================================


class AcademicYearCreate(BaseModel):
    school_id: UUID
    name: str = Field(max_length=20)
    start_date: date
    end_date: date
    is_current: bool = False


class AcademicYearUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=20)
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool | None = None


class AcademicYearRead(ORMBase):
    id: UUID
    school_id: UUID
    name: str
    start_date: date
    end_date: date
    is_current: bool
    created_at: datetime


# ============================================================
# Semester
# ============================================================


class SemesterCreate(BaseModel):
    academic_year_id: UUID
    name: str = Field(max_length=10)
    number: int = Field(ge=1, le=2)
    start_date: date
    end_date: date
    is_current: bool = False


class SemesterUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=10)
    number: int | None = Field(default=None, ge=1, le=2)
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool | None = None


class SemesterRead(ORMBase):
    id: UUID
    academic_year_id: UUID
    name: str
    number: int
    start_date: date
    end_date: date
    is_current: bool


# ============================================================
# Grade
# ============================================================


class GradeCreate(BaseModel):
    school_id: UUID
    name: str = Field(max_length=20)
    grade_number: int = Field(ge=1, le=12)
    school_level: enums.SchoolLevel


class GradeUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=20)
    grade_number: int | None = Field(default=None, ge=1, le=12)
    school_level: enums.SchoolLevel | None = None


class GradeRead(ORMBase):
    id: UUID
    school_id: UUID
    name: str
    grade_number: int
    school_level: enums.SchoolLevel
    created_at: datetime


# ============================================================
# Class
# ============================================================


class ClassCreate(BaseModel):
    grade_id: UUID
    name: str = Field(max_length=20)
    academic_year_id: UUID
    student_count: int = 0


class ClassUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=20)
    student_count: int | None = None


class ClassRead(ORMBase):
    id: UUID
    grade_id: UUID
    name: str
    academic_year_id: UUID
    student_count: int | None
    created_at: datetime


# ============================================================
# Subject
# ============================================================


class SubjectCreate(BaseModel):
    school_id: UUID
    name: str = Field(max_length=100)
    code: str = Field(max_length=20)
    applicable_level: enums.SchoolLevel = enums.SchoolLevel.ALL
    assessment_type: enums.AssessmentType = enums.AssessmentType.SCORED
    subject_head_id: UUID | None = None
    is_active: bool = True


class SubjectUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    code: str | None = Field(default=None, max_length=20)
    applicable_level: enums.SchoolLevel | None = None
    assessment_type: enums.AssessmentType | None = None
    subject_head_id: UUID | None = None
    is_active: bool | None = None


class SubjectRead(ORMBase):
    id: UUID
    school_id: UUID
    name: str
    code: str
    applicable_level: enums.SchoolLevel
    assessment_type: enums.AssessmentType
    subject_head_id: UUID | None
    is_active: bool
    created_at: datetime


# ============================================================
# CurriculumUnit (chuẩn chương trình — chủ đề/chương dùng cho ngân hàng câu hỏi)
# ============================================================


class CurriculumUnitCreate(BaseModel):
    subject_id: UUID
    grade_number: int = Field(ge=1, le=12)
    parent_id: UUID | None = None
    code: str = Field(max_length=50)
    name: str = Field(max_length=255)
    description: str | None = None
    semester_number: int | None = Field(default=None, ge=1, le=2)  # NULL = SGK không tách tập, dạy cả năm


class CurriculumUnitUpdate(BaseModel):
    parent_id: UUID | None = None
    code: str | None = Field(default=None, max_length=50)
    name: str | None = Field(default=None, max_length=255)
    description: str | None = None
    semester_number: int | None = Field(default=None, ge=1, le=2)
    is_active: bool | None = None


class CurriculumUnitRead(ORMBase):
    id: UUID
    subject_id: UUID
    grade_number: int
    parent_id: UUID | None
    code: str
    name: str
    description: str | None
    semester_number: int | None
    is_active: bool
    created_at: datetime
    # Làm giàu nội dung khi nạp sách giáo khoa (quét toàn cuốn) — picker không bắt buộc dùng.
    summary: str | None = None
    keywords: list[str] | None = None
    sections: list[dict] | None = None

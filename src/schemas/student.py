from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from src.schemas.common import ORMBase

Gender = Literal["MALE", "FEMALE", "OTHER"]


# ============================================================
# Student
# ============================================================


class StudentCreate(BaseModel):
    school_id: UUID
    student_code: str = Field(max_length=20)
    full_name: str = Field(max_length=255)
    date_of_birth: date | None = None
    gender: Gender | None = None
    is_active: bool = True


class StudentUpdate(BaseModel):
    student_code: str | None = Field(default=None, max_length=20)
    full_name: str | None = Field(default=None, max_length=255)
    date_of_birth: date | None = None
    gender: Gender | None = None
    is_active: bool | None = None


class StudentRead(ORMBase):
    id: UUID
    school_id: UUID
    student_code: str
    full_name: str
    date_of_birth: date | None
    gender: Gender | None
    is_active: bool
    created_at: datetime


# ============================================================
# Enrollment
# ============================================================


class EnrollmentCreate(BaseModel):
    student_id: UUID
    class_id: UUID
    academic_year_id: UUID
    enrolled_at: date | None = None
    is_active: bool = True


class EnrollmentUpdate(BaseModel):
    class_id: UUID | None = None
    is_active: bool | None = None


class EnrollmentRead(ORMBase):
    id: UUID
    student_id: UUID
    class_id: UUID
    academic_year_id: UUID
    enrolled_at: date
    is_active: bool

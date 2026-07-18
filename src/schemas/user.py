from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from src.models import enums
from src.schemas.common import ORMBase


class UserCreate(BaseModel):
    school_id: UUID
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    full_name: str = Field(max_length=255)
    role: enums.UserRole
    school_level: enums.SchoolLevel = enums.SchoolLevel.ALL
    phone: str | None = Field(default=None, max_length=20)
    subject_id: UUID | None = None  # môn phụ trách (chuyên môn của GV)


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    role: enums.UserRole | None = None
    school_level: enums.SchoolLevel | None = None
    phone: str | None = Field(default=None, max_length=20)
    subject_id: UUID | None = None
    is_active: bool | None = None


class UserRead(ORMBase):
    id: UUID
    school_id: UUID
    school_name: str | None = None
    principal_name: str | None = None
    email: EmailStr
    full_name: str
    role: enums.UserRole
    school_level: enums.SchoolLevel
    phone: str | None
    subject_id: UUID | None
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime
    homeroom_class_id: UUID | None = None


class AssignmentCreate(BaseModel):
    user_id: UUID
    academic_year_id: UUID
    role_context: enums.RoleContext
    class_id: UUID | None = None
    grade_id: UUID | None = None
    subject_id: UUID | None = None


class AssignmentRead(ORMBase):
    id: UUID
    user_id: UUID
    academic_year_id: UUID
    role_context: enums.RoleContext
    class_id: UUID | None
    grade_id: UUID | None
    subject_id: UUID | None
    is_active: bool


class UserListParams(BaseModel):
    """Tham số lọc/phân trang danh sách user (dùng qua Depends)."""

    q: str | None = None
    role: enums.UserRole | None = None
    is_active: bool | None = None
    school_id: UUID | None = None
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)


class UserListPage(BaseModel):
    """Trang kết quả danh sách user."""

    items: list[UserRead]
    total: int


class UserUpdateResult(UserRead):
    """Kết quả PATCH user — kèm số phân công bị vô hiệu do đổi vai trò."""

    deactivated_assignments: int = 0


class PasswordResetPayload(BaseModel):
    new_password: str = Field(min_length=6, max_length=128)


class OptionItem(BaseModel):
    """Một lựa chọn dropdown (id + tên)."""

    id: UUID
    name: str
    is_current: bool = False


class ClassOption(BaseModel):
    id: UUID
    name: str
    academic_year_id: UUID


class AssignmentOptions(BaseModel):
    """Dữ liệu dropdown cho form phân công của 1 GV — theo trường của GV đó."""

    allowed_contexts: list[enums.RoleContext]
    years: list[OptionItem]
    classes: list[ClassOption]
    grades: list[OptionItem]
    subjects: list[OptionItem]


class SubjectCoverage(BaseModel):
    subject_id: UUID
    name: str
    teacher_name: str | None


class ClassCoverage(BaseModel):
    """Độ phủ phân công của 1 lớp trong 1 niên khóa."""

    class_id: UUID
    name: str
    grade_name: str
    homeroom_teacher: str | None
    subjects: list[SubjectCoverage]


class CoverageFilter(BaseModel):
    """Bộ lọc tab 'Theo lớp': trường + các niên khóa của trường."""

    school_id: UUID
    school_name: str
    years: list[OptionItem]


class TeacherOption(BaseModel):
    """1 GV trong danh sách picker phân công (tab 'Theo lớp')."""

    id: UUID
    full_name: str
    subject_id: UUID | None

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from src.models import enums
from src.schemas.common import ORMBase


class ScoreCreate(BaseModel):
    student_id: UUID
    subject_id: UUID
    class_id: UUID
    semester_id: UUID
    score_category: enums.ScoreCategory
    column_index: int = Field(ge=1, le=10)
    value: float = Field(ge=0, le=10)
    exam_paper_id: UUID | None = None
    status: enums.ScoreStatus = enums.ScoreStatus.DRAFT
    note: str | None = None
    # entered_by KHÔNG nhận từ client — server gán theo user đăng nhập.


class ScoreUpdate(BaseModel):
    value: float | None = Field(default=None, ge=0, le=10)
    status: enums.ScoreStatus | None = None
    note: str | None = None
    approved_by: UUID | None = None


class ScoreRead(ORMBase):
    id: UUID
    student_id: UUID
    subject_id: UUID
    class_id: UUID
    semester_id: UUID
    score_category: enums.ScoreCategory
    column_index: int
    value: float
    exam_paper_id: UUID | None
    status: enums.ScoreStatus
    note: str | None
    entered_by: UUID
    approved_by: UUID | None
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ScoreBatchCreate(BaseModel):
    items: list[ScoreCreate] = Field(min_length=1, max_length=1000)


class ScoreImportRecord(BaseModel):
    student_id: UUID
    score_category: enums.ScoreCategory
    column_index: int = Field(ge=1, le=10)
    value: float | None = Field(default=None, ge=0, le=10)


class ScoreImportConfirmRequest(BaseModel):
    class_id: UUID
    subject_id: UUID
    semester_id: UUID
    records: list[ScoreImportRecord] = Field(min_length=1)

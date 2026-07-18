from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from src.models import enums
from src.schemas.common import ORMBase


class ClassroomRecordingCreate(BaseModel):
    subject_id: UUID
    class_id: UUID
    semester_id: UUID
    lesson_name: str = Field(..., max_length=255)
    period: int = Field(..., ge=1, le=15)
    date: date
    week: int = Field(..., ge=1, le=52)


class ClassroomRecordingRead(ORMBase):
    id: UUID
    school_id: UUID
    teacher_id: UUID
    teacher_name: str | None = None
    subject_id: UUID
    subject_name: str | None = None
    class_id: UUID
    class_name: str | None = None
    semester_id: UUID
    lesson_name: str
    period: int
    date: date
    week: int
    audio_file_url: str
    status: str
    progress: int
    score: float | None = None
    engagement: str | None = None
    rank: enums.RecordingRank | None = None
    ai_report: str | None = None
    transcript: list[dict] | None = None
    created_at: datetime
    updated_at: datetime


class ClassroomRecordingList(ORMBase):
    id: UUID
    school_id: UUID
    teacher_id: UUID
    teacher_name: str | None = None
    subject_id: UUID
    subject_name: str | None = None
    class_id: UUID
    class_name: str | None = None
    semester_id: UUID
    lesson_name: str
    period: int
    date: date
    week: int
    audio_file_url: str
    status: str
    progress: int
    score: float | None = None
    engagement: str | None = None
    rank: enums.RecordingRank | None = None
    created_at: datetime


class CameraExtractRequest(BaseModel):
    teacher_id: UUID
    subject_id: UUID
    class_id: UUID
    semester_id: UUID
    lesson_name: str = Field(..., max_length=255)
    period: int = Field(..., ge=1, le=15)
    date: date
    week: int = Field(..., ge=1, le=52)


class CameraWebhookPayload(BaseModel):
    cam_id: str
    from_time: str = Field(..., alias="from")
    audioUrl: str  # noqa: N815 - khớp đúng tên field JSON từ webhook camera ngoài, không đổi được
    status: str

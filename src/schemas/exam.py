from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from src.models import enums
from src.schemas.common import ORMBase


class ExamPaperRead(ORMBase):
    id: UUID
    subject_id: UUID
    semester_id: UUID
    grade_id: UUID | None
    title: str
    description: str | None
    file_type: enums.FileType | None
    file_size_bytes: int | None
    uploaded_by: UUID
    created_at: datetime
    # Độ khó nội dung (CDI, TEVI) — LLM phân tích chạy nền, content_analyzed_at null = chưa xong.
    # Dùng để FE poll RIÊNG endpoint này (GET /exam-papers/{id}) thay vì load lại cả bảng điểm.
    content_difficulty: float | None = None
    content_analyzed_at: datetime | None = None


class ExamPaperDetailRead(ExamPaperRead):
    """Chi tiết 1 đề: thêm ai_analysis (khối content_analysis = phân tích RAG-anchored CDI)."""

    ai_analysis: dict = {}


class MappingCreate(BaseModel):
    subject_id: UUID
    semester_id: UUID
    score_category: enums.ScoreCategory
    column_index: int = Field(ge=1, le=10)
    exam_paper_id: UUID
    class_id: UUID | None = None  # cho REGULAR (TX)
    grade_id: UUID | None = None  # cho MIDTERM/FINAL


class MappingRead(ORMBase):
    id: UUID
    subject_id: UUID
    semester_id: UUID
    score_category: enums.ScoreCategory
    column_index: int
    class_id: UUID | None
    grade_id: UUID | None
    exam_paper_id: UUID
    mapped_by: UUID | None
    created_at: datetime

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from src.models import enums
from src.schemas.common import ORMBase


class ExamPaperRead(ORMBase):
    id: int
    subject_id: int
    semester_id: int
    grade_id: int | None
    title: str
    description: str | None
    file_type: enums.FileType | None
    file_size_bytes: int | None
    uploaded_by: int
    created_at: datetime
    # Độ khó nội dung (CDI, TEVI) — LLM phân tích chạy nền, content_analyzed_at null = chưa xong.
    # Dùng để FE poll RIÊNG endpoint này (GET /exam-papers/{id}) thay vì load lại cả bảng điểm.
    content_difficulty: float | None = None
    content_analyzed_at: datetime | None = None


class ExamPaperDetailRead(ExamPaperRead):
    """Chi tiết 1 đề: thêm ai_analysis (khối content_analysis = phân tích RAG-anchored CDI)."""

    ai_analysis: dict = {}


class MappingCreate(BaseModel):
    subject_id: int | UUID
    semester_id: int | UUID
    score_category: enums.ScoreCategory
    column_index: int = Field(ge=1, le=10)
    exam_paper_id: int
    class_id: UUID | int | None = None  # cho REGULAR (TX)
    grade_id: UUID | int | None = None  # cho MIDTERM/FINAL


class MappingRead(ORMBase):
    id: UUID | int
    subject_id: int | UUID
    semester_id: int | UUID
    score_category: enums.ScoreCategory
    column_index: int
    class_id: UUID | int | None
    grade_id: UUID | int | None
    exam_paper_id: int
    mapped_by: int | None
    created_at: datetime

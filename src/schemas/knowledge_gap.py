"""src/schemas/knowledge_gap.py — DTO cho API lỗ hổng kiến thức (M2)."""

from pydantic import BaseModel, Field


class KnowledgeGapItem(BaseModel):
    """1 unit hổng của 1 học sinh."""

    unit_id: int
    unit_name: str | None = None
    chapter: str | None = None
    lesson: str | None = None
    gap_score: float = Field(..., description="0..1, cao = hổng nặng")
    mastery: float = Field(..., description="0..1, mức thành thạo")
    evidence_source: str | None = None  # 'EXAM' | 'LMS' | 'HYBRID' | 'PRIOR'
    evidence_detail: dict | None = None


class StudentKnowledgeGaps(BaseModel):
    """Danh sách unit hổng của 1 học sinh."""

    student_code: str
    subject_id: int
    school_year_id: int
    semester_index: int
    gaps: list[KnowledgeGapItem] = Field(default_factory=list)


class ClassKnowledgeGaps(BaseModel):
    """Unit hổng phổ biến của 1 lớp."""

    class_id: int
    subject_id: int
    school_year_id: int
    semester_index: int
    gaps: list[KnowledgeGapItem] = Field(default_factory=list)

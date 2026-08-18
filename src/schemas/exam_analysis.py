"""Schema phân tích nội dung đề thi (5 trục — M3 trong docs_vsf/plan_cdi_kg_anchored.md).

Dùng chung service + API. Xem src/services/content_difficulty.py (dựng dữ liệu) và
src/api/v1/exam_papers.py (expose qua `exam_papers.ai_analysis.content_analysis`).
"""

from pydantic import BaseModel


class NodeRef(BaseModel):
    """Trích dẫn tĩnh từ cây chuẩn chương trình (không RAG, không OCR sách)."""

    node_id: int
    chapter: str | None = None
    lesson: str | None = None


class AnalysisItemRead(BaseModel):
    topic: str
    excerpt: str | None
    unit_code: str | None
    unit_name: str | None
    matched_catalog: bool
    bloom_level: int
    weight: float
    node_ref: NodeRef | None = None
    off_curriculum: bool | None = None
    off_curriculum_weight: float = 0.0


class CoverageUnitRead(BaseModel):
    unit_code: str
    unit_name: str
    weight: float


class CoverageRead(BaseModel):
    catalog_total: int
    matched: int
    ratio: float | None


class ConcentrationRead(BaseModel):
    top_unit_code: str | None
    top_unit_name: str | None
    top_share: float | None
    is_concentrated: bool


class ExamContentAnalysis(BaseModel):
    version: int = 1
    model: str | None
    cdi: float
    items: list[AnalysisItemRead]
    coverage: CoverageRead
    coverage_units: list[CoverageUnitRead]
    concentration: ConcentrationRead
    off_curriculum_weight: float | None
    bloom_distribution: dict[str, float] | None = None
    bloom_alignment: str | None = None

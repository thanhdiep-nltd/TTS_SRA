"""Schema phân tích nội dung đề thi (RAG-anchored CDI) — dùng chung service + API.

Xem src/services/content_difficulty.py (dựng dữ liệu) và src/api/v1/exam_papers.py (expose qua
`exam_papers.ai_analysis.content_analysis`).
"""

from pydantic import BaseModel


class EvidenceRef(BaseModel):
    """Bằng chứng SGK tốt nhất cho 1 ý của đề (từ Qdrant, đã qua ngưỡng retrieval_score_floor).

    `heading` CHỈ mô tả nguồn cho người duyệt (đường dẫn heading OCR, khá nhiễu) — KHÔNG dùng để
    xác định chủ đề (xem _resolve_units trong content_difficulty.py, taxonomy neo theo unit_code).
    """

    score: float
    heading: str | None = None
    source_md: str | None = None


class AnalysisItemRead(BaseModel):
    topic: str
    excerpt: str | None
    unit_code: str | None
    unit_name: str | None
    matched_catalog: bool
    bloom_level: int
    weight: float
    evidence: EvidenceRef | None
    off_curriculum: bool | None


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
    rag_available: bool
    items: list[AnalysisItemRead]
    coverage: CoverageRead
    coverage_units: list[CoverageUnitRead]
    concentration: ConcentrationRead
    off_curriculum_weight: float | None
    bloom_distribution: dict[str, float] | None = None
    bloom_alignment: str | None = None
    avg_retrieval_distance: float | None = None

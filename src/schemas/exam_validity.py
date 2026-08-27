from pydantic import BaseModel

from src.models import enums


class ExamValidityRead(BaseModel):
    """Một dòng tam giác hóa độ khó: EDI (thực nghiệm, từ điểm số) vs CDI (nội dung đề)."""

    exam_paper_id: int
    subject_id: int
    subject_name: str
    semester_id: int
    score_category: enums.ScoreCategory
    grade_id: int | None
    grade_name: str
    n: int
    mean_score: float
    edi: float
    cdi: float | None
    divergence: float | None
    flag: str
    confidence: str
    column_index: int | None = None


class SchoolValidityOverview(BaseModel):
    """Tổng hợp toàn trường: số lượng theo cờ + danh sách đề đáng rà soát nhất."""

    total_checked: int
    flags_count: dict[str, int]
    flagged_items: list[ExamValidityRead]


class ContentAdjustedRankRow(BaseModel):
    """Xếp hạng lớp theo thực lực neo-nội-dung (content_adjusted_ability)."""

    class_id: int
    class_name: str
    raw_average: float
    content_adjusted_ability: float
    cdi: float

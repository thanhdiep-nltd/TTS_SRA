"""src/schemas/pass_fail_forecast.py — DTO cho API dự đoán pass/fail (M4)."""

from pydantic import BaseModel, Field


class StudentForecastRow(BaseModel):
    """Dự đoán 1 học sinh."""

    student_code: str
    student_name: str | None = None
    predicted_score: float
    verdict: str  # 'PASS' | 'FAIL' | 'BORDERLINE'


class PassFailForecastResult(BaseModel):
    """Kết quả dự đoán pass/fail cho 1 đề cuối kỳ."""

    exam_paper_id: int | None = None
    cdi: float | None = None
    total: int = 0
    pass_count: int = 0
    fail_count: int = 0
    borderline_count: int = 0
    fail_rate: float = 0.0
    students: list[StudentForecastRow] = Field(default_factory=list)

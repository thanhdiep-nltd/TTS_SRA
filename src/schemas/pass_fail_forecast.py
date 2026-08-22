"""src/schemas/pass_fail_forecast.py — DTO cho API dự đoán pass/fail (M4)."""

from pydantic import BaseModel, Field


class WeakUnitInfo(BaseModel):
    """1 bài học sinh yếu + trọng số của bài đó trong đề."""

    unit_name: str
    ability: float | None  # 0..10; None nếu không có LMS
    exam_weight: float  # 0..1, trọng số của bài trong đề


class StudentForecastRow(BaseModel):
    """Dự đoán 1 học sinh."""

    student_code: str
    student_name: str | None = None
    class_name: str | None = None
    predicted_score: float | None = None  # None = INSUFFICIENT (không đủ dữ liệu LMS)
    verdict: str  # 'PASS' | 'FAIL' | 'BORDERLINE' | 'INSUFFICIENT'
    weak_units: list[WeakUnitInfo] = Field(default_factory=list)  # top 2 bài gây mất điểm nhất


class PassFailForecastResult(BaseModel):
    """Kết quả dự đoán pass/fail cho 1 đề cuối kỳ."""

    exam_paper_id: int | None = None
    cdi: float | None = None
    total: int = 0
    pass_count: int = 0
    fail_count: int = 0
    borderline_count: int = 0
    insufficient_count: int = 0  # số HS không đủ dữ liệu LMS (không dự đoán được)
    fail_rate: float = 0.0  # tính trên số HS CÓ dự đoán
    students: list[StudentForecastRow] = Field(default_factory=list)

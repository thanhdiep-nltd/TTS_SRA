"""src/services/pass_fail_forecast.py — Dự đoán Pass/Fail cho đề cuối kỳ (M4).

Mục tiêu: GV upload đề cuối kỳ → dự đoán bao nhiêu học sinh trượt/pass.
Dùng năng lực từng unit (ability_u) + trọng số unit của đề + độ khó CDI để
ước lượng điểm từng học sinh, rồi phân loại pass/fail/borderline.

Module này là hàm THUẦN (không DB, không LLM) → dễ unit test.
"""

from __future__ import annotations

from pydantic import BaseModel

# Ngưỡng phân loại (có thể cấu hình theo trường/môn).
BORDERLINE_LOW = 4.5
BORDERLINE_HIGH = 5.5


class StudentAbility(BaseModel):
    """Năng lực từng unit của 1 học sinh (0..10)."""

    student_code: str
    ability: dict[int, float]  # {unit_id: ability 0..10}


class ExamUnit(BaseModel):
    """1 unit trong đề cuối kỳ."""

    unit_id: int
    weight: float  # 0..1, tổng ≈ 1


class StudentForecast(BaseModel):
    """Kết quả dự đoán 1 học sinh."""

    student_code: str
    predicted_score: float
    verdict: str  # 'PASS' | 'FAIL' | 'BORDERLINE'


def _difficulty_adj(cdi: float | None) -> float:
    """Hệ số điều chỉnh theo độ khó nội dung CDI (0..1).

    CDI cao (đề khó) → điểm dự kiến giảm; CDI thấp (đề dễ) → tăng.
    Mặc định 0.5 (trung tính) nếu không có CDI.
    """
    cdi = 0.5 if cdi is None else cdi
    # CDI 0.5 → adj 1.0; CDI 0.0 → adj 1.25; CDI 1.0 → adj 0.75.
    return 1.0 + (0.5 - cdi) * 0.5


def predict_student_score(
    student: StudentAbility,
    exam_units: list[ExamUnit],
    cdi: float | None = None,
) -> float:
    """Dự đoán điểm của 1 học sinh trên đề cuối kỳ.

    predicted = Σ_u(weight_u * ability_u) * difficulty_adj(CDI)
    ability_u mặc định 0.0 nếu học sinh không có dữ liệu unit đó.
    """
    if not exam_units:
        return 0.0

    total_weight = sum(u.weight for u in exam_units)
    if total_weight <= 0:
        weights = [1.0 / len(exam_units)] * len(exam_units)
    else:
        weights = [u.weight / total_weight for u in exam_units]

    weighted = sum(
        w * student.ability.get(u.unit_id, 0.0)
        for w, u in zip(weights, exam_units, strict=False)
    )
    return round(weighted * _difficulty_adj(cdi), 2)


def classify_verdict(score: float) -> str:
    """Phân loại pass/fail/borderline theo ngưỡng."""
    if score < BORDERLINE_LOW:
        return "FAIL"
    if score > BORDERLINE_HIGH:
        return "PASS"
    return "BORDERLINE"


def forecast_exam(
    students: list[StudentAbility],
    exam_units: list[ExamUnit],
    cdi: float | None = None,
) -> list[StudentForecast]:
    """Dự đoán pass/fail cho cả lớp trên 1 đề cuối kỳ."""
    forecasts: list[StudentForecast] = []
    for s in students:
        score = predict_student_score(s, exam_units, cdi)
        forecasts.append(
            StudentForecast(
                student_code=s.student_code,
                predicted_score=score,
                verdict=classify_verdict(score),
            )
        )
    return forecasts


def summarize(forecasts: list[StudentForecast]) -> dict:
    """Tổng hợp số lượng pass/fail/borderline."""
    n_pass = sum(1 for f in forecasts if f.verdict == "PASS")
    n_fail = sum(1 for f in forecasts if f.verdict == "FAIL")
    n_border = sum(1 for f in forecasts if f.verdict == "BORDERLINE")
    total = len(forecasts)
    return {
        "total": total,
        "pass": n_pass,
        "fail": n_fail,
        "borderline": n_border,
        "fail_rate": round(n_fail / total, 3) if total else 0.0,
    }

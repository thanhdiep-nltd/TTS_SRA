"""src/services/pass_fail_forecast.py — Dự đoán Pass/Fail cho đề cuối kỳ (M4).

Mục tiêu: GV upload đề cuối kỳ → dự đoán bao nhiêu học sinh trượt/pass.
Dùng năng lực từng UNIT (ability_u, từ LMS cấp bài) + trọng số unit của đề (W,
cấp bài) + độ khó CDI để ước lượng điểm từng học sinh, rồi phân loại
pass/fail/borderline/insufficient.

Chuỗi điền `ability`: bài có LMS → raw×10; thiếu → TB chương của HS; chương
trống → TB toàn môn; HS không có LMS → INSUFFICIENT (trả None, không bịa số).

Module này là hàm THUẦN (không DB, không LLM) → dễ unit test.
"""

from __future__ import annotations

from pydantic import BaseModel

# Ngưỡng phân loại (có thể cấu hình theo trường/môn).
BORDERLINE_LOW = 4.5
BORDERLINE_HIGH = 5.5


class StudentAbility(BaseModel):
    """Năng lực từng unit của 1 học sinh (0..10; None = bài chưa có dữ liệu)."""

    student_code: str
    ability: dict[int, float | None]  # {unit_id: ability 0..10 | None}


class ExamUnit(BaseModel):
    """1 unit (bài) trong đề cuối kỳ."""

    unit_id: int
    weight: float  # 0..1, tổng ≈ 1


class StudentForecast(BaseModel):
    """Kết quả dự đoán 1 học sinh."""

    student_code: str
    predicted_score: float | None  # None = INSUFFICIENT (không có dữ liệu LMS)
    verdict: str  # 'PASS' | 'FAIL' | 'BORDERLINE' | 'INSUFFICIENT'


def resolve_abilities(
    raw_by_lesson: dict[int, float],
    lesson_ids: list[int],
    lesson_to_chapter: dict[int, int] | None = None,
) -> dict[int, float | None] | None:
    """Điền ability (0..10) cho từng bài có dữ liệu LMS.
    
    Không fallback: Bài chưa có LMS sẽ gán None (không bịa điểm hoặc gán trung bình).
    Nếu học sinh hoàn toàn không có bất kỳ bài LMS nào -> trả về None (INSUFFICIENT).
    """
    if not raw_by_lesson:
        return None

    abilities: dict[int, float | None] = {}
    for lesson_id in lesson_ids:
        if lesson_id in raw_by_lesson:
            abilities[lesson_id] = raw_by_lesson[lesson_id] * 10.0
        else:
            abilities[lesson_id] = None
    return abilities


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
) -> float | None:
    """Dự đoán điểm của 1 học sinh trên đề cuối kỳ.

    predicted = ( Σ_u(weight_u * ability_u) / Σ_u weight_u ) * difficulty_adj(CDI), clamp 0..10.
    ability None → coi 0.0; trả None nếu HS không có ability cho BẤT KỲ unit nào (INSUFFICIENT).
    """
    if not exam_units:
        return None

    abilities = [student.ability.get(u.unit_id) for u in exam_units]
    if all(a is None for a in abilities):
        return None

    total_weight = sum(u.weight for u in exam_units)
    if total_weight <= 0:
        weights = [1.0 / len(exam_units)] * len(exam_units)
    else:
        weights = [u.weight / total_weight for u in exam_units]

    weighted = sum(
        (w * (a or 0.0) for a, w in zip(abilities, weights, strict=False)),
        start=0.0,
    )
    raw_score = weighted * _difficulty_adj(cdi)
    return round(min(10.0, max(0.0, raw_score)), 2)


def classify_verdict(score: float | None) -> str:
    """Phân loại pass/fail/borderline/insufficient theo ngưỡng."""
    if score is None:
        return "INSUFFICIENT"
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
    """Tổng hợp pass/fail/borderline/insufficient.

    `fail_rate` tính trên số HS CÓ dự đoán (không gồm INSUFFICIENT) để không bị nhiễu.
    """
    n_insufficient = sum(1 for f in forecasts if f.predicted_score is None)
    n_pass = sum(1 for f in forecasts if f.verdict == "PASS")
    n_fail = sum(1 for f in forecasts if f.verdict == "FAIL")
    n_border = sum(1 for f in forecasts if f.verdict == "BORDERLINE")
    total_predicted = len(forecasts) - n_insufficient
    return {
        "total": len(forecasts),
        "pass": n_pass,
        "fail": n_fail,
        "borderline": n_border,
        "insufficient": n_insufficient,
        "fail_rate": round(n_fail / total_predicted, 3) if total_predicted else 0.0,
    }


def compute_weak_units(
    student: StudentAbility,
    exam_units: list[ExamUnit],
    unit_names: dict[int, str],
) -> list:
    """Top 2 bài học sinh yếu nhất + trọng số cao nhất trong đề.

    Sắp xếp theo Loss Score = (10.0 - ability_u) × exam_weight_u.
    ability_u None → coi 0.0. Chỉ giữ bài có loss > 0.
    """
    if not exam_units:
        return []

    losses: list[tuple[float, int, float | None, float]] = []
    for u in exam_units:
        ability = student.ability.get(u.unit_id)
        effective = ability if ability is not None else 0.0
        loss = (10.0 - effective) * u.weight
        if loss > 0:
            losses.append((loss, u.unit_id, ability, u.weight))

    losses.sort(key=lambda x: x[0], reverse=True)
    top = losses[:2]

    result: list = []
    for _loss, unit_id, ability, weight in top:
        name = unit_names.get(unit_id, f"Bài #{unit_id}")
        result.append(
            {
                "unit_name": name,
                "ability": round(ability, 2) if ability is not None else None,
                "exam_weight": round(weight, 3),
            }
        )
    return result

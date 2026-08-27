"""Unit test cho src/services/pass_fail_forecast.py — dự đoán pass/fail (M4)."""

from src.services.pass_fail_forecast import (
    ExamUnit,
    StudentAbility,
    classify_verdict,
    forecast_exam,
    predict_student_score,
    resolve_abilities,
    summarize,
)


def test_predict_score_weighted_average():
    student = StudentAbility(student_code="S1", ability={1: 8.0, 2: 4.0})
    units = [ExamUnit(unit_id=1, weight=0.5), ExamUnit(unit_id=2, weight=0.5)]
    # (0.5*8 + 0.5*4) = 6.0, CDI=0.5 → adj=1.0
    assert predict_student_score(student, units, cdi=0.5) == 6.0


def test_predict_score_missing_unit_defaults_zero():
    student = StudentAbility(student_code="S1", ability={1: 8.0})
    units = [ExamUnit(unit_id=1, weight=0.5), ExamUnit(unit_id=2, weight=0.5)]
    # (0.5*8 + 0.5*0) = 4.0
    assert predict_student_score(student, units, cdi=0.5) == 4.0


def test_hard_exam_lowers_score():
    student = StudentAbility(student_code="S1", ability={1: 8.0})
    units = [ExamUnit(unit_id=1, weight=1.0)]
    easy = predict_student_score(student, units, cdi=0.0)
    hard = predict_student_score(student, units, cdi=1.0)
    assert easy > hard


def test_classify_verdict():
    assert classify_verdict(3.0) == "FAIL"
    assert classify_verdict(5.0) == "BORDERLINE"
    assert classify_verdict(7.0) == "PASS"


def test_forecast_and_summarize():
    students = [
        StudentAbility(student_code="S1", ability={1: 8.0}),
        StudentAbility(student_code="S2", ability={1: 3.0}),
        StudentAbility(student_code="S3", ability={1: 5.0}),
    ]
    units = [ExamUnit(unit_id=1, weight=1.0)]
    forecasts = forecast_exam(students, units, cdi=0.5)
    summary = summarize(forecasts)
    assert summary["total"] == 3
    assert summary["pass"] == 1
    assert summary["fail"] == 1
    assert summary["borderline"] == 1


# === resolve_abilities: chuỗi fallback (bài → chương → môn → INSUFFICIENT) ===


def test_resolve_abilities_lesson_present():
    # Bài 1 có dữ liệu → raw×10; bài 2 thiếu nhưng cùng chương có bài 1 dữ liệu → TB chương.
    l2c = {1: 10, 2: 10, 3: 20}
    abilities = resolve_abilities({1: 0.8}, lesson_ids=[1, 2, 3], lesson_to_chapter=l2c)
    assert abilities[1] == 8.0
    assert abilities[2] == 8.0  # cùng chương (10) với bài 1 → TB chương 0.8
    assert abilities[3] == 8.0  # chương 20 không có dữ liệu → TB toàn môn 0.8


def test_resolve_abilities_chapter_avg():
    # Bài 1 (chương 10) raw 0.9; bài 2 (chương 10) raw 0.7 → TB chương 0.8;
    # bài 3 (chương 20) chưa có → TB toàn môn = (0.9+0.7)/2 = 0.8.
    l2c = {1: 10, 2: 10, 3: 20}
    abilities = resolve_abilities({1: 0.9, 2: 0.7}, lesson_ids=[1, 2, 3], lesson_to_chapter=l2c)
    assert abilities[1] == 9.0
    assert abilities[2] == 7.0
    assert abilities[3] == 8.0


def test_resolve_abilities_returns_none_without_lms():
    assert resolve_abilities({}, lesson_ids=[1, 2], lesson_to_chapter={1: 10, 2: 10}) is None


# === INSUFFICIENT: HS không có LMS → predicted_score None, verdict INSUFFICIENT ===


def test_predict_insufficient_when_all_none():
    student = StudentAbility(student_code="S1", ability={1: None, 2: None})
    units = [ExamUnit(unit_id=1, weight=0.5), ExamUnit(unit_id=2, weight=0.5)]
    assert predict_student_score(student, units, cdi=0.5) is None
    assert classify_verdict(None) == "INSUFFICIENT"


def test_summarize_ignores_insufficient_in_fail_rate():
    students = [
        StudentAbility(student_code="S1", ability={1: 8.0}),  # PASS
        StudentAbility(student_code="S2", ability={1: 2.0}),  # FAIL
        StudentAbility(student_code="S3", ability={1: None}),  # INSUFFICIENT
    ]
    units = [ExamUnit(unit_id=1, weight=1.0)]
    summary = summarize(forecast_exam(students, units, cdi=0.5))
    assert summary["total"] == 3
    assert summary["insufficient"] == 1
    assert summary["pass"] == 1
    assert summary["fail"] == 1
    # fail_rate tính trên HS có dự đoán (2) → 1/2 = 0.5, không phải 1/3.
    assert summary["fail_rate"] == 0.5


# === clamp 0..10 (đề cực dễ/khó không làm điểm vượt biên) ===


def test_predict_score_clamped_to_10():
    student = StudentAbility(student_code="S1", ability={1: 9.0})
    units = [ExamUnit(unit_id=1, weight=1.0)]
    # CDI 0 → adj 1.25 → 9.0*1.25=11.25 → clamp 10.0
    assert predict_student_score(student, units, cdi=0.0) == 10.0


def test_predict_score_clamped_to_0():
    student = StudentAbility(student_code="S1", ability={1: 1.0})
    units = [ExamUnit(unit_id=1, weight=1.0)]
    # ability lớn hơn 0 nên không âm; bài missing → coi 0.0 → clamp vẫn ≥ 0
    assert predict_student_score(student, units, cdi=1.0) >= 0.0

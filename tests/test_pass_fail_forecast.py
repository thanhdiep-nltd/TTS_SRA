"""Unit test cho src/services/pass_fail_forecast.py — dự đoán pass/fail (M4)."""

from src.services.pass_fail_forecast import (
    ExamUnit,
    StudentAbility,
    classify_verdict,
    forecast_exam,
    predict_student_score,
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

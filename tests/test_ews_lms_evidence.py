"""Unit test cho src/ews/lms_evidence.py — phân loại hành vi LMS (M3)."""

from src.ews.lms_evidence import (
    EvidencePattern,
    LmsAssignmentEvidence,
    classify_lms_behavior,
    mark_missing_in_exam,
)


def test_skipped():
    a = LmsAssignmentEvidence(unit_name="Chương 2", submitted=False)
    result = classify_lms_behavior([a])
    assert result == [
        EvidencePattern(unit_name="Chương 2", pattern="SKIPPED", explanation="Không nộp bài LMS chương 'Chương 2'.")
    ]


def test_rushed_by_rte():
    a = LmsAssignmentEvidence(unit_name="Chương 3", final_grade=2.0, rte=0)
    result = classify_lms_behavior([a])
    assert result[0].pattern == "RUSHED"


def test_rushed_by_short_active_time():
    a = LmsAssignmentEvidence(
        unit_name="Chương 3",
        final_grade=2.0,
        active_time_sec=40,
        time_limit_sec=600,  # 40/600 = 0.067 < 0.1
    )
    result = classify_lms_behavior([a])
    assert result[0].pattern == "RUSHED"


def test_off_task_by_low_active_fraction():
    a = LmsAssignmentEvidence(
        unit_name="Chương 4",
        final_grade=3.0,
        active_time_sec=100,
        time_spent_sec=1000,  # 100/1000 = 0.1 < 0.3
        time_limit_sec=600,
    )
    result = classify_lms_behavior([a])
    assert result[0].pattern == "OFF_TASK"


def test_off_task_by_tab_hidden():
    a = LmsAssignmentEvidence(
        unit_name="Chương 4",
        final_grade=3.0,
        active_time_sec=500,
        time_spent_sec=600,
        time_limit_sec=600,
        tab_hidden_count=5,
    )
    result = classify_lms_behavior([a])
    assert result[0].pattern == "OFF_TASK"


def test_effort_but_lost():
    a = LmsAssignmentEvidence(
        unit_name="Chương 2",
        final_grade=3.0,
        active_time_sec=1500,
        time_spent_sec=1600,
        time_limit_sec=1800,  # 1500/1800 = 0.83 > 0.6
        attempt_count=2,
        rte=1,
    )
    result = classify_lms_behavior([a])
    assert result[0].pattern == "EFFORT_BUT_LOST"


def test_weak_chapter():
    a = LmsAssignmentEvidence(
        unit_name="Chương 5",
        final_grade=4.0,
        active_time_sec=500,
        time_spent_sec=600,
        time_limit_sec=1200,  # 500/1200 = 0.42 (không rushed, không effort)
    )
    result = classify_lms_behavior([a])
    assert result[0].pattern == "WEAK_CHAPTER"


def test_no_evidence_when_good_score():
    a = LmsAssignmentEvidence(
        unit_name="Chương 6",
        final_grade=8.0,
        active_time_sec=500,
        time_spent_sec=600,
        time_limit_sec=1200,
    )
    result = classify_lms_behavior([a])
    assert result == []


def test_mark_missing_in_exam():
    exam_units = ["Chương 2", "Chương 3", "Chương 4"]
    lms_units = {"Chương 2"}
    result = mark_missing_in_exam(exam_units, lms_units)
    assert [p.unit_name for p in result] == ["Chương 3", "Chương 4"]
    assert all(p.pattern == "MISSING_IN_EXAM" for p in result)

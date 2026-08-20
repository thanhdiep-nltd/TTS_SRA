"""Unit test cho src/services/lms_item_ingest.py — adapter nạp item-response LMS từ đối tác."""

import pytest

from src.services.lms_item_ingest import (
    INTEGRITY_NORMAL,
    INTEGRITY_SUSPECTED,
    ItemIngestRow,
    build_best_attempt_flags,
    deduplicate_rows,
    resolve_integrity,
    resolve_mastery,
    validate_row,
)


class _FakeUnitMapper:
    """UnitMapper giả: Tầng 2 trả unit cố định, Tầng 3 không chạy."""

    def __init__(self, unit: int | None, bloom: int | None = None):
        self.unit = unit
        self.bloom = bloom

    def map_unit(self, row: ItemIngestRow) -> tuple[int | None, int | None]:
        return self.unit, self.bloom


def _direct_fn(unit: int | None, bloom: int | None = None):
    def fn(row: ItemIngestRow) -> tuple[int | None, int | None]:
        return unit, bloom

    return fn


def test_validate_row_ok():
    row = validate_row(
        {
            "student_code": "HS001",
            "assignment_id": 10,
            "question_id": 5,
            "so_school_id": 1,
            "subject_id": 2,
            "attempt_number": 2,
            "is_correct": True,
            "score_received": "1.0",
            "max_score": 1,
        }
    )
    assert row.student_code == "HS001"
    assert row.attempt_number == 2
    assert row.score_received == 1.0
    assert row.max_score == 1.0


def test_validate_row_missing_student_raises():
    with pytest.raises(ValueError):
        validate_row({"question_id": 5})


def test_validate_row_empty_student_raises():
    with pytest.raises(ValueError):
        validate_row({"student_code": "  ", "question_id": 5})


def test_resolve_integrity_rapid_guess():
    # Trả lời trong < 2 giây → Suspected (đoán mò siêu tốc).
    fast = ItemIngestRow(student_code="HS001", assignment_id=1, question_id=1, so_school_id=1, subject_id=2,
                         response_time_seconds=1)
    slow = ItemIngestRow(student_code="HS001", assignment_id=1, question_id=2, so_school_id=1, subject_id=2,
                         response_time_seconds=30)
    assert resolve_integrity(fast) == INTEGRITY_SUSPECTED
    assert resolve_integrity(slow) == INTEGRITY_NORMAL


def test_resolve_mastery_tier1_direct_first():
    # Tầng 1 (direct) có unit → dùng luôn, không cần Tầng 2.
    row = ItemIngestRow(student_code="HS001", assignment_id=1, question_id=1, so_school_id=1, subject_id=2)
    unit, bloom = resolve_mastery(_FakeUnitMapper(99, 4), _direct_fn(7, 2), row)
    assert (unit, bloom) == (7, 2)


def test_resolve_mastery_tier1_fallback_to_tier2():
    # Tầng 1 không map được (None) → Tầng 2 (strand/AI).
    row = ItemIngestRow(student_code="HS001", assignment_id=1, question_id=1, so_school_id=1, subject_id=2)
    unit, bloom = resolve_mastery(_FakeUnitMapper(99, 4), _direct_fn(None, None), row)
    assert (unit, bloom) == (99, 4)


def test_resolve_mastery_tier1_fallback_default_bloom():
    # Tầng 2 trả unit nhưng bloom None → mặc định 3.
    row = ItemIngestRow(student_code="HS001", assignment_id=1, question_id=1, so_school_id=1, subject_id=2)
    unit, bloom = resolve_mastery(_FakeUnitMapper(99, None), _direct_fn(None, None), row)
    assert (unit, bloom) == (99, 3)


def test_resolve_mastery_none_when_no_mapping():
    row = ItemIngestRow(student_code="HS001", assignment_id=1, question_id=1, so_school_id=1, subject_id=2)
    unit, bloom = resolve_mastery(_FakeUnitMapper(None, None), _direct_fn(None, None), row)
    assert (unit, bloom) == (None, 3)  # bloom mặc định, unit None → không tính được


def _row(qid: int, attempt: int, score: float) -> ItemIngestRow:
    return ItemIngestRow(
        student_code="HS001",
        assignment_id=10,
        question_id=qid,
        so_school_id=1,
        subject_id=2,
        attempt_number=attempt,
        score_received=score,
    )


def test_deduplicate_rows_keeps_best_same_attempt():
    rows = [_row(1, 1, 0.5), _row(1, 1, 1.0)]
    out = deduplicate_rows(rows)
    assert len(out) == 1
    assert out[("HS001", 10, 1, 1)].score_received == 1.0


def test_build_best_attempt_flags_picks_highest():
    # 3 attempt cùng câu: điểm 0.4, 0.8, 0.6 → best là 0.8.
    rows = [_row(1, 1, 0.4), _row(1, 2, 0.8), _row(1, 3, 0.6)]
    best = build_best_attempt_flags(rows)
    assert best[("HS001", 10, 1)].attempt_number == 2
    assert best[("HS001", 10, 1)].score_received == 0.8


def test_build_best_attempt_flags_lower_keeps_old():
    # attempt mới điểm thấp hơn → best giữ attempt cũ (pro-tip #2).
    rows = [_row(1, 1, 0.9), _row(1, 2, 0.5)]
    best = build_best_attempt_flags(rows)
    assert best[("HS001", 10, 1)].attempt_number == 1

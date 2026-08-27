"""Unit test cho src/services/item_mastery.py — mastery theo chương từ item-response + đối soát."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from src.api.v1.knowledge_gap import get_student_knowledge_gaps
from src.services.item_mastery import (
    ItemResult,
    compute_evidence_source,
    finalize_mastery,
    merge_onclass_adjustment,
    raw_unit_mastery,
)

# === raw_unit_mastery ===


def _items(scores: list[float], blooms: list[int] | None = None, max_scores: list[float] | None = None) -> list[ItemResult]:
    n = len(scores)
    blooms = blooms or [3] * n
    max_scores = max_scores or [1.0] * n
    return [
        ItemResult(unit_id=1, bloom_level=blooms[i], score_received=scores[i], max_score=max_scores[i])
        for i in range(n)
    ]


def test_raw_empty_items_insufficient():
    r = raw_unit_mastery([])
    assert r.raw_mastery is None
    assert r.confidence == "INSUFFICIENT"
    assert r.integrity_status == "INSUFFICIENT"


def test_raw_mastery_bloom_weighted():
    # 2 câu Bloom 1 (factor 0.5) đúng hết, 1 câu Bloom 6 (factor 2.0) sai.
    # Tử: 1*0.5 + 1*0.5 + 0*2.0 = 1.0; Mẫu: 1*0.5 + 1*0.5 + 1*2.0 = 3.0 → 1/3.
    items = _items([1.0, 1.0, 0.0], blooms=[1, 1, 6])
    r = raw_unit_mastery(items)
    assert r.n_items == 3
    assert r.raw_mastery == round(1.0 / 3.0, 4)


def test_raw_coverage_low_medium_confidence():
    # 2 câu (< MIN_ITEMS=5) → coverage 0.4 → confidence MEDIUM.
    r = raw_unit_mastery(_items([1.0, 1.0]))
    assert r.coverage == 0.4
    assert r.confidence == "MEDIUM"


def test_raw_coverage_full_high_confidence():
    r = raw_unit_mastery(_items([1.0] * 5))
    assert r.coverage == 1.0
    assert r.confidence == "HIGH"


# === multi-chapter (lms_question_unit): 1 câu đóng góp vào nhiều chương theo trọng số ===


def test_raw_multi_chapter_weighted_mastery():
    # Câu multi-chapter 60% chương này + 40% chương khác, đúng 1.0:
    # câu này đóng góp vào chương hiện tại với unit_weight=0.6.
    items = [ItemResult(unit_id=1, bloom_level=3, score_received=1.0, max_score=1.0, unit_weight=0.6)]
    r = raw_unit_mastery(items)
    # Tử = 1.0 * 1.0 * 0.6; Mẫu = 1.0 * 1.0 * 0.6 → mastery 1.0 (câu đúng).
    assert r.raw_mastery == 1.0
    assert r.n_items == 1


def test_raw_multi_chapter_weighted_wrong_answer():
    # Câu multi-chapter sai: đóng góp 0 vào chương dù có weight → mastery 0.
    items = [ItemResult(unit_id=1, bloom_level=3, score_received=0.0, max_score=1.0, unit_weight=0.6)]
    r = raw_unit_mastery(items)
    assert r.raw_mastery == 0.0
    assert r.n_correct == 0


def test_raw_multi_chapter_weighted_partial_share():
    # 2 câu cùng chương: câu A đúng weight 1.0 (1 chương), câu B đúng weight 0.4
    # (câu multi-chapter đóng góp 40% vào chương này). Cả 2 đúng → mastery 1.0
    # nhưng n_correct tính theo số ItemResult (2).
    items = [
        ItemResult(unit_id=1, bloom_level=3, score_received=1.0, max_score=1.0, unit_weight=1.0),
        ItemResult(unit_id=1, bloom_level=3, score_received=1.0, max_score=1.0, unit_weight=0.4),
    ]
    r = raw_unit_mastery(items)
    assert r.raw_mastery == 1.0
    assert r.n_items == 2
    assert r.n_correct == 2


def test_finalize_mastery_multi_chapter():
    # Pipeline đầy đủ với câu multi-chapter: raw weighted + đối soát exam.
    items = [ItemResult(unit_id=1, bloom_level=3, score_received=1.0, max_score=1.0, unit_weight=0.6)] * 5
    out = finalize_mastery(items, exam_mastery=0.75)
    assert out.raw_mastery == 1.0
    # Δ = 1.0 - 0.75 = 0.25 → trong (0.15, 0.30] → MEDIUM.
    assert out.confidence == "MEDIUM"
    assert out.integrity_status == "OK"


# === merge_onclass_adjustment (đối soát bất cân xứng) ===


def test_merge_match_high_confidence():
    raw = raw_unit_mastery(_items([1.0] * 5))
    out = merge_onclass_adjustment(raw, exam_mastery=0.9)
    assert out.lm_weight == 0.8 and out.exam_weight == 0.2
    assert out.confidence == "HIGH"
    assert out.integrity_status == "OK"
    assert out.evidence_source == "HYBRID"
    # adjusted = 0.8*1.0 + 0.2*0.9 = 0.98
    assert out.adjusted_mastery == 0.98


def test_merge_buffer_zone_medium():
    # |Δ| = 0.2 nằm trong vùng đệm (0.15, 0.30] → w 0.6/0.4, MEDIUM, OK.
    raw = raw_unit_mastery(_items([1.0] * 5))
    out = merge_onclass_adjustment(raw, exam_mastery=0.8)
    assert out.lm_weight == 0.6 and out.exam_weight == 0.4
    assert out.confidence == "MEDIUM"
    assert out.integrity_status == "OK"
    # adjusted = 0.6*1.0 + 0.4*0.8 = 0.92
    assert out.adjusted_mastery == 0.92


def test_merge_lms_exceeds_exam():
    # LMS 1.0 vs thi 0.4 → Δ=0.6 > 0.30 → LMS vượt trội, kết hợp cân bằng.
    raw = raw_unit_mastery(_items([1.0] * 5))
    out = merge_onclass_adjustment(raw, exam_mastery=0.4)
    assert out.lm_weight == 0.5 and out.exam_weight == 0.5
    assert out.confidence == "MEDIUM"
    assert out.integrity_status == "LMS_EXCEEDS_EXAM"
    # adjusted = 0.5*1.0 + 0.5*0.4 = 0.70 >= 0.6 → not gap
    assert out.adjusted_mastery == 0.70
    assert out.is_gap is False


def test_merge_low_engagement():
    # LMS 0.4 vs thi 0.9 → Δ=-0.5 < -0.30 → ít luyện tập LMS.
    raw = raw_unit_mastery(_items([0.4] * 5))
    out = merge_onclass_adjustment(raw, exam_mastery=0.9)
    assert out.lm_weight == 0.4 and out.exam_weight == 0.6
    assert out.confidence == "MEDIUM"
    assert out.integrity_status == "LOW_ENGAGEMENT"


def test_merge_no_exam_lms_only():
    raw = raw_unit_mastery(_items([1.0] * 5))
    out = merge_onclass_adjustment(raw, exam_mastery=None)
    assert out.evidence_source == "LMS"
    assert out.integrity_status == "LMS_ONLY"
    assert out.adjusted_mastery == raw.raw_mastery


def test_merge_insufficient_raw_returns_insufficient():
    raw = raw_unit_mastery([])
    out = merge_onclass_adjustment(raw, exam_mastery=0.9)
    assert out.confidence == "INSUFFICIENT"
    assert out.integrity_status == "INSUFFICIENT"


# === finalize_mastery + compute_evidence_source ===


def test_finalize_pipeline():
    out = finalize_mastery(_items([1.0] * 5), exam_mastery=0.9)
    assert out.adjusted_mastery is not None
    assert out.evidence_source == "HYBRID"


def test_evidence_source_insufficient_student():
    assert compute_evidence_source(0) == "INSUFFICIENT_STUDENT"
    assert compute_evidence_source(3) == "VALID"


# === endpoint: student_unit_mastery là nguồn 1, fallback EXAM là nguồn 2 ===


def _fake_db(sum_rows: list, score_row=None):
    """Fake Session trả student_unit_mastery trước, fact_gradebooks sau (theo thứ tự gọi)."""
    db = MagicMock()
    calls = {"sum": iter(sum_rows), "score": iter([score_row] if score_row else [])}

    def execute(stmt, params=None):
        sql = str(stmt)
        if "student_unit_mastery" in sql:
            row = next(calls["sum"], None)
            return SimpleNamespace(fetchall=lambda: [row] if row else [])
        if "fact_gradebooks" in sql:
            row = next(calls["score"], None)
            return SimpleNamespace(fetchone=lambda: row)
        if "curriculum_units" in sql:
            return SimpleNamespace(fetchall=lambda: [])
        if "exam_competencies" in sql:
            return SimpleNamespace(fetchall=lambda: [])
        if "dim_school_year" in sql:
            return SimpleNamespace(fetchone=lambda: SimpleNamespace(id=2025))
        return SimpleNamespace(fetchall=lambda: [], fetchone=lambda: None)

    db.execute.side_effect = execute
    return db


def _sum_row(unit_id=7, adjusted=0.8, confidence="HIGH", coverage=1.0, status="OK", source="HYBRID"):
    return SimpleNamespace(
        unit_id=unit_id,
        raw_mastery=0.9,
        adjusted_mastery=adjusted,
        n_items=5,
        n_correct=4,
        coverage=coverage,
        confidence=confidence,
        evidence_source=source,
        integrity_status=status,
        evidence_detail={"delta": 0.1, "exam_mastery": 0.8},
        lm_weight=0.8,
        exam_weight=0.2,
    )


def test_endpoint_uses_student_unit_mastery():
    db = _fake_db(sum_rows=[_sum_row()])
    res = get_student_knowledge_gaps(
        student_code="HS001",
        subject_id=2,
        school_year_id=2025,
        semester_index=1,
        current_user=SimpleNamespace(so_school_id=1),
        db=db,
    )
    assert len(res.gaps) == 1
    g = res.gaps[0]
    assert g.unit_id == 7
    assert g.mastery == 0.8
    assert g.confidence == "HIGH"
    assert g.coverage == 1.0
    assert g.integrity_status == "OK"
    assert g.evidence_source == "HYBRID"


def test_endpoint_skips_invalid_mastery_rows():
    # adjusted_mastery None → bỏ qua, không trả gap sai.
    db = _fake_db(sum_rows=[_sum_row(adjusted=None)])
    res = get_student_knowledge_gaps(
        student_code="HS001",
        subject_id=2,
        school_year_id=2025,
        semester_index=1,
        current_user=SimpleNamespace(so_school_id=1),
        db=db,
    )
    assert res.gaps == []


# === mapper confidence: SMALLINT (1/2/3) → chuỗi HIGH/MEDIUM/LOW ===


def test_endpoint_maps_smallint_confidence():
    # DB student_unit_mastery.confidence là SMALLINT (1 LOW | 2 MEDIUM | 3 HIGH).
    db = _fake_db(sum_rows=[_sum_row(confidence=3)])
    res = get_student_knowledge_gaps(
        student_code="HS001",
        subject_id=2,
        school_year_id=2025,
        semester_index=1,
        current_user=SimpleNamespace(so_school_id=1),
        db=db,
    )
    assert res.gaps[0].confidence == "HIGH"


def test_endpoint_maps_medium_confidence():
    db = _fake_db(sum_rows=[_sum_row(confidence=2)])
    res = get_student_knowledge_gaps(
        student_code="HS001",
        subject_id=2,
        school_year_id=2025,
        semester_index=1,
        current_user=SimpleNamespace(so_school_id=1),
        db=db,
    )
    assert res.gaps[0].confidence == "MEDIUM"


# === recalc_unit_mastery ===


def test_recalc_unit_mastery_mock():
    from src.services.item_mastery import recalc_unit_mastery

    unit_rows = [
        SimpleNamespace(question_id=101, unit_id=1, weight=1.0),
        SimpleNamespace(question_id=102, unit_id=2, weight=1.0),
    ]
    resp_rows = [
        SimpleNamespace(
            student_code="HS001",
            so_school_id=1,
            question_id=101,
            bloom_level=3,
            is_correct=True,
            score_received=1.0,
            max_score=1.0,
        ),
        SimpleNamespace(
            student_code="HS001",
            so_school_id=1,
            question_id=102,
            bloom_level=3,
            is_correct=False,
            score_received=0.0,
            max_score=1.0,
        ),
    ]

    mock_db = MagicMock()
    mock_db.execute.return_value.fetchall.side_effect = [unit_rows, resp_rows]

    count = recalc_unit_mastery(mock_db, subject_id=106, semester_index=1, school_id=1)
    assert count == 2
    assert mock_db.commit.called


def test_recalc_mastery_endpoint():
    from src.api.v1.knowledge_gap import recalc_mastery_endpoint

    mock_db = MagicMock()
    mock_db.execute.return_value.fetchall.side_effect = [[], []]

    res = recalc_mastery_endpoint(
        subject_id=106,
        semester_index=1,
        current_user=SimpleNamespace(so_school_id=1),
        db=mock_db,
    )
    assert res.success is True
    assert res.subject_id == 106
    assert res.records_calculated == 0

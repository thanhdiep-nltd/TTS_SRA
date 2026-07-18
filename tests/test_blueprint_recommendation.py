"""Test offline (không chạm DB) cho service gợi ý ma trận đề từ năng lực trường.

Tầng DB dùng SimpleNamespace/MagicMock giả lập kết quả execute() (khớp cách các test khác
trong repo đã làm — vd test_exam_papers_api.py monkeypatch rbac._active_assignments), không
parse SQL thật.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from src.models import enums
from src.schemas.exam_generation import RecommendBlueprintRequest
from src.services import blueprint_recommendation, exam_assembly, exam_validity

# ============================================================
# LOGIC THUẦN
# ============================================================


def test_target_difficulty_baseline_at_default_ability():
    assert blueprint_recommendation.target_difficulty_from_ability(6.5) == pytest.approx(0.35)


def test_target_difficulty_increases_with_ability():
    assert blueprint_recommendation.target_difficulty_from_ability(8.5) > blueprint_recommendation.target_difficulty_from_ability(6.5)


def test_target_difficulty_clamped_at_bounds():
    """Kẹp dưới đạt được ở ability=0 (thang 0-10). Kẹp trên là ngưỡng an toàn — với slope hiện
    tại, ability=10 (max thang thực tế) chỉ ra 0.525, chưa chạm 0.60; dùng giá trị bất thường
    (>10) để xác nhận cơ chế clamp trên vẫn hoạt động nếu input lỗi vượt thang."""
    assert blueprint_recommendation.target_difficulty_from_ability(0.0) == pytest.approx(0.25)
    assert blueprint_recommendation.target_difficulty_from_ability(10.0) == pytest.approx(0.525)
    assert blueprint_recommendation.target_difficulty_from_ability(20.0) == pytest.approx(0.60)


def test_bloom_distribution_for_target_sums_to_one_and_covers_all_bloom_levels():
    for target in (0.25, 0.35, 0.45, 0.60):
        dist = blueprint_recommendation.bloom_distribution_for_target(target)
        assert sum(dist.values()) == pytest.approx(1.0)
        assert set(dist.keys()) == {1, 2, 3, 4, 5, 6}


def test_bloom_distribution_for_target_resulting_cdi_close_to_target():
    """Trọng tâm của thiết kế lại: CDI kỳ vọng (Σbloom·weight/6) từ phân phối phải BÁM SÁT
    target_difficulty — trước đây bảng tra 3 mức năng lực không liên kết với target_difficulty,
    gây CDI hiển thị lệch xa mục tiêu (vd 0.31 vs 0.53) làm GV hiểu lầm hệ thống có lỗi."""
    for target in (0.25, 0.31, 0.35, 0.45, 0.60):
        dist = blueprint_recommendation.bloom_distribution_for_target(target)
        resulting_cdi = sum(b * w for b, w in dist.items()) / 6.0
        assert resulting_cdi == pytest.approx(target, abs=0.03)


def test_bloom_distribution_for_target_spreads_across_multiple_levels():
    """Không suy biến về 1-2 mức Bloom duy nhất — vẫn giữ được phổ độ khó đa dạng trong đề."""
    dist = blueprint_recommendation.bloom_distribution_for_target(0.45)
    meaningful_levels = [b for b, w in dist.items() if w > 0.05]
    assert len(meaningful_levels) >= 3


def test_normalize_unit_weights_typical():
    result = blueprint_recommendation.normalize_unit_weights({"a": 1.0, "b": 3.0})
    assert result["a"] == pytest.approx(0.25)
    assert result["b"] == pytest.approx(0.75)


def test_normalize_unit_weights_falls_back_to_equal_split_when_all_zero():
    result = blueprint_recommendation.normalize_unit_weights({"a": 0.0, "b": 0.0})
    assert result == {"a": 0.5, "b": 0.5}


def test_normalize_unit_weights_empty():
    assert blueprint_recommendation.normalize_unit_weights({}) == {}


def test_boosted_unit_weights_applies_boosts_and_normalizes():
    plain, boosted = uuid4(), uuid4()
    weights = blueprint_recommendation.boosted_unit_weights(
        [plain, boosted],
        misconception_counts={boosted: 3},
        weak_units={boosted},
        uncovered_units=set(),
    )
    assert weights[boosted] > weights[plain]
    assert sum(weights.values()) == pytest.approx(1.0)


def test_allocate_cells_matches_total_points_exactly():
    unit_ids = [uuid4(), uuid4(), uuid4()]
    weights = blueprint_recommendation.normalize_unit_weights(dict.fromkeys(unit_ids, 1.0))
    cells = blueprint_recommendation.allocate_cells(
        weights, total_points=10.0, total_questions=20, exam_format=enums.ExamFormat.MCQ_ONLY, target_difficulty=0.35
    )
    summed = sum(c["num_questions"] * c["points_each"] for c in cells)
    assert summed == pytest.approx(10.0, abs=0.01)


def test_allocate_cells_mixed_matches_total_points_exactly():
    unit_ids = [uuid4(), uuid4()]
    weights = blueprint_recommendation.normalize_unit_weights(dict.fromkeys(unit_ids, 1.0))
    cells = blueprint_recommendation.allocate_cells(
        weights, total_points=10.0, total_questions=20, exam_format=enums.ExamFormat.MIXED, target_difficulty=0.35
    )
    summed = sum(c["num_questions"] * c["points_each"] for c in cells)
    assert summed == pytest.approx(10.0, abs=0.01)


def test_allocate_cells_mcq_only_never_emits_essay():
    cells = blueprint_recommendation.allocate_cells(
        {uuid4(): 1.0}, total_points=10.0, total_questions=20, exam_format=enums.ExamFormat.MCQ_ONLY, target_difficulty=0.35
    )
    assert cells
    assert all(c["question_type"] == enums.QuestionType.MCQ for c in cells)


def test_allocate_cells_essay_only_never_emits_mcq():
    cells = blueprint_recommendation.allocate_cells(
        {uuid4(): 1.0}, total_points=10.0, total_questions=20, exam_format=enums.ExamFormat.ESSAY_ONLY, target_difficulty=0.35
    )
    assert cells
    assert all(c["question_type"] == enums.QuestionType.ESSAY for c in cells)


def test_allocate_cells_mixed_never_drops_essay_basket_with_small_total():
    """Bug đã sửa: rổ tự luận (share nhỏ khi total_questions ít) không được biến mất hoàn
    toàn qua nhiều tầng làm tròn (rổ -> Bloom -> đơn vị) — basket-first đảm bảo rổ có ít
    nhất 1 câu trước khi chia nhỏ tiếp."""
    cells = blueprint_recommendation.allocate_cells(
        {uuid4(): 1.0}, total_points=10.0, total_questions=10, exam_format=enums.ExamFormat.MIXED, target_difficulty=0.35, mix_ratio=0.7
    )
    types_present = {c["question_type"] for c in cells}
    assert enums.QuestionType.MCQ in types_present
    assert enums.QuestionType.ESSAY in types_present


def test_allocate_cells_never_returns_zero_question_cell():
    unit_ids = [uuid4(), uuid4()]
    weights = blueprint_recommendation.normalize_unit_weights(dict.fromkeys(unit_ids, 1.0))
    cells = blueprint_recommendation.allocate_cells(
        weights, total_points=10.0, total_questions=20, exam_format=enums.ExamFormat.MCQ_ONLY, target_difficulty=0.25
    )
    assert all(c["num_questions"] >= 1 for c in cells)


def test_allocate_cells_points_each_even_within_basket_regardless_of_bloom():
    """Điểm/câu không được lệch theo Bloom (bug đã sửa: trước đây câu Bloom cao lại ít điểm
    hơn vì dùng chung trọng số Gauss cho cả số câu lẫn điểm) — trong CÙNG 1 rổ (TN/TL), mọi
    ô phải cùng điểm/câu, TRỪ tối đa 1 ô do `_reconcile_total` chỉnh để khớp tổng điểm."""
    unit_ids = [uuid4() for _ in range(4)]
    weights = blueprint_recommendation.normalize_unit_weights(dict.fromkeys(unit_ids, 1.0))
    cells = blueprint_recommendation.allocate_cells(
        weights, total_points=10.0, total_questions=30, exam_format=enums.ExamFormat.MCQ_ONLY, target_difficulty=0.31
    )
    bloom_levels_present = {c["bloom_level"] for c in cells}
    assert len(bloom_levels_present) >= 3
    points_values = [c["points_each"] for c in cells]
    mode_value = max(set(points_values), key=points_values.count)
    outliers = [p for p in points_values if p != mode_value]
    assert len(outliers) <= 1


def test_validate_size_inputs_passes_when_feasible():
    blueprint_recommendation._validate_size_inputs(10.0, 20)  # không raise


def test_validate_size_inputs_raises_when_infeasible():
    with pytest.raises(blueprint_recommendation.RecommendationInputError):
        blueprint_recommendation._validate_size_inputs(5.0, 30)  # 30*0.25=7.5 > 5 điểm


def test_derive_exam_format_mcq_only():
    cells = [{"question_type": "MCQ"}, {"question_type": "TRUE_FALSE"}]
    assert blueprint_recommendation.derive_exam_format(cells) == enums.ExamFormat.MCQ_ONLY


def test_derive_exam_format_essay_only():
    assert blueprint_recommendation.derive_exam_format([{"question_type": "ESSAY"}]) == enums.ExamFormat.ESSAY_ONLY


def test_derive_exam_format_mixed():
    cells = [{"question_type": "MCQ"}, {"question_type": "ESSAY"}]
    assert blueprint_recommendation.derive_exam_format(cells) == enums.ExamFormat.MIXED


def test_derive_exam_format_empty_cells_returns_none():
    assert blueprint_recommendation.derive_exam_format([]) is None


# ============================================================
# TẦNG DB (fake db, không chạm Neon)
# ============================================================


def test_estimate_ability_tier1_uses_content_adjusted_ranking(monkeypatch):
    rows = [SimpleNamespace(content_adjusted_ability=7.0), SimpleNamespace(content_adjusted_ability=5.0)]
    monkeypatch.setattr(exam_validity, "content_adjusted_ranking", lambda *a, **k: rows)

    ability, note = blueprint_recommendation.estimate_ability(
        db=MagicMock(),
        school_id=uuid4(),
        grade_id=uuid4(),
        subject_id=uuid4(),
        semester_id=uuid4(),
        score_category=enums.ScoreCategory.FINAL,
    )

    assert ability == 6.0
    assert "CDI" in note


def test_estimate_ability_tier2_falls_back_to_raw_average(monkeypatch):
    monkeypatch.setattr(exam_validity, "content_adjusted_ranking", lambda *a, **k: [])
    db = SimpleNamespace(execute=lambda *_a, **_k: SimpleNamespace(first=lambda: SimpleNamespace(avg_score=6.8)))

    ability, note = blueprint_recommendation.estimate_ability(
        db=db,
        school_id=uuid4(),
        grade_id=uuid4(),
        subject_id=uuid4(),
        semester_id=uuid4(),
        score_category=enums.ScoreCategory.FINAL,
    )

    assert ability == 6.8
    assert "trung bình thô" in note


def test_estimate_ability_tier3_defaults_when_no_data(monkeypatch):
    monkeypatch.setattr(exam_validity, "content_adjusted_ranking", lambda *a, **k: [])
    db = SimpleNamespace(execute=lambda *_a, **_k: SimpleNamespace(first=lambda: None))

    ability, note = blueprint_recommendation.estimate_ability(
        db=db,
        school_id=uuid4(),
        grade_id=uuid4(),
        subject_id=uuid4(),
        semester_id=uuid4(),
        score_category=enums.ScoreCategory.FINAL,
    )

    assert ability == 6.5
    assert "chuẩn" in note


def test_validate_grade_in_school_passes_when_matching():
    school_id = uuid4()
    db = MagicMock()
    db.get.return_value = SimpleNamespace(school_id=school_id)
    blueprint_recommendation._validate_grade_in_school(db, school_id, uuid4())  # không raise


def test_validate_grade_in_school_raises_for_other_school():
    db = MagicMock()
    db.get.return_value = SimpleNamespace(school_id=uuid4())
    with pytest.raises(blueprint_recommendation.RecommendationInputError):
        blueprint_recommendation._validate_grade_in_school(db, uuid4(), uuid4())


def test_validate_grade_in_school_raises_when_missing():
    db = MagicMock()
    db.get.return_value = None
    with pytest.raises(blueprint_recommendation.RecommendationInputError):
        blueprint_recommendation._validate_grade_in_school(db, uuid4(), uuid4())


def test_validate_units_belong_passes_when_all_found():
    unit_ids = [uuid4(), uuid4()]
    db = SimpleNamespace(execute=lambda _stmt: SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: unit_ids)))
    blueprint_recommendation._validate_units_belong(db, uuid4(), 8, unit_ids)  # không raise


def test_validate_units_belong_raises_when_missing():
    unit_a, unit_b = uuid4(), uuid4()
    db = SimpleNamespace(execute=lambda _stmt: SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [unit_a])))
    with pytest.raises(blueprint_recommendation.RecommendationInputError):
        blueprint_recommendation._validate_units_belong(db, uuid4(), 8, [unit_a, unit_b])


def test_expand_chapters_no_children_kept_as_is():
    uid = uuid4()
    db = SimpleNamespace(execute=lambda _stmt: SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [])))
    expanded, notes = blueprint_recommendation._expand_chapters_to_lessons(db, [uid])
    assert expanded == [uid]
    assert notes == []


def test_expand_chapters_samples_children_when_present(monkeypatch):
    chapter_id = uuid4()
    children = [uuid4() for _ in range(10)]
    db = SimpleNamespace(
        execute=lambda _stmt: SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: children)),
        get=lambda _model, _id: SimpleNamespace(name="Chương Test"),
    )
    monkeypatch.setattr(blueprint_recommendation.random, "sample", lambda pool, k: pool[:k])
    expanded, notes = blueprint_recommendation._expand_chapters_to_lessons(db, [chapter_id])
    assert len(expanded) == 7  # ceil(10*0.7) = 7
    assert all(e in children for e in expanded)
    assert len(notes) == 1
    assert "Chương Test" in notes[0]
    assert "7/10" in notes[0]


def test_expand_chapters_minimum_one_lesson_for_small_chapter():
    chapter_id = uuid4()
    children = [uuid4()]
    db = SimpleNamespace(
        execute=lambda _stmt: SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: children)),
        get=lambda _model, _id: SimpleNamespace(name="Chương Nhỏ"),
    )
    expanded, notes = blueprint_recommendation._expand_chapters_to_lessons(db, [chapter_id])
    assert expanded == children


def test_expand_chapters_mixed_list_only_expands_ones_with_children(monkeypatch):
    plain_unit = uuid4()
    chapter_id = uuid4()
    children = [uuid4(), uuid4()]

    def fake_execute(_stmt):
        # Giả lập: chỉ chapter_id có con; plain_unit không có (lesson hoặc chương chưa có bài).
        call_count = fake_execute.calls
        fake_execute.calls += 1
        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: children if call_count == 1 else []))

    fake_execute.calls = 0
    db = SimpleNamespace(execute=fake_execute, get=lambda _model, _id: SimpleNamespace(name="Chương X"))
    monkeypatch.setattr(blueprint_recommendation.random, "sample", lambda pool, k: pool[:k])
    expanded, notes = blueprint_recommendation._expand_chapters_to_lessons(db, [plain_unit, chapter_id])
    assert plain_unit in expanded  # không có con -> giữ nguyên
    assert chapter_id not in expanded  # có con -> bị thay bằng bài học con
    assert set(children) <= set(expanded)
    assert len(notes) == 1


def test_misconception_counts_groups_by_unit():
    unit_a, unit_b = uuid4(), uuid4()
    db = SimpleNamespace(execute=lambda _stmt: SimpleNamespace(all=lambda: [(unit_a, 5), (unit_b, 2)]))
    result = blueprint_recommendation._misconception_counts(db, uuid4(), uuid4(), 8, [unit_a, unit_b])
    assert result == {unit_a: 5, unit_b: 2}


def test_weak_units_filters_below_threshold():
    unit_weak, unit_ok = uuid4(), uuid4()
    db = SimpleNamespace(execute=lambda _stmt: SimpleNamespace(all=lambda: [(unit_weak, 0.3), (unit_ok, 0.8)]))
    result = blueprint_recommendation._weak_units(db, uuid4(), uuid4(), 8, [unit_weak, unit_ok])
    assert result == {unit_weak}


def test_uncovered_units_returns_units_not_in_recent_exams():
    covered, uncovered_unit = uuid4(), uuid4()
    db = SimpleNamespace(execute=lambda _stmt: SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [covered])))
    result = blueprint_recommendation._uncovered_units(db, uuid4(), uuid4(), uuid4(), uuid4(), [covered, uncovered_unit])
    assert result == {uncovered_unit}


def test_unit_names_maps_id_to_name():
    uid = uuid4()
    db = SimpleNamespace(execute=lambda _stmt: SimpleNamespace(all=lambda: [(uid, "Phân thức")]))
    assert blueprint_recommendation._unit_names(db, {uid}) == {uid: "Phân thức"}


def test_unit_names_empty_set_skips_query():
    db = MagicMock()
    assert blueprint_recommendation._unit_names(db, set()) == {}
    db.execute.assert_not_called()


# ============================================================
# recommend() — lắp ráp toàn bộ (mock các hàm con)
# ============================================================


def test_recommend_end_to_end_builds_draft(monkeypatch):
    subject_id, grade_id, semester_id = uuid4(), uuid4(), uuid4()
    unit_a, unit_b = uuid4(), uuid4()
    req = RecommendBlueprintRequest(
        subject_id=subject_id,
        grade_number=8,
        grade_id=grade_id,
        semester_id=semester_id,
        score_category=enums.ScoreCategory.FINAL,
        unit_ids=[unit_a, unit_b],
        total_points=10.0,
        exam_format=enums.ExamFormat.MIXED,
        total_questions=20,
    )
    monkeypatch.setattr(blueprint_recommendation, "_validate_grade_in_school", lambda *a, **k: None)
    monkeypatch.setattr(blueprint_recommendation, "_validate_units_belong", lambda *a, **k: None)
    monkeypatch.setattr(blueprint_recommendation, "estimate_ability", lambda *a, **k: (6.5, "ghi chú năng lực"))
    monkeypatch.setattr(blueprint_recommendation, "_expand_chapters_to_lessons", lambda db, ids: (ids, []))
    monkeypatch.setattr(blueprint_recommendation, "_misconception_counts", lambda *a, **k: {unit_a: 2})
    monkeypatch.setattr(blueprint_recommendation, "_weak_units", lambda *a, **k: set())
    monkeypatch.setattr(blueprint_recommendation, "_uncovered_units", lambda *a, **k: {unit_b})
    monkeypatch.setattr(blueprint_recommendation, "_unit_names", lambda db, ids: {unit_a: "A", unit_b: "B"})
    monkeypatch.setattr(exam_assembly, "count_candidates_for_cell", lambda *a, **k: 10)

    draft = blueprint_recommendation.recommend(db=MagicMock(), school_id=uuid4(), req=req)

    assert draft.target_difficulty == pytest.approx(0.35)
    assert draft.ability_used == 6.5
    assert draft.cells
    assert all(c.available == 10 and c.shortfall == 0 for c in draft.cells)
    assert draft.expected_cdi is not None
    assert "ghi chú năng lực" in draft.rationale
    assert any("chưa xuất hiện" in r for r in draft.rationale)


def test_recommend_reports_shortfall_when_kho_thin(monkeypatch):
    unit_a = uuid4()
    req = RecommendBlueprintRequest(
        subject_id=uuid4(),
        grade_number=8,
        grade_id=uuid4(),
        semester_id=uuid4(),
        score_category=enums.ScoreCategory.MIDTERM,
        unit_ids=[unit_a],
        total_points=10.0,
        exam_format=enums.ExamFormat.MCQ_ONLY,
        total_questions=20,
    )
    monkeypatch.setattr(blueprint_recommendation, "_validate_grade_in_school", lambda *a, **k: None)
    monkeypatch.setattr(blueprint_recommendation, "_validate_units_belong", lambda *a, **k: None)
    monkeypatch.setattr(blueprint_recommendation, "estimate_ability", lambda *a, **k: (6.5, "ghi chú"))
    monkeypatch.setattr(blueprint_recommendation, "_expand_chapters_to_lessons", lambda db, ids: (ids, []))
    monkeypatch.setattr(blueprint_recommendation, "_misconception_counts", lambda *a, **k: {})
    monkeypatch.setattr(blueprint_recommendation, "_weak_units", lambda *a, **k: set())
    monkeypatch.setattr(blueprint_recommendation, "_uncovered_units", lambda *a, **k: set())
    monkeypatch.setattr(blueprint_recommendation, "_unit_names", lambda db, ids: {unit_a: "A"})
    monkeypatch.setattr(exam_assembly, "count_candidates_for_cell", lambda *a, **k: 0)

    draft = blueprint_recommendation.recommend(db=MagicMock(), school_id=uuid4(), req=req)

    assert all(c.available == 0 for c in draft.cells)
    assert all(c.shortfall == c.num_questions for c in draft.cells)

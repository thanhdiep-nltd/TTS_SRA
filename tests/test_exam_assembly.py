"""Test offline (không chạm DB) cho logic ráp đề từ ngân hàng câu hỏi."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.models import enums
from src.services import exam_assembly


def _item(**overrides):
    base = {
        "id": uuid4(),
        "p_value": None,
        "bloom_level": 2,
        "discrimination": None,
        "times_used": 0,
        "exposure_at": None,
        "options": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


# ----------------------------- item_difficulty -----------------------------


def test_item_difficulty_uses_empirical_when_available():
    """Có p_value -> độ khó = 1 − p_value (thực nghiệm thắng proxy Bloom)."""
    assert exam_assembly.item_difficulty(0.3, bloom_level=1) == pytest.approx(0.7)


def test_item_difficulty_falls_back_to_bloom_proxy():
    """Chưa dùng (p_value None) -> proxy Bloom/6."""
    assert exam_assembly.item_difficulty(None, bloom_level=3) == pytest.approx(0.5)


# ----------------------------- select_for_cell -----------------------------


def test_select_prefers_difficulty_near_target():
    """Chọn câu có độ khó gần target nhất trước."""
    easy = _item(p_value=0.9, bloom_level=1)  # difficulty 0.1
    mid = _item(p_value=0.5, bloom_level=2)  # difficulty 0.5
    hard = _item(p_value=0.1, bloom_level=3)  # difficulty 0.9
    picked = exam_assembly.select_for_cell([easy, hard, mid], num_questions=1, target=0.5)
    assert picked == [mid]


def test_select_tiebreak_prefers_higher_discrimination_then_less_used():
    """Cùng độ khó: ưu tiên phân biệt cao, rồi ít dùng hơn."""
    a = _item(p_value=0.5, discrimination=0.2, times_used=0)
    b = _item(p_value=0.5, discrimination=0.6, times_used=5)  # disc cao hơn -> trước
    c = _item(p_value=0.5, discrimination=0.6, times_used=1)  # cùng disc, ít dùng hơn -> trước b
    picked = exam_assembly.select_for_cell([a, b, c], num_questions=2, target=0.5)
    assert picked == [c, b]


# ----------------------------- _select_all_cells (thiếu câu) -----------------------------


def test_insufficient_items_raises(monkeypatch):
    """Kho không đủ câu cho một ô -> InsufficientItemsError (KHÔNG tự bịa câu)."""
    monkeypatch.setattr(exam_assembly, "_candidates_for_cell", lambda *a, **k: [_item()])
    blueprint = SimpleNamespace(
        school_id=uuid4(),
        subject_id=uuid4(),
        grade_number=8,
        target_difficulty=0.5,
        cells=[
            {"unit_id": str(uuid4()), "bloom_level": 2, "question_type": "MCQ", "num_questions": 3, "points_each": 1.0}
        ],
    )
    with pytest.raises(exam_assembly.InsufficientItemsError):
        exam_assembly._select_all_cells(db=None, blueprint=blueprint)


# ----------------------------- build_variants -----------------------------


def test_first_variant_keeps_canonical_order():
    """Mã đề đầu giữ nguyên thứ tự câu + không xáo đáp án."""
    opts = [{"key": "A", "text": "x"}, {"key": "B", "text": "y"}]
    items = [_item(options=opts), _item(options=opts)]
    variants = exam_assembly.build_variants(items, num_variants=2, seed=1)
    first = variants[0]
    assert first["variant_code"] == "101"
    assert [e["item"] for e in first["items"]] == items
    assert all(e["option_order"] is None for e in first["items"])


def test_variant_codes_increment_from_101():
    items = [_item()]
    variants = exam_assembly.build_variants(items, num_variants=3, seed=7)
    assert [v["variant_code"] for v in variants] == ["101", "102", "103"]


def test_variants_are_reproducible_with_same_seed():
    """Cùng seed -> cùng kết quả xáo (tái lập được, phục vụ in lại đề)."""
    items = [_item(options=[{"key": "A"}, {"key": "B"}, {"key": "C"}]) for _ in range(4)]
    v1 = exam_assembly.build_variants(items, 3, seed=42)
    v2 = exam_assembly.build_variants(items, 3, seed=42)
    order1 = [[e["item"].id for e in var["items"]] for var in v1]
    order2 = [[e["item"].id for e in var["items"]] for var in v2]
    assert order1 == order2


# ----------------------------- shuffle_options -----------------------------


def test_shuffle_options_returns_key_order_preserving_correct_answer():
    """Xáo đáp án giữ nguyên key gốc -> vẫn map được đáp án đúng."""
    import random

    opts = [{"key": "A"}, {"key": "B"}, {"key": "C"}, {"key": "D"}]
    shuffled, order = exam_assembly.shuffle_options(opts, random.Random(3))
    assert set(order) == {"A", "B", "C", "D"}  # đủ key, chỉ đổi thứ tự
    assert [o["key"] for o in shuffled] == order


def test_shuffle_options_none_for_essay():
    import random

    assert exam_assembly.shuffle_options(None, random.Random(1)) == (None, None)


# ----------------------------- compute_cdi -----------------------------


def test_compute_cdi_matches_tevi_formula():
    """CDI = Σ(điểm·bloom)/Σđiểm /6. 70% Bloom1-2 + 30% Bloom3 ≈ 0.325 (Phụ lục design doc)."""
    # 7 câu bloom ~1.5 (xấp xỉ bằng 0.5đ mỗi câu) + 3 câu bloom 3
    pairs = [(0.5, 1)] * 4 + [(0.5, 2)] * 3 + [(1.0, 3)] * 3
    cdi = exam_assembly.compute_cdi(pairs)
    assert 0.30 <= cdi <= 0.45


def test_compute_cdi_none_when_no_points():
    assert exam_assembly.compute_cdi([]) is None


# ----------------------------- difficulty_band -----------------------------


def test_difficulty_band_thresholds():
    assert exam_assembly.difficulty_band(0.30) == enums.Difficulty.EASY
    assert exam_assembly.difficulty_band(0.50) == enums.Difficulty.MEDIUM
    assert exam_assembly.difficulty_band(0.80) == enums.Difficulty.HARD
    assert exam_assembly.difficulty_band(None) is None


# ----------------------------- _build_competencies -----------------------------


def test_build_competencies_aggregates_weight_by_unit():
    """Gộp điểm theo unit -> weight = Σđiểm_unit/tổng; bloom = TB có trọng số (làm tròn)."""
    unit_a, unit_b = uuid4(), uuid4()
    item_a = SimpleNamespace(unit_id=unit_a, bloom_level=2)
    item_b = SimpleNamespace(unit_id=unit_b, bloom_level=4)
    item_map = {1: item_a, 2: item_b}
    rows = [SimpleNamespace(item_id=1, points=6.0), SimpleNamespace(item_id=2, points=4.0)]
    comps = exam_assembly._build_competencies(rows, item_map, total=10.0)
    by_unit = {c["unit_id"]: c for c in comps}
    assert by_unit[unit_a]["weight"] == pytest.approx(0.6)
    assert by_unit[unit_b]["weight"] == pytest.approx(0.4)
    assert by_unit[unit_a]["bloom_level"] == 2


def test_mark_exposed_increments_usage_and_sets_timestamp():
    items = [_item(times_used=0, exposure_at=None), _item(times_used=2, exposure_at=None)]
    before = datetime.now(UTC)
    exam_assembly._mark_exposed(db=None, items=items)
    assert items[0].times_used == 1 and items[1].times_used == 3
    assert all(it.exposure_at >= before for it in items)


# ----------------------------- count_candidates_for_cell -----------------------------


def test_count_candidates_for_cell_returns_scalar():
    """Dùng để báo thiếu câu KHI SOẠN ma trận (trước khi ráp) — chỉ đếm, không tải full rows."""

    class _FakeDB:
        def execute(self, _stmt):
            return SimpleNamespace(scalar_one=lambda: 3)

    cell = {"unit_id": str(uuid4()), "bloom_level": 2, "question_type": "MCQ"}
    result = exam_assembly.count_candidates_for_cell(_FakeDB(), uuid4(), uuid4(), 8, cell)
    assert result == 3

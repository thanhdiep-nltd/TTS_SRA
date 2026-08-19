"""Unit test cho src/services/knowledge_gap.py — phát hiện lỗ hổng kiến thức (M2)."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from src.api.v1.knowledge_gap import _unit_meta
from src.services.knowledge_gap import UnitWeight, aggregate_class_gaps, compute_unit_mastery


def test_unit_meta_maps_chapter_and_lesson():
    fake = MagicMock()
    fake.execute.return_value.fetchall.return_value = [
        SimpleNamespace(id=1, name="Nguyên hàm", parent_id=101, chapter_name="Nguyên hàm – Tích phân", summary=None, keywords=None),
        SimpleNamespace(id=2, name="Chương X", parent_id=None, chapter_name=None, summary="Tóm tắt chương X", keywords=["số học"]),
    ]
    meta = _unit_meta(fake, [1, 2])
    assert meta[1] == ("Nguyên hàm", "Nguyên hàm – Tích phân", "Nguyên hàm", None, None)
    assert meta[2] == ("Chương X", "Chương X", None, "Tóm tắt chương X", ["số học"])
    assert _unit_meta(fake, []) == {}


def test_uniform_units_mastery_equals_score_ratio():
    # 2 unit cùng Bloom 3 (factor 1.0), weight bằng nhau → mastery = score ratio.
    units = [UnitWeight(unit_id=1, weight=0.5, bloom_level=3), UnitWeight(unit_id=2, weight=0.5, bloom_level=3)]
    result = compute_unit_mastery(total_score=5.0, max_score=10.0, units=units)
    assert result[0].mastery == 0.5
    assert result[1].mastery == 0.5


def test_higher_bloom_lower_mastery():
    # Unit 2 khó hơn (Bloom 6) → mastery thấp hơn unit 1 (Bloom 1).
    units = [UnitWeight(unit_id=1, weight=0.5, bloom_level=1), UnitWeight(unit_id=2, weight=0.5, bloom_level=6)]
    result = compute_unit_mastery(total_score=8.0, max_score=10.0, units=units)
    assert result[0].mastery > result[1].mastery


def test_gap_detection_threshold():
    # Điểm thấp → unit có mastery < 0.6 bị đánh dấu is_gap.
    units = [UnitWeight(unit_id=1, weight=1.0, bloom_level=3)]
    result = compute_unit_mastery(total_score=4.0, max_score=10.0, units=units)
    assert result[0].is_gap is True
    assert result[0].gap_score > 0.4


def test_no_gap_when_high_score():
    units = [UnitWeight(unit_id=1, weight=1.0, bloom_level=3)]
    result = compute_unit_mastery(total_score=9.0, max_score=10.0, units=units)
    assert result[0].is_gap is False


def test_zero_weight_falls_back_to_uniform():
    # LLM trả toàn weight 0 → coi trọng số đều.
    units = [UnitWeight(unit_id=1, weight=0.0), UnitWeight(unit_id=2, weight=0.0)]
    result = compute_unit_mastery(total_score=5.0, max_score=10.0, units=units)
    assert result[0].mastery == 0.5
    assert result[1].mastery == 0.5


def test_empty_units():
    assert compute_unit_mastery(total_score=5.0, max_score=10.0, units=[]) == []


def test_aggregate_class_gaps():
    units = [UnitWeight(unit_id=1, weight=1.0, bloom_level=3), UnitWeight(unit_id=2, weight=1.0, bloom_level=3)]
    s1 = compute_unit_mastery(total_score=3.0, max_score=10.0, units=units)
    s2 = compute_unit_mastery(total_score=5.0, max_score=10.0, units=units)
    agg = aggregate_class_gaps([s1, s2])
    # unit 1 gap trung bình = (0.7 + 0.5)/2 = 0.6
    assert agg[1] == 0.6
    assert agg[2] == 0.6

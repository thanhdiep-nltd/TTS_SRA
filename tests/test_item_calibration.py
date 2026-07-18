"""Test offline cho luật hiệu chỉnh kho câu (calibration loop)."""

from src.services import item_calibration


def test_negative_discrimination_flags_retire():
    flags = item_calibration.calibration_flags(p_value=0.6, discrimination=-0.18, bloom_level=2)
    assert "NEGATIVE_DISCRIMINATION" in flags
    assert item_calibration.recommendation(flags) == "RETIRE"


def test_low_discrimination_flags_review():
    flags = item_calibration.calibration_flags(p_value=0.6, discrimination=0.1, bloom_level=2)
    assert flags == ["LOW_DISCRIMINATION"]
    assert item_calibration.recommendation(flags) == "REVIEW"


def test_difficulty_drift_when_empirical_far_from_bloom_proxy():
    # bloom 2 -> dự đoán độ khó ~0.33; p=0.15 -> thực nghiệm 0.85 -> lệch 0.52 > 0.35
    flags = item_calibration.calibration_flags(p_value=0.15, discrimination=0.4, bloom_level=2)
    assert flags == ["DIFFICULTY_DRIFT"]
    assert item_calibration.recommendation(flags) == "REVIEW"


def test_healthy_item_has_no_flags():
    flags = item_calibration.calibration_flags(p_value=0.65, discrimination=0.45, bloom_level=2)
    assert flags == []
    assert item_calibration.recommendation(flags) is None


def test_missing_stats_yield_no_flags():
    assert item_calibration.calibration_flags(p_value=None, discrimination=None, bloom_level=3) == []

"""src/services/knowledge_gap.py — Phát hiện lỗ hổng kiến thức của học sinh theo unit (M2).

Mục tiêu: với 1 đề thi (đã map unit qua exam_competencies) + điểm tổng của học sinh,
ước lượng mức độ thành thạo (mastery) từng unit → unit nào thấp = hổng kiến thức.

Nguyên tắc (theo plan M2.1):
    - DB không lưu điểm từng câu → dùng xấp xỉ có trọng số: phân bổ điểm tổng về từng
      unit theo weight, hiệu chỉnh theo bloom_level (Bloom cao → khó hơn).
    - unit_mastery = clamp01(điểm_phân_bổ_unit / trọng_số_unit_tối_đa).
    - gap_score = 1 - mastery (cao = hổng nặng).

Module này là hàm THUẦN (không DB, không LLM) → dễ unit test.
"""

from __future__ import annotations

from pydantic import BaseModel

# Bloom level → hệ số khó tương đối (Bloom 1 dễ nhất, 6 khó nhất).
_BLOOM_DIFFICULTY = {1: 0.5, 2: 0.7, 3: 1.0, 4: 1.3, 5: 1.6, 6: 2.0}

# Ngưỡng mastery: dưới mức này coi là "hổng".
GAP_MASTERY_THRESHOLD = 0.6


class UnitWeight(BaseModel):
    """1 unit trong đề: trọng số + mức Bloom."""

    unit_id: int
    weight: float  # 0..1, tổng các unit ≈ 1
    bloom_level: int = 3  # 1..6


class UnitMastery(BaseModel):
    """Kết quả mastery 1 unit của 1 học sinh."""

    unit_id: int
    mastery: float  # 0..1
    gap_score: float  # 0..1, cao = hổng nặng
    is_gap: bool


def _bloom_factor(bloom_level: int) -> float:
    """Hệ số khó theo Bloom (mặc định 1.0 nếu ngoài 1..6)."""
    return _BLOOM_DIFFICULTY.get(bloom_level, 1.0)


def compute_unit_mastery(
    total_score: float,
    max_score: float,
    units: list[UnitWeight],
) -> list[UnitMastery]:
    """Ước lượng mastery từng unit từ điểm tổng của 1 học sinh trên 1 đề.

    total_score: điểm tổng học sinh đạt (0..max_score).
    max_score: điểm tối đa của đề (thường 10).
    units: danh sách unit trong đề (weight + bloom_level).
    Công thức:
        mastery_u = clamp01( (total_score / max_score) * (bloom_factor_trung_bình / bloom_factor_u) )
    Trong đó bloom_factor_trung_bình = Σ(weight_u * bloom_factor_u) / Σ(weight_u).
    Unit có Bloom cao hơn trung bình → mastery thấp hơn (khó hơn), và ngược lại.
    """
    if not units:
        return []

    total_weight = sum(u.weight for u in units)
    if total_weight <= 0:
        # Trọng số đều nếu LLM trả toàn weight 0.
        weights = [1.0 / len(units)] * len(units)
    else:
        weights = [u.weight / total_weight for u in units]

    avg_bloom_factor = sum(w * _bloom_factor(u.bloom_level) for w, u in zip(weights, units, strict=False))

    score_ratio = total_score / max_score if max_score > 0 else 0.0
    score_ratio = max(0.0, min(1.0, score_ratio))

    results: list[UnitMastery] = []
    for w, u in zip(weights, units, strict=False):
        bf = _bloom_factor(u.bloom_level)
        # Unit khó hơn trung bình (bf cao) → mastery giảm; dễ hơn → mastery tăng.
        relative = avg_bloom_factor / bf if bf > 0 else 1.0
        mastery = max(0.0, min(1.0, score_ratio * relative))
        gap = round(1.0 - mastery, 3)
        results.append(
            UnitMastery(
                unit_id=u.unit_id,
                mastery=round(mastery, 3),
                gap_score=gap,
                is_gap=mastery < GAP_MASTERY_THRESHOLD,
            )
        )
    return results


def aggregate_class_gaps(
    student_gaps: list[list[UnitMastery]],
) -> dict[int, float]:
    """Gộp lỗ hổng của nhiều học sinh → unit hổng phổ biến của lớp.

    student_gaps: danh sách kết quả compute_unit_mastery của từng học sinh.
    Trả dict {unit_id: gap_score trung bình} (chỉ unit có gap_score > 0).
    """
    acc: dict[int, list[float]] = {}
    for gaps in student_gaps:
        for g in gaps:
            if g.gap_score > 0:
                acc.setdefault(g.unit_id, []).append(g.gap_score)

    return {uid: round(sum(v) / len(v), 3) for uid, v in acc.items()}

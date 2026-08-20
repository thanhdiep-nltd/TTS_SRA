"""src/services/item_mastery.py — Độ thành thạo theo chương từ LMS Item-Level + đối soát chống gian lận.

Mục tiêu: từ dữ liệu item-response (mỗi câu hỏi trắc nghiệm LMS) của 1 học sinh, ước lượng
mức độ thành thạo (mastery) cho TỪNG chương (curriculum_units), sau đó đối soát với điểm thi
trên lớp (giám thị) để hạ nhiệt gian lận và xuất confidence/integrity.

Khác `src/services/knowledge_gap.py` (chỉ dùng điểm tổng → ill-posed): module này dùng
Item-Response Matrix để giải bài toán dưới xác định bằng nhiều phép đo trên cùng chương.

Module này là hàm THUẦN (không DB, không LLM) → dễ unit test.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

# Tái dùng bảng hệ số khó Bloom của knowledge_gap (không import để tránh phụ thuộc vòng tròn).
_BLOOM_DIFFICULTY = {1: 0.5, 2: 0.7, 3: 1.0, 4: 1.3, 5: 1.6, 6: 2.0}

# Ngưỡng: số câu tối thiểu trên 1 chương để coi là có đủ dữ liệu.
MIN_ITEMS = 5
COVERAGE_MIN = 0.6  # dưới mức này → INSUFFICIENT / confidence LOW
GAP_MASTERY_THRESHOLD = 0.6  # đồng nhất với knowledge_gap

# Ngưỡng đối soát Δ = raw − exam.
DELTA_MATCH = 0.15  # |Δ| ≤ 0.15 → khớp chặt (HIGH)
DELTA_WARN = 0.30   # |Δ| trên mức này → lệch mạnh (gian lận / lười)

Confidence = Literal["HIGH", "MEDIUM", "LOW", "INSUFFICIENT"]


@dataclass(frozen=True)
class ItemResult:
    """1 câu response hợp lệ (đã lọc nhiễu) dùng để tính mastery."""

    unit_id: int
    bloom_level: int = 3
    score_received: float = 0.0
    max_score: float = 1.0


@dataclass
class UnitMastery:
    """Mastery 1 chương của 1 học sinh từ item-response + đối soát."""

    unit_id: int
    raw_mastery: float | None = None  # None = thiếu dữ liệu
    n_items: int = 0
    n_correct: int = 0
    coverage: float = 0.0
    lm_weight: float = 0.0
    exam_weight: float = 0.0
    adjusted_mastery: float | None = None
    confidence: str = "INSUFFICIENT"
    evidence_source: str = "LMS"
    integrity_status: str = "INSUFFICIENT"
    is_gap: bool = False
    evidence_detail: dict = field(default_factory=dict)


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def raw_unit_mastery(items: list[ItemResult]) -> UnitMastery:
    """Tính mastery thô Bloom-weighted + coverage cho 1 chương từ các item đã lọc.

    items: các câu response của học sinh thuộc 1 unit (đã chọn is_best, bỏ nhiễu).
    raw_u = Σ(score_received × bloom_factor) / Σ(max_score × bloom_factor).
    """
    n = len(items)
    if n == 0:
        return UnitMastery(unit_id=0)
    total_max = sum(i.max_score * _BLOOM_DIFFICULTY.get(i.bloom_level, 1.0) for i in items)
    if total_max <= 0:
        return UnitMastery(unit_id=items[0].unit_id, n_items=n)
    total_earned = sum(i.score_received * _BLOOM_DIFFICULTY.get(i.bloom_level, 1.0) for i in items)
    n_correct = sum(1 for i in items if i.score_received > 0)
    coverage = min(1.0, n / MIN_ITEMS)
    raw = _clamp01(total_earned / total_max)
    confidence: str = "HIGH" if coverage >= COVERAGE_MIN else "MEDIUM"
    return UnitMastery(
        unit_id=items[0].unit_id,
        raw_mastery=round(raw, 4),
        n_items=n,
        n_correct=n_correct,
        coverage=round(coverage, 3),
        confidence=confidence,
        integrity_status="OK",
        evidence_detail={"n_items": n, "coverage": round(coverage, 3)},
    )


def merge_onclass_adjustment(
    raw: UnitMastery,
    exam_mastery: float | None,
    delta_match: float = DELTA_MATCH,
    delta_warn: float = DELTA_WARN,
) -> UnitMastery:
    """Đối soát LMS ↔ điểm thi trên lớp (bất cân xứng) → adjusted + confidence + integrity.

    exam_mastery: mastery của unit từ compute_unit_mastery (điểm thi trên lớp, giám thị);
                  None nếu không có đề/điểm thi trên lớp.
    """
    if raw.raw_mastery is None:
        raw.integrity_status = "INSUFFICIENT"
        raw.confidence = "INSUFFICIENT"
        return raw

    if exam_mastery is None:
        raw.lm_weight, raw.exam_weight = 1.0, 0.0
        raw.adjusted_mastery = raw.raw_mastery
        raw.confidence = raw.confidence if raw.confidence == "HIGH" else "LOW"
        raw.evidence_source = "LMS"
        raw.integrity_status = "LMS_ONLY"
        return raw

    delta = raw.raw_mastery - exam_mastery
    raw.evidence_detail["delta"] = round(delta, 4)
    raw.evidence_detail["exam_mastery"] = round(exam_mastery, 4)

    if abs(delta) <= delta_match:
        lm, ex, conf, status = 0.8, 0.2, "HIGH", "OK"
    elif abs(delta) <= delta_warn:
        lm, ex, conf, status = 0.6, 0.4, "MEDIUM", "OK"
    elif delta > delta_warn:
        # LMS ≫ thi → nghi gian lận (chép bài/dùng AI): bias mạnh về thi.
        lm, ex, conf, status = 0.2, 0.8, "LOW", "SUSPECTED_CHEATING"
    else:  # delta < -delta_warn: LMS ≪ thi → lười/kém tham gia, không phạt gian lận.
        lm, ex, conf, status = 0.3, 0.7, "MEDIUM", "LOW_ENGAGEMENT"

    raw.lm_weight, raw.exam_weight = lm, ex
    raw.confidence = conf
    raw.integrity_status = status
    raw.evidence_source = "HYBRID"
    raw.adjusted_mastery = round(_clamp01(lm * raw.raw_mastery + ex * exam_mastery), 4)
    raw.is_gap = bool(raw.adjusted_mastery < GAP_MASTERY_THRESHOLD)
    return raw


def finalize_mastery(items: list[ItemResult], exam_mastery: float | None) -> UnitMastery:
    """Pipeline đầy đủ: raw → đối soát → trả UnitMastery hoàn chỉnh cho 1 chương.

    items: item-response đã lọc của 1 unit (best attempt, không nhiễu).
    exam_mastery: mastery từ điểm thi trên lớp (None nếu không có).
    """
    raw = raw_unit_mastery(items)
    if raw.raw_mastery is not None:
        raw = merge_onclass_adjustment(raw, exam_mastery)
    return raw


def compute_evidence_source(student_total_items: int) -> str:
    """Phân loại nguồn bằng chứng tổng thể của 1 học sinh/môn:
    'INSUFFICIENT_STUDENT' nếu chưa có item nào → báo 'chưa đủ dữ liệu để đánh giá học sinh'."""
    if student_total_items == 0:
        return "INSUFFICIENT_STUDENT"
    return "VALID"

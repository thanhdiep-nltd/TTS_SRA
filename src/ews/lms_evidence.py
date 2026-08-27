"""src/ews/lms_evidence.py — Phân loại hành vi làm bài LMS thành bằng chứng giải trình EWS.

Mục đích: biến dữ liệu LMS thô (điểm, thời gian, số lần thử, trạng thái nộp) thành các
"bằng chứng" có thể lý giải được tại sao học sinh học tệ, phục vụ EWS explainability (M3).

Các nhãn hành vi (pattern):
    - SKIPPED          : không nộp bài (bỏ bê).
    - RUSHED           : làm qua loa / đoán mò (active_time cực ngắn, rte=0).
    - OFF_TASK         : treo máy (time_spent cao nhưng active_time thấp + nhiều lần rời tab).
    - EFFORT_BUT_LOST  : nỗ lực nhưng không hiểu (active_time cao + rte=1 + điểm thấp).
    - WEAK_CHAPTER     : điểm thấp ở chương này (không rơi vào các nhãn trên).
    - MISSING_IN_EXAM  : unit có trong đề nhưng LMS cùng unit không làm (mất kiến thức).

Lưu ý quan trọng (theo nghiên cứu deepsearch_about_outliner_response_time.md):
    - KHÔNG dùng `time_spent_sec` thô để kết luận "nỗ lực" — phải dùng `active_time_sec`.
    - Bản ghi OFF_TASK / RUSHED là NHIỄU, không được dùng làm bằng chứng năng lực.

Module này là hàm THUẦN (không DB, không LLM) → dễ unit test.
"""

from __future__ import annotations

from pydantic import BaseModel

# Ngưỡng phân loại (tham số, có thể hiệu chỉnh sau).
RAPID_GUESS_ACTIVE_RATIO = 0.1   # active_time < 10% time_limit → đoán mò
EFFORT_ACTIVE_RATIO = 0.6        # active_time > 60% time_limit → nỗ lực
OFF_TASK_ACTIVE_FRACTION = 0.3   # active_time < 30% time_spent → treo máy
LOW_SCORE = 5.0                  # điểm < 5.0 coi là thấp


class LmsAssignmentEvidence(BaseModel):
    """1 bài LMS đã map unit — input cho phân loại hành vi."""

    unit_name: str
    final_grade: float | None = None
    active_time_sec: int | None = None
    time_spent_sec: int | None = None
    time_limit_sec: int | None = None
    attempt_count: int = 1
    tab_hidden_count: int = 0
    rte: int | None = None  # 1=effortful, 0=rapid-guess/off-task
    submitted: bool = True


class EvidencePattern(BaseModel):
    """Kết quả phân loại 1 bài LMS."""

    unit_name: str
    pattern: str
    explanation: str


def _active_ratio(a: LmsAssignmentEvidence) -> float | None:
    """Tỷ lệ active_time / time_limit (None nếu thiếu dữ liệu)."""
    if a.active_time_sec is None or not a.time_limit_sec:
        return None
    return a.active_time_sec / a.time_limit_sec


def _active_fraction(a: LmsAssignmentEvidence) -> float | None:
    """Tỷ lệ active_time / time_spent (None nếu thiếu dữ liệu)."""
    if a.active_time_sec is None or not a.time_spent_sec:
        return None
    return a.active_time_sec / a.time_spent_sec


def _is_low_score(a: LmsAssignmentEvidence) -> bool:
    """Điểm thấp (None coi là không xác định → không kết luận thấp)."""
    return a.final_grade is not None and a.final_grade < LOW_SCORE


def _classify_one(a: LmsAssignmentEvidence) -> EvidencePattern | None:
    """Phân loại 1 bài LMS → EvidencePattern (None = không có bằng chứng bất thường)."""
    if not a.submitted:
        return EvidencePattern(
            unit_name=a.unit_name,
            pattern="SKIPPED",
            explanation=f"Không nộp bài LMS chương '{a.unit_name}'.",
        )

    # Rapid guessing: rte=0 hoặc active_time cực ngắn.
    ratio = _active_ratio(a)
    if a.rte == 0 or (ratio is not None and ratio < RAPID_GUESS_ACTIVE_RATIO):
        return EvidencePattern(
            unit_name=a.unit_name,
            pattern="RUSHED",
            explanation=f"Làm qua loa / đoán mò chương '{a.unit_name}' (thời gian tương tác quá ngắn).",
        )

    # Off-task: treo máy (time_spent cao nhưng active thấp, hoặc rời tab nhiều).
    fraction = _active_fraction(a)
    if (fraction is not None and fraction < OFF_TASK_ACTIVE_FRACTION) or a.tab_hidden_count >= 3:
        return EvidencePattern(
            unit_name=a.unit_name,
            pattern="OFF_TASK",
            explanation=f"Treo máy khi làm chương '{a.unit_name}' (dữ liệu nhiễu, không dùng làm bằng chứng).",
        )

    # Nỗ lực nhưng không hiểu: active_time cao + rte=1 + điểm thấp.
    if ratio is not None and ratio > EFFORT_ACTIVE_RATIO and _is_low_score(a):
        return EvidencePattern(
            unit_name=a.unit_name,
            pattern="EFFORT_BUT_LOST",
            explanation=f"Nỗ lực làm lâu chương '{a.unit_name}' nhưng điểm thấp → chưa hiểu kiến thức.",
        )

    # Điểm thấp đơn thuần.
    if _is_low_score(a):
        return EvidencePattern(
            unit_name=a.unit_name,
            pattern="WEAK_CHAPTER",
            explanation=f"Điểm thấp ở chương '{a.unit_name}'.",
        )

    return None


def classify_lms_behavior(assignments: list[LmsAssignmentEvidence]) -> list[EvidencePattern]:
    """Phân loại hành vi LMS cho danh sách bài tập (đã map unit).

    Trả danh sách EvidencePattern (bỏ qua bài không có bằng chứng bất thường).
    """
    patterns: list[EvidencePattern] = []
    for a in assignments:
        p = _classify_one(a)
        if p is not None:
            patterns.append(p)
    return patterns


def mark_missing_in_exam(
    exam_units: list[str],
    lms_units: set[str],
) -> list[EvidencePattern]:
    """Phát hiện unit có trong đề nhưng học sinh KHÔNG làm LMS cùng unit.

    exam_units: danh sách tên unit xuất hiện trong đề (từ exam_competencies).
    lms_units: tập tên unit học sinh đã làm trên LMS.
    Trả EvidencePattern MISSING_IN_EXAM cho mỗi unit thiếu.
    """
    missing: list[EvidencePattern] = []
    for unit in exam_units:
        if unit not in lms_units:
            missing.append(
                EvidencePattern(
                    unit_name=unit,
                    pattern="MISSING_IN_EXAM",
                    explanation=f"Chương '{unit}' có trong đề nhưng không làm LMS → mất kiến thức.",
                )
            )
    return missing

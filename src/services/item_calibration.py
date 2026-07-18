"""Vòng hiệu chỉnh kho câu hỏi (calibration loop) — Classical Test Theory mức MVP.

Sau khi câu được dùng trong đề và có thống kê (p_value = tỉ lệ làm đúng, discrimination = độ
phân biệt), hệ tự gắn cờ câu "bệnh" để Trưởng bộ môn xử lý: phân biệt ÂM (HS giỏi sai nhiều
hơn HS yếu -> gần như chắc chắn đáp án/đề sai) đề nghị RETIRE; phân biệt thấp hoặc độ khó lệch
xa dự đoán Bloom -> đề nghị rà lại. DEMO: thống kê mock từ scripts/seed_item_stats_toan.py.
"""

_LOW_DISCRIMINATION = 0.2
_DRIFT_THRESHOLD = 0.35


def calibration_flags(p_value: float | None, discrimination: float | None, bloom_level: int) -> list[str]:
    """Cờ 'bệnh' của một câu dựa trên thống kê thực nghiệm; thiếu thống kê -> không cờ."""
    flags: list[str] = []
    if discrimination is not None:
        if float(discrimination) < 0:
            flags.append("NEGATIVE_DISCRIMINATION")
        elif float(discrimination) < _LOW_DISCRIMINATION:
            flags.append("LOW_DISCRIMINATION")
    if p_value is not None:
        empirical = 1.0 - float(p_value)  # độ khó thực nghiệm (cao = khó)
        predicted = bloom_level / 6.0  # proxy Bloom (khớp exam_assembly.item_difficulty)
        if abs(empirical - predicted) > _DRIFT_THRESHOLD:
            flags.append("DIFFICULTY_DRIFT")
    return flags


def recommendation(flags: list[str]) -> str | None:
    """RETIRE khi phân biệt âm; REVIEW khi có cờ khác; None khi khỏe mạnh."""
    if "NEGATIVE_DISCRIMINATION" in flags:
        return "RETIRE"
    return "REVIEW" if flags else None

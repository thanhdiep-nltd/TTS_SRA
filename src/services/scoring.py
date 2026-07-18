"""Cấu trúc cột điểm + công thức tính ĐTB (theo private_docs/detail_table_score.md).

Cấu trúc 1 học kỳ (THCS/THPT): Miệng×3, Thường xuyên×4, Giữa kỳ×2, Cuối kỳ×1.
Hệ số: Miệng & TX = 1, Giữa kỳ = 2, Cuối kỳ = 3.
ĐTB HK = Σ(hệ_số × điểm) / Σ(hệ_số) trên các đầu điểm HIỆN CÓ.
ĐTB CN = (ĐTB HK1 × 1 + ĐTB HK2 × 2) / 3.
"""

from src.models.enums import ScoreCategory

# Số cột cho mỗi nhóm
COLUMN_COUNT: dict[ScoreCategory, int] = {
    ScoreCategory.ORAL: 3,
    ScoreCategory.REGULAR: 4,
    ScoreCategory.MIDTERM: 2,
    ScoreCategory.FINAL: 1,
}

WEIGHT: dict[ScoreCategory, int] = {
    ScoreCategory.ORAL: 1,
    ScoreCategory.REGULAR: 1,
    ScoreCategory.MIDTERM: 2,
    ScoreCategory.FINAL: 3,
}

# Nhóm nào được phép map đề thi (Miệng: không)
MAPPABLE = {ScoreCategory.REGULAR, ScoreCategory.MIDTERM, ScoreCategory.FINAL}

# Danh sách cột theo thứ tự hiển thị/biểu đồ
SCORE_COLUMNS: list[tuple[ScoreCategory, int]] = [
    (cat, idx)
    for cat in (ScoreCategory.ORAL, ScoreCategory.REGULAR, ScoreCategory.MIDTERM, ScoreCategory.FINAL)
    for idx in range(1, COLUMN_COUNT[cat] + 1)
]

_HL_BANDS = [(8.0, "Giỏi"), (6.5, "Khá"), (5.0, "Trung bình"), (3.5, "Yếu")]


def column_key(category: ScoreCategory, index: int) -> str:
    """Khóa chuỗi cho 1 ô điểm, ví dụ 'REGULAR_2'."""
    return f"{category.value}_{index}"


def column_label(category: ScoreCategory, index: int) -> str:
    if category == ScoreCategory.ORAL:
        return f"Miệng {index}"
    if category == ScoreCategory.REGULAR:
        return f"TX{index}"
    if category == ScoreCategory.MIDTERM:
        return f"GK{index}"
    return "Cuối kỳ"


def dtb_semester(scores: dict[ScoreCategory, list[float]]) -> float | None:
    """ĐTB học kỳ — trung bình có trọng số trên các đầu điểm hiện có."""
    num = 0.0
    den = 0
    for category, values in scores.items():
        w = WEIGHT[category]
        for v in values:
            num += w * v
            den += w
    return round(num / den, 2) if den else None


def dtb_year(hk1: float | None, hk2: float | None) -> float | None:
    if hk1 is None or hk2 is None:
        return None
    return round((hk1 + 2 * hk2) / 3, 2)


def hoc_luc(avg: float | None) -> str | None:
    if avg is None:
        return None
    for threshold, label in _HL_BANDS:
        if avg >= threshold:
            return label
    return "Kém"

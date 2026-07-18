from collections import defaultdict

from src.models.enums import ScoreCategory
from src.services import scoring


def _score_type_str(score) -> str:
    """Nhãn TX/GK/CK gọn cho các chỉ số CHỦ ĐÍCH chỉ dùng thường xuyên/cuối kỳ (GDI, Momentum)
    — KHÔNG dùng để tính ĐTB môn (xem `subject_average_and_rank`), vì bỏ qua điểm Miệng.
    """
    cat = score.score_category.value if hasattr(score.score_category, "value") else str(score.score_category)
    idx = score.column_index
    if cat == "REGULAR":
        return f"TX{idx}"
    elif cat == "MIDTERM":
        return "GK"
    elif cat == "FINAL":
        return "CK"
    elif cat == "ORAL":
        return f"ORAL{idx}"
    return "UNKNOWN"


def group_scores_by_category(score_objs) -> dict[ScoreCategory, list[float]]:
    """Gom danh sách Score (ORM) theo `score_category` — đầu vào cho `services.scoring.dtb_semester`."""
    grouped: dict[ScoreCategory, list[float]] = defaultdict(list)
    for s in score_objs:
        grouped[s.score_category].append(float(s.value))
    return grouped


def subject_average_and_rank(score_objs) -> tuple[float | None, str | None]:
    """ĐTB môn học kỳ + học lực của 1 học sinh/môn, dùng ĐÚNG công thức chính thức
    (`src/services/scoring.py` — cũng là công thức bảng điểm `/scores/gradebook` đang dùng):
    có tính điểm Miệng (hệ số 1) và tính trung bình có trọng số trên các đầu điểm HIỆN CÓ,
    không yêu cầu phải đủ TX1-4 + GK + CK như công thức CSV cũ.
    """
    dtb = scoring.dtb_semester(group_scores_by_category(score_objs))
    return dtb, scoring.hoc_luc(dtb)


def score_breakdown(score_objs) -> dict[str, float]:
    """Điểm từng đầu điểm hiện có của 1 học sinh/môn, nhãn hiển thị khớp bảng điểm chính thức
    (Miệng 1-3/TX1-4/GK1-2/Cuối kỳ), theo đúng thứ tự cột hiển thị (`scoring.SCORE_COLUMNS`)."""
    by_col = {(s.score_category, s.column_index): float(s.value) for s in score_objs}
    return {
        scoring.column_label(cat, idx): by_col[(cat, idx)] for cat, idx in scoring.SCORE_COLUMNS if (cat, idx) in by_col
    }

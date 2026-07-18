"""Test offline cho src/agents/helpers.py sau khi sửa bug ĐTB (audit 2026-07-02):

data_agent/stat_agent trước đây dùng công thức ĐTB kiểu CSV cũ — bỏ qua điểm Miệng và bắt
buộc phải đủ TX1-4+GK+CK mới tính được, khác với công thức chính thức ở services/scoring.py
mà bảng điểm /scores/gradebook đang dùng. Test này khóa lại hành vi ĐÚNG: agent phải cho ra
kết quả khớp 1-1 với services/scoring.py.

Chạy offline: dùng SimpleNamespace giả lập ORM Score, không chạm DB thật.
"""

from types import SimpleNamespace

from src.agents.helpers import group_scores_by_category, score_breakdown, subject_average_and_rank
from src.models.enums import ScoreCategory
from src.services import scoring


def _score(category: ScoreCategory, index: int, value: float):
    return SimpleNamespace(score_category=category, column_index=index, value=value)


def test_subject_average_includes_oral_scores():
    """Bug cũ: điểm Miệng (ORAL) bị bỏ hoàn toàn khỏi ĐTB. Giờ phải được tính, hệ số 1."""
    scores = [
        _score(ScoreCategory.ORAL, 1, 10.0),
        _score(ScoreCategory.REGULAR, 1, 8.0),
        _score(ScoreCategory.MIDTERM, 1, 8.0),
        _score(ScoreCategory.FINAL, 1, 8.0),
    ]
    dtb, rank = subject_average_and_rank(scores)
    expected = scoring.dtb_semester(
        {
            ScoreCategory.ORAL: [10.0],
            ScoreCategory.REGULAR: [8.0],
            ScoreCategory.MIDTERM: [8.0],
            ScoreCategory.FINAL: [8.0],
        }
    )
    assert dtb == expected
    # (10*1 + 8*1 + 8*2 + 8*3) / (1+1+2+3) = 58/7 ~= 8.29 -> khác 8.0 nếu bỏ Miệng
    assert dtb != 8.0


def test_subject_average_tolerates_partial_data():
    """Bug cũ: thiếu bất kỳ ô nào trong TX1-4/GK/CK -> trả None. Giờ vẫn tính trên phần có sẵn."""
    scores = [_score(ScoreCategory.REGULAR, 1, 7.0), _score(ScoreCategory.REGULAR, 2, 9.0)]
    dtb, rank = subject_average_and_rank(scores)
    assert dtb == 8.0  # (7+9)/2, hệ số TX = 1 cho cả hai
    assert rank == "Giỏi"  # >= 8.0 theo _HL_BANDS trong services/scoring.py


def test_subject_average_empty_returns_none():
    dtb, rank = subject_average_and_rank([])
    assert dtb is None
    assert rank is None


def test_subject_average_matches_gradebook_formula_exactly():
    """Đối chiếu 1-1 với services/scoring.py — nguồn công thức chính thức của bảng điểm."""
    scores = [
        _score(ScoreCategory.ORAL, 1, 9.0),
        _score(ScoreCategory.ORAL, 2, 7.0),
        _score(ScoreCategory.REGULAR, 1, 8.0),
        _score(ScoreCategory.REGULAR, 2, 6.0),
        _score(ScoreCategory.MIDTERM, 1, 7.5),
        _score(ScoreCategory.FINAL, 1, 8.5),
    ]
    dtb, rank = subject_average_and_rank(scores)
    by_cat = group_scores_by_category(scores)
    assert dtb == scoring.dtb_semester(by_cat)
    assert rank == scoring.hoc_luc(dtb)


def test_rank_labels_use_official_5_band_scale():
    """Bug cũ dùng nhãn 'Tốt/Khá/Đạt/Chưa đạt' (4 mức) khác bảng điểm thật.

    Nhãn đúng phải khớp _HL_LABELS ở gradebook.py: Giỏi/Khá/Trung bình/Yếu/Kém.
    """
    _, rank_gioi = subject_average_and_rank([_score(ScoreCategory.FINAL, 1, 9.0)])
    _, rank_kem = subject_average_and_rank([_score(ScoreCategory.FINAL, 1, 2.0)])
    assert rank_gioi == "Giỏi"
    assert rank_kem == "Kém"
    assert rank_gioi in ("Giỏi", "Khá", "Trung bình", "Yếu", "Kém")
    assert rank_kem in ("Giỏi", "Khá", "Trung bình", "Yếu", "Kém")


def test_group_scores_by_category_groups_correctly():
    scores = [
        _score(ScoreCategory.REGULAR, 1, 7.0),
        _score(ScoreCategory.REGULAR, 2, 8.0),
        _score(ScoreCategory.FINAL, 1, 9.0),
    ]
    grouped = group_scores_by_category(scores)
    assert grouped[ScoreCategory.REGULAR] == [7.0, 8.0]
    assert grouped[ScoreCategory.FINAL] == [9.0]


def test_score_breakdown_labels_and_order():
    """Nhãn hiển thị phải khớp cột bảng điểm chính thức và đúng thứ tự Miệng -> TX -> GK -> CK."""
    scores = [
        _score(ScoreCategory.FINAL, 1, 9.0),
        _score(ScoreCategory.ORAL, 2, 10.0),
        _score(ScoreCategory.REGULAR, 1, 7.0),
    ]
    breakdown = score_breakdown(scores)
    assert list(breakdown.keys()) == ["Miệng 2", "TX1", "Cuối kỳ"]
    assert breakdown["Miệng 2"] == 10.0
    assert breakdown["TX1"] == 7.0
    assert breakdown["Cuối kỳ"] == 9.0


def test_score_breakdown_empty_for_no_scores():
    assert score_breakdown([]) == {}

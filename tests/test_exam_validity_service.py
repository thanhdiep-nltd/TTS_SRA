"""Test offline (không chạm DB) cho công thức tam giác hóa EDI/CDI."""

from types import SimpleNamespace

from src.models import enums
from src.services import exam_validity


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None


class _FakeSession:
    """Giả lập Session.execute trả về danh sách dòng cố định, không cần Postgres."""

    def __init__(self, rows):
        self._rows = rows
        self.last_params: dict | None = None

    def execute(self, _stmt, params=None):
        self.last_params = params
        return _FakeResult(self._rows)


class _SequentialFakeSession:
    """Giả lập Session.execute trả về lần lượt từng kết quả theo thứ tự gọi (cho hàm gọi nhiều query)."""

    def __init__(self, results):
        self._results = list(results)

    def execute(self, _stmt, _params=None):
        return _FakeResult(self._results.pop(0))


def _row(**overrides):
    base = {
        "exam_paper_id": 1,
        "subject_id": 1,
        "subject_name": "Toán",
        "semester_id": 1,
        "score_category": enums.ScoreCategory.FINAL,
        "grade_id": 8,
        "grade_name": "Khối 8",
        "n": 35,
        "mean_score": 4.8,
        "edi": 0.52,
        "cdi": 0.325,
        "divergence": 0.195,
        "flag": "LEARNING_GAP",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_confidence_high_when_enough_sample_and_cdi():
    assert exam_validity._confidence(30, 0.5) == "HIGH"


def test_confidence_low_when_sample_too_small():
    assert exam_validity._confidence(5, 0.5) == "LOW"


def test_confidence_low_when_no_cdi():
    assert exam_validity._confidence(100, None) == "LOW"


def test_inflation_flag_example_from_design_doc():
    """Phụ lục §13: mean=9.2 trên đề CDI=0.325 -> divergence âm mạnh -> INFLATION_OR_LEAK."""
    row = _row(edi=0.08, cdi=0.325, divergence=0.08 - 0.325, flag="INFLATION_OR_LEAK")
    result = exam_validity._row_to_read(row)
    assert result.flag == "INFLATION_OR_LEAK"
    assert result.divergence < -0.2


def test_learning_gap_flag_example_from_design_doc():
    """Phụ lục §13: mean=4.8 trên đề CDI=0.325 -> divergence dương -> LEARNING_GAP."""
    row = _row()
    result = exam_validity._row_to_read(row)
    assert result.flag == "LEARNING_GAP"
    assert result.confidence == "HIGH"


def test_compute_validity_filters_by_school_and_subject(monkeypatch):
    rows = [_row()]
    fake_db = _FakeSession(rows)
    so_school_id, subject_id, semester_id = 101, 1, 1
    result = exam_validity.compute_validity(fake_db, so_school_id, semester_id, subject_id, enums.ScoreCategory.FINAL)
    assert len(result) == 1
    assert result[0].flag == "LEARNING_GAP"


def test_compute_validity_scans_whole_school_when_subject_omitted():
    fake_db = _FakeSession([])
    exam_validity.compute_validity(fake_db, 101, 1)
    assert fake_db.last_params["subject_id"] is None
    assert fake_db.last_params["cat"] is None


def test_school_overview_excludes_valid_and_no_content_from_flagged_items():
    rows = [
        _row(flag="VALID", divergence=0.05),
        _row(flag="NO_CONTENT", cdi=None, divergence=None),
        _row(flag="LEARNING_GAP", divergence=0.3),
        _row(flag="INFLATION_OR_LEAK", divergence=-0.4),
    ]
    fake_db = _FakeSession(rows)
    overview = exam_validity.school_overview(fake_db, 101, 1)
    assert overview.total_checked == 4
    assert overview.flags_count == {"VALID": 1, "NO_CONTENT": 1, "LEARNING_GAP": 1, "INFLATION_OR_LEAK": 1}
    # Chỉ cờ bất thường, sắp xếp theo |divergence| giảm dần -> INFLATION_OR_LEAK (0.4) trước LEARNING_GAP (0.3)
    assert [i.flag for i in overview.flagged_items] == ["INFLATION_OR_LEAK", "LEARNING_GAP"]


def test_content_adjusted_ability_diverges_from_raw_average_when_cdi_high():
    """§2.5 design doc: đề khó (CDI cao) -> cộng bù thực lực, ability > raw_average (phá vòng lặp
    "TB cohort" cũ — hai lớp cùng raw_average nhưng đề khác độ khó nội dung sẽ KHÔNG cùng ability).
    """
    cdi_row = _row(cdi=0.8)
    class_rows = [SimpleNamespace(class_id=1, class_name="8A1", raw_average=6.0)]
    fake_db = _SequentialFakeSession([[cdi_row], class_rows])

    result = exam_validity.content_adjusted_ranking(
        fake_db, 101, 8, 1, 1, enums.ScoreCategory.FINAL
    )

    assert len(result) == 1
    row = result[0]
    assert row.raw_average == 6.0
    assert row.cdi == 0.8
    # k=3.0 -> ability = clamp(0..10, 6.0 + 3.0*(0.8-0.5)) = 6.9, khác hẳn raw_average.
    assert row.content_adjusted_ability == 6.9
    assert row.content_adjusted_ability != row.raw_average


def test_content_adjusted_ability_equals_raw_when_cdi_neutral():
    """CDI=0.5 (trung tính) -> không cộng/trừ gì -> ability == raw_average, đúng như §2.5."""
    cdi_row = _row(cdi=0.5)
    class_rows = [SimpleNamespace(class_id=2, class_name="8A2", raw_average=7.0)]
    fake_db = _SequentialFakeSession([[cdi_row], class_rows])

    result = exam_validity.content_adjusted_ranking(
        fake_db, 101, 8, 1, 1, enums.ScoreCategory.FINAL
    )

    assert result[0].content_adjusted_ability == result[0].raw_average == 7.0


def test_content_adjusted_ability_falls_back_to_raw_when_no_cdi():
    """Chưa có CDI (đề chưa được phân tích nội dung) -> không cộng bù, ability == raw_average."""
    fake_db = _SequentialFakeSession([[], [SimpleNamespace(class_id=3, class_name="8A3", raw_average=5.5)]])

    result = exam_validity.content_adjusted_ranking(
        fake_db, 101, 8, 1, 1, enums.ScoreCategory.FINAL
    )

    assert result[0].content_adjusted_ability == result[0].raw_average == 5.5

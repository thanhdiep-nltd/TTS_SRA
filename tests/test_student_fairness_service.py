"""Test offline (không chạm DB) cho công thức cảnh báo công bằng đánh giá cấp học sinh."""

from types import SimpleNamespace
from uuid import uuid4

from src.services import student_fairness


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeSession:
    """Giả lập Session.execute trả về danh sách dòng cố định + ghi lại params đã truyền."""

    def __init__(self, rows):
        self._rows = rows
        self.last_params: dict | None = None

    def execute(self, _stmt, params=None):
        self.last_params = params
        return _FakeResult(self._rows)


def _row(**overrides):
    base = {
        "student_id": uuid4(),
        "student_code": "HS001",
        "full_name": "Nguyễn Văn A",
        "class_id": uuid4(),
        "class_name": "6A1",
        "subject_id": uuid4(),
        "subject_name": "Toán",
        "tx_avg": 9.0,
        "tx_cdi": 0.7,
        "tx_n": 4,
        "periodic_avg": 4.0,
        "periodic_cdi": 0.3,
        "periodic_n": 2,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_favoritism_flag_when_tx_easy_to_ace_but_periodic_low():
    fake_db = _FakeSession([_row()])
    result = student_fairness.compute_fairness_signals(fake_db, uuid4(), uuid4())
    assert len(result) == 1
    assert result[0].flag == "SUSPECT_FAVORITISM"
    assert result[0].confidence == "HIGH"
    assert result[0].gap == 5.0
    assert "TX" in result[0].evidence and "5.0" in result[0].evidence


def test_suppression_flag_when_tx_low_but_periodic_high():
    row = _row(tx_avg=4.0, tx_cdi=0.3, periodic_avg=9.0, periodic_cdi=0.7)
    fake_db = _FakeSession([row])
    result = student_fairness.compute_fairness_signals(fake_db, uuid4(), uuid4())
    assert len(result) == 1
    assert result[0].flag == "SUSPECT_SUPPRESSION"
    assert result[0].gap == 5.0
    assert result[0].evidence


def test_normal_when_gap_small():
    row = _row(tx_avg=7.0, periodic_avg=6.5)
    fake_db = _FakeSession([row])
    result = student_fairness.compute_fairness_signals(fake_db, uuid4(), uuid4())
    assert result == []


def test_low_confidence_when_cdi_missing():
    row = _row(tx_cdi=None)
    fake_db = _FakeSession([row])
    result = student_fairness.compute_fairness_signals(fake_db, uuid4(), uuid4())
    assert len(result) == 1
    assert result[0].flag == "SUSPECT_FAVORITISM"
    assert result[0].confidence == "LOW"
    assert "chưa rõ" in result[0].evidence


def test_filters_by_school_id():
    school_id = uuid4()
    fake_db = _FakeSession([])
    student_fairness.compute_fairness_signals(fake_db, school_id, uuid4())
    assert fake_db.last_params["school_id"] == school_id


def test_subject_id_defaults_to_none_for_school_wide_scan():
    fake_db = _FakeSession([])
    student_fairness.compute_fairness_signals(fake_db, uuid4(), uuid4())
    assert fake_db.last_params["subject_id"] is None

"""Offline test cho logic bảng điểm mới: môn REMARK, đánh giá học tập, hạnh kiểm.

Kiểm tra hàm thuần _detail_row / _summary_row (không chạm DB).
"""

from types import SimpleNamespace
from uuid import uuid4

from src.api.v1.gradebook import _detail_row, _summary_row
from src.models import enums


def _student():
    return SimpleNamespace(id=uuid4(), student_code="HS001", full_name="Nguyen Van A")


def _subject(assessment=enums.AssessmentType.SCORED):
    return SimpleNamespace(id=uuid4(), name="Môn", code="M", assessment_type=assessment)


def _score(cat, value):
    return SimpleNamespace(score_category=cat, column_index=1, value=value, id=uuid4())


def test_detail_row_scored_computes_dtb_and_eval():
    st, subj = _student(), _subject()
    sem = uuid4()
    bucket = {(st.id, sem): [_score(enums.ScoreCategory.FINAL, 8.0)]}
    ev = SimpleNamespace(result=None, comment="Tiến bộ")
    row = _detail_row(st, subj, ev, bucket, (sem, sem, None))
    assert row.dtb_hk == 8.0
    assert row.evaluation == "Tiến bộ"
    assert row.result is None


def test_detail_row_remark_has_result_no_cells():
    st, subj = _student(), _subject(enums.AssessmentType.REMARK)
    ev = SimpleNamespace(result=enums.PassFail.DAT, comment="OK")
    row = _detail_row(st, subj, ev, {}, (uuid4(), None, None))
    assert row.result == "DAT"
    assert row.cells == {}
    assert row.dtb_hk is None


def test_summary_row_excludes_remark_from_overall():
    st = _student()
    scored, remark = _subject(), _subject(enums.AssessmentType.REMARK)
    bucket = {(st.id, scored.id): [_score(enums.ScoreCategory.FINAL, 9.0)]}
    evals = {(st.id, remark.id): SimpleNamespace(result=enums.PassFail.DAT, comment=None)}
    report = SimpleNamespace(conduct=enums.Conduct.TOT, general_comment="Ngoan")
    row = _summary_row(st, [scored, remark], bucket, evals, report)
    assert row.averages[str(scored.id)] == 9.0
    assert str(remark.id) not in row.averages  # môn REMARK không vào averages
    assert row.remarks[str(remark.id)] == "DAT"
    assert row.overall == 9.0  # overall chỉ từ môn SCORED
    assert row.conduct == "TOT"
    assert row.general_comment == "Ngoan"


def test_summary_row_no_report_is_none():
    st, scored = _student(), _subject()
    row = _summary_row(st, [scored], {}, {}, None)
    assert row.conduct is None
    assert row.general_comment is None
    assert row.overall is None

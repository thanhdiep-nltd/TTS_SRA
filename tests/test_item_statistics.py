"""Test offline (không chạm DB) cho vòng hiệu chỉnh kho câu hỏi sau khi đề được chấm."""

from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from src.models import enums
from src.services import exam_assembly, item_statistics

# ----------------------------- _exam_edi -----------------------------


def test_exam_edi_computes_one_minus_mean_over_ten():
    db = SimpleNamespace(execute=lambda _stmt: SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [8.0, 6.0])))
    edi = item_statistics._exam_edi(db, uuid4(), uuid4(), enums.ScoreCategory.FINAL, uuid4())
    assert edi == pytest.approx(1 - 7.0 / 10.0)


def test_exam_edi_none_when_no_approved_scores():
    db = SimpleNamespace(execute=lambda _stmt: SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [])))
    assert item_statistics._exam_edi(db, uuid4(), uuid4(), enums.ScoreCategory.FINAL, uuid4()) is None


# ----------------------------- update_from_exam -----------------------------


def _gen(exam_paper_id=None):
    return SimpleNamespace(
        id=uuid4(), blueprint_id=uuid4(), exam_paper_id=exam_paper_id, semester_id=uuid4(), grade_id=uuid4()
    )


def _blueprint():
    return SimpleNamespace(subject_id=uuid4(), score_category=enums.ScoreCategory.FINAL)


def test_update_from_exam_returns_zero_when_generated_exam_missing():
    db = MagicMock()
    db.get.return_value = None
    assert item_statistics.update_from_exam(db, uuid4()) == 0


def test_update_from_exam_returns_zero_when_not_finalized():
    db = MagicMock()
    db.get.return_value = _gen(exam_paper_id=None)
    assert item_statistics.update_from_exam(db, uuid4()) == 0


def test_update_from_exam_returns_zero_when_blueprint_missing():
    gen = _gen(exam_paper_id=uuid4())
    db = MagicMock()
    db.get.side_effect = lambda model, _id: gen if model is item_statistics.GeneratedExam else None
    assert item_statistics.update_from_exam(db, gen.id) == 0


def test_update_from_exam_returns_zero_when_no_approved_scores(monkeypatch):
    gen = _gen(exam_paper_id=uuid4())
    bp = _blueprint()
    db = MagicMock()
    db.get.side_effect = lambda model, _id: gen if model is item_statistics.GeneratedExam else bp
    monkeypatch.setattr(item_statistics, "_exam_edi", lambda *a, **k: None)
    assert item_statistics.update_from_exam(db, gen.id) == 0


def test_update_from_exam_returns_zero_when_no_items_found(monkeypatch):
    gen = _gen(exam_paper_id=uuid4())
    bp = _blueprint()
    db = MagicMock()
    db.get.side_effect = lambda model, _id: gen if model is item_statistics.GeneratedExam else bp
    monkeypatch.setattr(item_statistics, "_exam_edi", lambda *a, **k: 0.4)
    monkeypatch.setattr(exam_assembly, "_canonical_items", lambda _db, _gen: [])
    db.execute.return_value = SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))
    assert item_statistics.update_from_exam(db, gen.id) == 0


def test_update_from_exam_updates_p_value_by_relative_bloom_weight(monkeypatch):
    """Bloom cao hơn TB đề -> ước lượng khó hơn -> p_value thấp hơn (cùng EDI của cả đề)."""
    gen = _gen(exam_paper_id=uuid4())
    bp = _blueprint()
    db = MagicMock()
    db.get.side_effect = lambda model, _id: gen if model is item_statistics.GeneratedExam else bp
    monkeypatch.setattr(item_statistics, "_exam_edi", lambda *a, **k: 0.4)

    item_low = SimpleNamespace(id=uuid4(), bloom_level=1, p_value=None)
    item_high = SimpleNamespace(id=uuid4(), bloom_level=3, p_value=None)
    rows = [SimpleNamespace(item_id=item_low.id), SimpleNamespace(item_id=item_high.id)]
    monkeypatch.setattr(exam_assembly, "_canonical_items", lambda _db, _gen: rows)
    db.execute.return_value = SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [item_low, item_high]))

    updated = item_statistics.update_from_exam(db, gen.id)

    assert updated == 2
    assert item_low.p_value == pytest.approx(0.8)  # 1 - 0.4*(1/2)
    assert item_high.p_value == pytest.approx(0.4)  # 1 - 0.4*(3/2)
    assert item_high.p_value < item_low.p_value
    db.commit.assert_called_once()


# ----------------------------- update_from_exam_paper -----------------------------


def test_update_from_exam_paper_returns_zero_when_no_matching_generated_exam():
    db = MagicMock()
    db.execute.return_value = SimpleNamespace(scalar_one_or_none=lambda: None)
    assert item_statistics.update_from_exam_paper(db, uuid4()) == 0


def test_update_from_exam_paper_delegates_to_update_from_exam(monkeypatch):
    gen = _gen(exam_paper_id=uuid4())
    db = MagicMock()
    db.execute.return_value = SimpleNamespace(scalar_one_or_none=lambda: gen)
    monkeypatch.setattr(item_statistics, "update_from_exam", lambda _db, gen_id: 42 if gen_id == gen.id else 0)
    assert item_statistics.update_from_exam_paper(db, uuid4()) == 42

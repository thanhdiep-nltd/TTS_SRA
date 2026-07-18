"""Test offline (không chạm DB) cho helper thuần trong api/v1/exams.py.

Bug thật phát hiện qua review toàn nhánh: _apply_order() từng trả nguyên option dict
(gồm cả misconception — chỉ đáp án ĐÚNG có misconception=null) thẳng ra endpoint
GET /exams/{id} (đáp án ẩn — chỉ phục vụ in đề/đối soát). Ai đọc response cũng suy ra được
đáp án đúng bằng cách tìm option có misconception=null. Test này khóa lại hành vi đúng:
chỉ giữ key/text.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from src.api.v1 import exams
from src.models import enums
from src.services import rbac


def test_apply_order_strips_misconception_field():
    """Đáp án lộ ra qua endpoint in đề KHÔNG được có misconception (chỉ đáp án đúng có null -> lộ đáp án)."""
    options = [
        {"key": "A", "text": "1/2", "misconception": "cộng tử với tử"},
        {"key": "B", "text": "2/3", "misconception": None},
    ]
    result = exams._apply_order(options, None)
    assert result == [{"key": "A", "text": "1/2"}, {"key": "B", "text": "2/3"}]


def test_apply_order_strips_misconception_and_reorders():
    options = [
        {"key": "A", "text": "1/2", "misconception": "sai 1"},
        {"key": "B", "text": "2/3", "misconception": None},
    ]
    result = exams._apply_order(options, ["B", "A"])
    assert result == [{"key": "B", "text": "2/3"}, {"key": "A", "text": "1/2"}]


def test_apply_order_none_options_returns_none():
    assert exams._apply_order(None, None) is None


def test_apply_order_empty_options_returns_none():
    assert exams._apply_order([], None) is None


# ----------------------------- _validate_cells_sum -----------------------------


def test_validate_cells_sum_passes_when_matching():
    cells = [{"num_questions": 4, "points_each": 0.5}, {"num_questions": 2, "points_each": 1.0}]
    exams._validate_cells_sum(cells, total_points=4.0)  # không raise


def test_validate_cells_sum_raises_when_mismatched():
    cells = [{"num_questions": 4, "points_each": 0.5}]
    with pytest.raises(HTTPException) as exc:
        exams._validate_cells_sum(cells, total_points=10.0)
    assert exc.value.status_code == 422


# ----------------------------- _get_blueprint_in_school / _get_generated_exam_in_school -----------------------------


def test_get_blueprint_in_school_raises_404_when_missing():
    db = MagicMock()
    db.get.return_value = None
    with pytest.raises(HTTPException) as exc:
        exams._get_blueprint_in_school(db, uuid4(), uuid4())
    assert exc.value.status_code == 404


def test_get_blueprint_in_school_raises_404_when_other_school():
    db = MagicMock()
    db.get.return_value = SimpleNamespace(school_id=uuid4())
    with pytest.raises(HTTPException):
        exams._get_blueprint_in_school(db, uuid4(), uuid4())


def test_get_blueprint_in_school_returns_when_matching():
    school_id = uuid4()
    blueprint = SimpleNamespace(school_id=school_id)
    db = MagicMock()
    db.get.return_value = blueprint
    assert exams._get_blueprint_in_school(db, uuid4(), school_id) is blueprint


def test_get_generated_exam_in_school_raises_404_when_other_school():
    db = MagicMock()
    db.get.return_value = SimpleNamespace(school_id=uuid4())
    with pytest.raises(HTTPException):
        exams._get_generated_exam_in_school(db, uuid4(), uuid4())


def test_get_generated_exam_in_school_returns_when_matching():
    school_id = uuid4()
    gen = SimpleNamespace(school_id=school_id)
    db = MagicMock()
    db.get.return_value = gen
    assert exams._get_generated_exam_in_school(db, uuid4(), school_id) is gen


# ----------------------------- _can_edit_blueprint -----------------------------


def test_can_edit_blueprint_true_for_creator():
    creator_id = uuid4()
    blueprint = SimpleNamespace(created_by=creator_id, subject_id=uuid4())
    user = SimpleNamespace(id=creator_id, role=enums.UserRole.SUBJECT_TEACHER)
    assert exams._can_edit_blueprint(MagicMock(), user, blueprint) is True


def test_can_edit_blueprint_true_for_subject_head_of_subject(monkeypatch):
    blueprint = SimpleNamespace(created_by=uuid4(), subject_id=uuid4())
    user = SimpleNamespace(id=uuid4(), role=enums.UserRole.SUBJECT_HEAD)
    assigns = [SimpleNamespace(role_context=enums.RoleContext.SUBJECT_HEAD, subject_id=blueprint.subject_id)]
    monkeypatch.setattr(rbac, "_active_assignments", lambda db, uid: assigns)
    assert exams._can_edit_blueprint(MagicMock(), user, blueprint) is True


def test_can_edit_blueprint_false_for_unrelated_teacher(monkeypatch):
    blueprint = SimpleNamespace(created_by=uuid4(), subject_id=uuid4())
    user = SimpleNamespace(id=uuid4(), role=enums.UserRole.SUBJECT_TEACHER)
    monkeypatch.setattr(rbac, "_active_assignments", lambda db, uid: [])
    assert exams._can_edit_blueprint(MagicMock(), user, blueprint) is False


# ----------------------------- _variant_rows_with_items / _build_answer_keys -----------------------------


def test_variant_rows_with_items_maps_item_ids():
    item_a, item_b = SimpleNamespace(id=uuid4()), SimpleNamespace(id=uuid4())
    row1 = SimpleNamespace(item_id=item_a.id, variant_code="101", position=1)
    row2 = SimpleNamespace(item_id=item_b.id, variant_code="101", position=2)

    call_results = iter([[row1, row2], [item_a, item_b]])

    def _execute(_stmt):
        result = next(call_results)
        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: result))

    db = SimpleNamespace(execute=_execute)
    rows, item_map = exams._variant_rows_with_items(db, SimpleNamespace(id=uuid4()))

    assert rows == [row1, row2]
    assert item_map == {item_a.id: item_a, item_b.id: item_b}


def test_build_answer_keys_groups_by_variant_and_exposes_answer(monkeypatch):
    item = SimpleNamespace(id=uuid4(), answer_key={"correct": "B"}, solution="giải thích")
    row_101 = SimpleNamespace(item_id=item.id, variant_code="101", position=1, points=1.0)
    row_102 = SimpleNamespace(item_id=item.id, variant_code="102", position=1, points=1.0)
    monkeypatch.setattr(
        exams, "_variant_rows_with_items", lambda db, gen: ([row_101, row_102], {item.id: item})
    )

    result = exams._build_answer_keys(db=None, gen=SimpleNamespace(id=uuid4()))

    by_code = {v.variant_code: v for v in result}
    assert set(by_code) == {"101", "102"}
    assert by_code["101"].items[0].answer_key == {"correct": "B"}
    assert by_code["101"].items[0].solution == "giải thích"

"""Test offline cho các lỗ hổng phân quyền vừa vá (audit 2026-07-02):

- Điểm đã APPROVED không được GV thường sửa/xóa (chỉ ADMIN/PRINCIPAL).
- gradebook/class-summary kiểm tra lớp thuộc trường + user có quyền truy cập lớp.
- exam-papers: helper lấy đề trong đúng trường của user.

Chạy offline: mock Session/monkeypatch, không chạm DB thật.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from src.api.v1 import exam_papers, gradebook, scores
from src.models import enums
from src.services import rbac


def _user(role: enums.UserRole, school_id=None) -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), school_id=school_id or uuid4(), role=role)


# --- scores._require_not_locked -------------------------------------------------


def test_require_not_locked_blocks_teacher_on_approved_score():
    score = SimpleNamespace(status=enums.ScoreStatus.APPROVED)
    teacher = _user(enums.UserRole.SUBJECT_TEACHER)
    with pytest.raises(HTTPException) as exc:
        scores._require_not_locked(score, teacher)
    assert exc.value.status_code == 403


def test_require_not_locked_allows_admin_on_approved_score():
    score = SimpleNamespace(status=enums.ScoreStatus.APPROVED)
    admin = _user(enums.UserRole.ADMIN)
    scores._require_not_locked(score, admin)  # không raise


def test_require_not_locked_allows_teacher_on_draft_score():
    score = SimpleNamespace(status=enums.ScoreStatus.DRAFT)
    teacher = _user(enums.UserRole.SUBJECT_TEACHER)
    scores._require_not_locked(score, teacher)  # không raise


# --- gradebook._check_class_access ----------------------------------------------


def test_check_class_access_rejects_class_from_other_school(monkeypatch):
    user = _user(enums.UserRole.ADMIN)
    cls = SimpleNamespace(id=uuid4(), grade_id=uuid4())
    other_school_grade = SimpleNamespace(school_id=uuid4())
    db = MagicMock()
    db.get.return_value = other_school_grade
    with pytest.raises(HTTPException) as exc:
        gradebook._check_class_access(db, user, cls)
    assert exc.value.status_code == 404


def test_check_class_access_rejects_class_outside_assignment(monkeypatch):
    user = _user(enums.UserRole.SUBJECT_TEACHER)
    cls = SimpleNamespace(id=uuid4(), grade_id=uuid4())
    grade = SimpleNamespace(school_id=user.school_id)
    db = MagicMock()
    db.get.return_value = grade
    monkeypatch.setattr(rbac, "accessible_class_ids", lambda _db, _user: [uuid4()])  # not cls.id
    with pytest.raises(HTTPException) as exc:
        gradebook._check_class_access(db, user, cls)
    assert exc.value.status_code == 403


def test_check_class_access_allows_admin_same_school():
    user = _user(enums.UserRole.ADMIN)
    cls = SimpleNamespace(id=uuid4(), grade_id=uuid4())
    grade = SimpleNamespace(school_id=user.school_id)
    db = MagicMock()
    db.get.return_value = grade
    gradebook._check_class_access(db, user, cls)  # không raise


def test_check_class_access_rejects_missing_class():
    db = MagicMock()
    with pytest.raises(HTTPException) as exc:
        gradebook._check_class_access(db, _user(enums.UserRole.ADMIN), None)
    assert exc.value.status_code == 404


# --- gradebook._is_enrolled / scores._require_enrolled ---------------------------


def test_is_enrolled_true_when_row_found():
    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = uuid4()
    assert gradebook._is_enrolled(db, uuid4(), uuid4()) is True


def test_is_enrolled_false_when_no_row():
    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = None
    assert gradebook._is_enrolled(db, uuid4(), uuid4()) is False


def test_require_enrolled_raises_when_not_enrolled():
    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = None
    with pytest.raises(HTTPException) as exc:
        scores._require_enrolled(db, uuid4(), uuid4())
    assert exc.value.status_code == 400


# --- exam_papers._get_exam_in_school ---------------------------------------------


def test_get_exam_in_school_rejects_other_school():
    user = _user(enums.UserRole.ADMIN)
    paper = SimpleNamespace(id=uuid4(), school_id=uuid4())
    db = MagicMock()
    db.get.return_value = paper
    with pytest.raises(HTTPException) as exc:
        exam_papers._get_exam_in_school(db, paper.id, user)
    assert exc.value.status_code == 404


def test_get_exam_in_school_rejects_missing_paper():
    user = _user(enums.UserRole.ADMIN)
    db = MagicMock()
    db.get.return_value = None
    with pytest.raises(HTTPException) as exc:
        exam_papers._get_exam_in_school(db, uuid4(), user)
    assert exc.value.status_code == 404


def test_get_exam_in_school_allows_same_school():
    user = _user(enums.UserRole.ADMIN)
    paper = SimpleNamespace(id=uuid4(), school_id=user.school_id)
    db = MagicMock()
    db.get.return_value = paper
    result = exam_papers._get_exam_in_school(db, paper.id, user)
    assert result is paper

"""Test logic lọc lớp theo quyền (rbac.accessible_class_ids).

Chạy offline: mock Session + phân công, không chạm DB thật.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

from src.models import enums
from src.services import rbac


def _fake_db(class_ids: list | None = None) -> MagicMock:
    """Session giả: db.execute(...).scalars().all() trả về danh sách cho trước."""
    db = MagicMock()
    db.execute.return_value.scalars.return_value.all.return_value = class_ids or []
    return db


def _user(role: enums.UserRole) -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), school_id=uuid4(), role=role)


def test_full_access_roles_return_none(monkeypatch):
    """ADMIN/PRINCIPAL không giới hạn theo lớp (None = mọi lớp trong trường)."""
    db = _fake_db()
    for role in (enums.UserRole.ADMIN, enums.UserRole.PRINCIPAL):
        assert rbac.accessible_class_ids(db, _user(role)) is None


def test_teacher_without_assignments_returns_empty(monkeypatch):
    """GV chưa có phân công → không thấy lớp nào ([])."""
    monkeypatch.setattr(rbac, "_active_assignments", lambda db, uid: [])
    result = rbac.accessible_class_ids(_fake_db(), _user(enums.UserRole.SUBJECT_TEACHER))
    assert result == []


def test_subject_teacher_sees_assigned_classes(monkeypatch):
    """GV bộ môn chỉ thấy các lớp được phân công."""
    c1, c2 = uuid4(), uuid4()
    assigns = [
        SimpleNamespace(role_context=enums.RoleContext.SUBJECT_TEACHER, class_id=c1, grade_id=None, subject_id=uuid4()),
        SimpleNamespace(role_context=enums.RoleContext.SUBJECT_TEACHER, class_id=c2, grade_id=None, subject_id=uuid4()),
    ]
    monkeypatch.setattr(rbac, "_active_assignments", lambda db, uid: assigns)
    result = rbac.accessible_class_ids(_fake_db(), _user(enums.UserRole.SUBJECT_TEACHER))
    assert set(result) == {c1, c2}


def test_subject_head_returns_none(monkeypatch):
    """Trưởng bộ môn xem môn phụ trách ở mọi lớp → None."""
    assigns = [
        SimpleNamespace(role_context=enums.RoleContext.SUBJECT_HEAD, class_id=None, grade_id=None, subject_id=uuid4())
    ]
    monkeypatch.setattr(rbac, "_active_assignments", lambda db, uid: assigns)
    result = rbac.accessible_class_ids(_fake_db(), _user(enums.UserRole.SUBJECT_HEAD))
    assert result is None


def test_grade_head_expands_to_classes_of_grade(monkeypatch):
    """Trưởng khối thấy mọi lớp thuộc khối phụ trách (mở rộng từ grade_id)."""
    grade_id = uuid4()
    cls_a, cls_b = uuid4(), uuid4()
    assigns = [
        SimpleNamespace(role_context=enums.RoleContext.GRADE_HEAD, class_id=None, grade_id=grade_id, subject_id=None)
    ]
    monkeypatch.setattr(rbac, "_active_assignments", lambda db, uid: assigns)
    result = rbac.accessible_class_ids(_fake_db([cls_a, cls_b]), _user(enums.UserRole.GRADE_HEAD_PRIMARY))
    assert set(result) == {cls_a, cls_b}

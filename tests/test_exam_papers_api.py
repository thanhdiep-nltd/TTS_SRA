"""Test offline cho quyền xem `ai_analysis` ở GET /exam-papers/{id} (không chạm DB/HTTP thật)."""

from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

from src.api.v1.exam_papers import _can_view_analysis
from src.models import enums
from src.services import rbac


def _user(role: enums.UserRole) -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), school_id=uuid4(), role=role)


def test_admin_and_principal_can_always_view_analysis():
    db = MagicMock()
    for role in (enums.UserRole.ADMIN, enums.UserRole.PRINCIPAL):
        assert _can_view_analysis(db, _user(role), uuid4()) is True


def test_subject_teacher_of_matching_subject_can_view(monkeypatch):
    subject_id = uuid4()
    assigns = [SimpleNamespace(role_context=enums.RoleContext.SUBJECT_TEACHER, subject_id=subject_id)]
    monkeypatch.setattr(rbac, "_active_assignments", lambda db, uid: assigns)

    assert _can_view_analysis(MagicMock(), _user(enums.UserRole.SUBJECT_TEACHER), subject_id) is True


def test_subject_teacher_of_other_subject_cannot_view(monkeypatch):
    assigns = [SimpleNamespace(role_context=enums.RoleContext.SUBJECT_TEACHER, subject_id=uuid4())]
    monkeypatch.setattr(rbac, "_active_assignments", lambda db, uid: assigns)

    assert _can_view_analysis(MagicMock(), _user(enums.UserRole.SUBJECT_TEACHER), uuid4()) is False


def test_homeroom_teacher_without_subject_assignment_cannot_view(monkeypatch):
    monkeypatch.setattr(rbac, "_active_assignments", lambda db, uid: [])

    assert _can_view_analysis(MagicMock(), _user(enums.UserRole.HOMEROOM_TEACHER_PRIMARY), uuid4()) is False

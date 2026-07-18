"""Test offline (không chạm DB) cho RBAC của 3 endpoint exam-validity (TEVI)."""

import pytest
from fastapi import HTTPException

from src.api.deps import require_roles
from src.api.v1.exam_validity import _OVERVIEW_ROLES, _VALIDITY_READ_ROLES
from src.models import enums
from src.models.tables import User


def _user(role: enums.UserRole) -> User:
    return User(role=role)


@pytest.mark.parametrize("role", [enums.UserRole.ADMIN, enums.UserRole.PRINCIPAL, enums.UserRole.SUBJECT_HEAD])
def test_exam_validity_allows_read_roles(role):
    guard = require_roles(*_VALIDITY_READ_ROLES)
    user = _user(role)
    assert guard(user) is user


@pytest.mark.parametrize("role", [enums.UserRole.SUBJECT_TEACHER, enums.UserRole.HOMEROOM_TEACHER_PRIMARY])
def test_exam_validity_blocks_non_read_roles(role):
    guard = require_roles(*_VALIDITY_READ_ROLES)
    with pytest.raises(HTTPException) as exc:
        guard(_user(role))
    assert exc.value.status_code == 403


@pytest.mark.parametrize("role", [enums.UserRole.ADMIN, enums.UserRole.PRINCIPAL])
def test_overview_allows_admin_and_principal(role):
    guard = require_roles(*_OVERVIEW_ROLES)
    user = _user(role)
    assert guard(user) is user


def test_overview_blocks_subject_head():
    """SUBJECT_HEAD đọc được bảng tam giác hóa chi tiết, nhưng KHÔNG được xem tổng hợp toàn trường."""
    guard = require_roles(*_OVERVIEW_ROLES)
    with pytest.raises(HTTPException) as exc:
        guard(_user(enums.UserRole.SUBJECT_HEAD))
    assert exc.value.status_code == 403

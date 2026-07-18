"""Test offline cho router /users: quyền ghi ADMIN-only + query lọc/phân trang — không chạm DB thật."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select

from src.api.deps import get_current_user
from src.api.v1.users import _apply_user_filters
from src.main import app
from src.models import enums
from src.models.tables import User
from src.schemas.user import UserListParams


def _compiled(stmt) -> str:
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))


def _admin(school_id=None):
    return SimpleNamespace(id=uuid4(), role=enums.UserRole.ADMIN, school_id=school_id or uuid4(), is_active=True)


def _principal(school_id=None):
    return SimpleNamespace(id=uuid4(), role=enums.UserRole.PRINCIPAL, school_id=school_id or uuid4(), is_active=True)


# ---- Query builder ----


def test_filters_principal_forced_to_own_school():
    principal = _principal()
    stmt = _apply_user_filters(select(User), UserListParams(school_id=uuid4()), principal)
    sql = _compiled(stmt)
    assert str(principal.school_id).replace("-", "") in sql.replace("-", "")


def test_filters_admin_can_pick_school():
    other_school = uuid4()
    stmt = _apply_user_filters(select(User), UserListParams(school_id=other_school), _admin())
    assert str(other_school).replace("-", "") in _compiled(stmt).replace("-", "")


def test_filters_admin_without_school_sees_all():
    stmt = _apply_user_filters(select(User), UserListParams(), _admin())
    assert "WHERE" not in _compiled(stmt)


def test_filters_q_matches_name_or_email():
    stmt = _apply_user_filters(select(User), UserListParams(q="lan"), _admin())
    sql = _compiled(stmt)
    assert "full_name" in sql and "email" in sql and "OR" in sql


def test_filters_role_and_active():
    stmt = _apply_user_filters(
        select(User), UserListParams(role=enums.UserRole.SUBJECT_TEACHER, is_active=True), _admin()
    )
    sql = _compiled(stmt)
    assert "role" in sql and "is_active" in sql


# ---- Quyền ghi: PRINCIPAL bị 403 ----


@pytest.fixture
def principal_client(client):
    app.dependency_overrides[get_current_user] = lambda: _principal()
    yield client
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_principal_cannot_create_user(principal_client):
    res = await principal_client.post("/api/v1/users", json={})
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_principal_cannot_create_assignment(principal_client):
    res = await principal_client.post("/api/v1/users/assignments", json={})
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_principal_cannot_reset_password(principal_client):
    res = await principal_client.post(f"/api/v1/users/{uuid4()}/reset-password", json={"new_password": "abc123"})
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_principal_cannot_reassign(principal_client):
    res = await principal_client.put("/api/v1/users/assignments/reassign", json={})
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_teachers_endpoint_registered_and_requires_auth(client):
    res = await client.get(f"/api/v1/users/assignments/teachers?school_id={uuid4()}")
    assert res.status_code == 401

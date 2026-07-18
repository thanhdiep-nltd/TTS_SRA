"""Test offline cho vòng vá thứ 2 (audit 2026-07-02):

- Rate-limit đăng nhập theo email (login_rate_limit).
- Chuẩn hóa message 409 theo tên constraint DB (main.integrity_error_handler).
- Dọn refresh token hết hạn/thu hồi khi login (auth._cleanup_expired_tokens).
- can_write_score nhận `assignments` truyền sẵn (dedupe N+1 cho batch).

Chạy offline: mock Session/monkeypatch, không chạm DB thật.
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

from fastapi.testclient import TestClient

from src.api.v1.auth import _cleanup_expired_tokens
from src.main import _CONSTRAINT_MESSAGES, _SQLSTATE_FALLBACK, app, integrity_error_handler
from src.models import enums
from src.services import login_rate_limit, rbac

client = TestClient(app)


# --- login_rate_limit -------------------------------------------------------------


def test_login_rate_limit_locks_after_max_attempts():
    key = f"test-{uuid4()}@example.com"
    for _ in range(login_rate_limit._MAX_ATTEMPTS):
        assert not login_rate_limit.is_locked(key)
        login_rate_limit.register_failure(key)
    assert login_rate_limit.is_locked(key)


def test_login_rate_limit_reset_clears_lock():
    key = f"test-{uuid4()}@example.com"
    for _ in range(login_rate_limit._MAX_ATTEMPTS):
        login_rate_limit.register_failure(key)
    assert login_rate_limit.is_locked(key)
    login_rate_limit.reset(key)
    assert not login_rate_limit.is_locked(key)


def test_login_rate_limit_keys_are_independent():
    key_a, key_b = f"a-{uuid4()}@example.com", f"b-{uuid4()}@example.com"
    for _ in range(login_rate_limit._MAX_ATTEMPTS):
        login_rate_limit.register_failure(key_a)
    assert login_rate_limit.is_locked(key_a)
    assert not login_rate_limit.is_locked(key_b)


def test_login_endpoint_returns_429_when_locked():
    email = f"locked-{uuid4()}@example.com"
    for _ in range(login_rate_limit._MAX_ATTEMPTS):
        login_rate_limit.register_failure(email.lower())
    res = client.post("/api/v1/auth/login", json={"email": email, "password": "whatever"})
    assert res.status_code == 429
    login_rate_limit.reset(email.lower())


# --- 409 constraint mapping --------------------------------------------------------


def test_constraint_messages_cover_known_unique_constraints():
    assert _CONSTRAINT_MESSAGES["uq_users_email"] == "Email này đã được sử dụng bởi tài khoản khác."
    assert "uq_score_unique" in _CONSTRAINT_MESSAGES


def test_integrity_error_handler_uses_constraint_message():
    diag = SimpleNamespace(constraint_name="uq_users_email", sqlstate="23505")
    exc = SimpleNamespace(orig=SimpleNamespace(diag=diag))
    response = asyncio.run(integrity_error_handler(None, exc))
    assert response.status_code == 409
    assert "Email" in response.body.decode()


def test_integrity_error_handler_falls_back_to_sqlstate():
    diag = SimpleNamespace(constraint_name="some_unnamed_constraint", sqlstate="23503")
    exc = SimpleNamespace(orig=SimpleNamespace(diag=diag))
    response = asyncio.run(integrity_error_handler(None, exc))
    assert response.status_code == 409
    assert _SQLSTATE_FALLBACK["23503"] in response.body.decode()


def test_integrity_error_handler_generic_fallback_when_no_diag():
    exc = SimpleNamespace(orig=None)
    response = asyncio.run(integrity_error_handler(None, exc))
    assert response.status_code == 409
    assert "vi phạm" in response.body.decode()


# --- auth._cleanup_expired_tokens ---------------------------------------------------


def test_cleanup_expired_tokens_executes_delete():
    db = MagicMock()
    _cleanup_expired_tokens(db, uuid4())
    assert db.execute.called


# --- rbac.can_write_score with preloaded assignments --------------------------------


def _user(role: enums.UserRole) -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), school_id=uuid4(), role=role)


def test_can_write_score_uses_preloaded_assignments_without_db_query():
    class_id, subject_id = uuid4(), uuid4()
    assignments = [
        SimpleNamespace(
            role_context=enums.RoleContext.SUBJECT_TEACHER, subject_id=subject_id, class_id=class_id, grade_id=None
        )
    ]
    db = MagicMock()
    teacher = _user(enums.UserRole.SUBJECT_TEACHER)
    result = rbac.can_write_score(db, teacher, subject_id, class_id, assignments=assignments)
    assert result is True
    db.execute.assert_not_called()  # không query DB vì assignments đã truyền sẵn


def test_can_write_score_admin_bypasses_even_without_assignments():
    admin = _user(enums.UserRole.ADMIN)
    db = MagicMock()
    assert rbac.can_write_score(db, admin, uuid4(), uuid4(), assignments=[]) is True
    db.execute.assert_not_called()


def test_load_assignments_delegates_to_active_assignments(monkeypatch):
    sentinel = [SimpleNamespace()]
    monkeypatch.setattr(rbac, "_active_assignments", lambda db, uid: sentinel)
    assert rbac.load_assignments(MagicMock(), uuid4()) is sentinel

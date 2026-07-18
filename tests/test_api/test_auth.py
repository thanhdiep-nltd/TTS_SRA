"""Offline test cho Auth + RBAC: security utils, role guard, bảo vệ endpoint.

Không chạm DB (các route trả 401 trước khi truy vấn).
"""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.api.deps import require_roles
from src.core import security
from src.main import app
from src.models import enums
from src.models.tables import User

client = TestClient(app)


def test_password_hash_and_verify():
    hashed = security.hash_password("MatKhau123")
    assert hashed != "MatKhau123"
    assert security.verify_password("MatKhau123", hashed)
    assert not security.verify_password("sai", hashed)


def test_access_token_roundtrip():
    token = security.create_access_token("user-123")
    payload = security.decode_token(token)
    assert payload["sub"] == "user-123"
    assert payload["type"] == security.ACCESS


def test_decode_rejects_tampered_token():
    token = security.create_access_token("user-123")
    with pytest.raises(Exception):
        security.decode_token(token + "tampered")


def test_require_roles_allows_and_blocks():
    guard = require_roles(enums.UserRole.ADMIN)
    admin = User(role=enums.UserRole.ADMIN)
    teacher = User(role=enums.UserRole.SUBJECT_TEACHER)
    assert guard(admin) is admin
    with pytest.raises(HTTPException) as exc:
        guard(teacher)
    assert exc.value.status_code == 403


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/scores",
        "/api/v1/grades",
        "/api/v1/users",
        "/api/v1/students",
        "/api/v1/analytics/overview",
        "/api/v1/exam-papers",
        "/api/v1/analytics/exam-validity",
        "/api/v1/analytics/exam-validity/overview",
        "/api/v1/analytics/content-adjusted-ranking",
    ],
)
def test_protected_endpoints_require_auth(path):
    assert client.get(path).status_code == 401


def test_login_validates_body():
    # thiếu password -> 422 (validation, không chạm DB)
    assert client.post("/api/v1/auth/login", json={"email": "a@b.com"}).status_code == 422


def test_gradebook_endpoints_require_auth():
    import uuid

    u = str(uuid.uuid4())
    assert client.get(f"/api/v1/scores/gradebook?class_id={u}&subject_id={u}&semester_id={u}").status_code == 401
    assert client.get(f"/api/v1/scores/class-summary?class_id={u}&semester_id={u}").status_code == 401
    assert client.get(f"/api/v1/scores/mappings?subject_id={u}&semester_id={u}").status_code == 401

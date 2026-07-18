"""Offline test cho nghiệp vụ phân công giảng dạy.

Không chạm DB: dùng mock Session cho service và kiểm tra đăng ký route.
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from src.main import app
from src.models import enums
from src.models.tables import TeacherAssignment
from src.schemas.user import AssignmentCreate
from src.services import assignments as svc

USER_ID = uuid4()
YEAR_ID = uuid4()
CLASS_A = uuid4()
CLASS_B = uuid4()


def _homeroom_payload(class_id):
    return AssignmentCreate(
        user_id=USER_ID,
        academic_year_id=YEAR_ID,
        role_context=enums.RoleContext.HOMEROOM_SECONDARY,
        class_id=class_id,
    )


def _mock_db_with_existing(existing):
    """Session giả: db.execute(...).scalars().first() -> existing; db.get() -> GV hợp lệ."""
    db = MagicMock()
    db.execute.return_value.scalars.return_value.first.return_value = existing
    db.get.return_value = MagicMock(role=enums.UserRole.HOMEROOM_TEACHER_SECONDARY, subject_id=None)
    return db


# Các kiểm tra tenant/niên khóa/trùng lặp/GV-khác-đang-chủ-nhiệm được test riêng, đầy đủ
# (với fake db chính xác hơn) trong tests/test_assignments_service.py. Ở đây patch chúng đi
# để tập trung đúng vào quy tắc "1 GV chỉ chủ nhiệm 1 lớp/năm" mà file này nhắm tới.
_BYPASS = (
    patch.object(svc, "_validate_year"),
    patch.object(svc, "_validate_refs"),
    patch.object(svc, "_duplicate_exists", return_value=False),
    patch.object(svc, "_class_homeroom_holder", return_value=None),
)


def test_homeroom_blocks_second_class():
    """GV đã chủ nhiệm CLASS_A -> nhận chủ nhiệm CLASS_B phải bị chặn 409."""
    existing = TeacherAssignment(
        user_id=USER_ID,
        academic_year_id=YEAR_ID,
        role_context=enums.RoleContext.HOMEROOM_SECONDARY,
        class_id=CLASS_A,
    )
    db = _mock_db_with_existing(existing)
    with _BYPASS[0], _BYPASS[1], _BYPASS[2], _BYPASS[3]:
        with pytest.raises(HTTPException) as exc:
            svc.create_assignment(db, _homeroom_payload(CLASS_B))
    assert exc.value.status_code == 409
    db.commit.assert_not_called()


def test_homeroom_same_class_not_blocked_by_rule():
    """Cùng lớp đang chủ nhiệm: không bị quy tắc 1-lớp chặn (UNIQUE DB lo phần trùng)."""
    existing = TeacherAssignment(
        user_id=USER_ID,
        academic_year_id=YEAR_ID,
        role_context=enums.RoleContext.HOMEROOM_SECONDARY,
        class_id=CLASS_A,
    )
    db = _mock_db_with_existing(existing)  # GV không có môn phụ trách -> _auto_subject_teacher no-op
    with _BYPASS[0], _BYPASS[1], _BYPASS[2], _BYPASS[3]:
        svc.create_assignment(db, _homeroom_payload(CLASS_A))
    db.commit.assert_called_once()


def test_delete_assignment_route_registered():
    # Dùng OpenAPI schema (ổn định qua các phiên bản FastAPI/Starlette) thay vì duyệt app.routes.
    methods = app.openapi()["paths"].get("/api/v1/users/assignments/{assignment_id}", {})
    assert "delete" in methods

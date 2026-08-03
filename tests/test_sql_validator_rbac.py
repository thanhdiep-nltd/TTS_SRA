"""Tests RBAC injection trong validate_and_secure_sql (KHÔNG cần DB thật).

Dùng monkeypatch để mock get_user_assignment_constraints trả về dict cố định,
nhằm kiểm tra cách inject clause RBAC theo cấu trúc cột thực của từng bảng:

- fact_gradebooks (KHÔNG có cột grade_id) -> resolve qua s360.dim_homeroom_class
- fact_gradebooks_moet (có cột grade_id) -> inject trực tiếp grade_id IN (...)
- fact_so_assignment_grade (không có class/grade/subject) -> resolve qua
  s360.dim_so_assignment + s360.dim_homeroom_class_student
"""

import pytest

from src.core.security import sql_validator
from src.core.security.sql_validator import PermissionDeniedError, validate_and_secure_sql


def _grade_head_grade6():
    return {
        "is_full_access": False,
        "homeroom_class_ids": [],
        "grade_ids": [6],
        "subject_class_pairs": [],
    }


def _kiem_nhiem_merged():
    """Giáo viên kiêm nhiệm: Toàn quyền lớp 6A2 (class_id=2) + Quyền môn Toán 6A1 (class 1, subject 106)."""
    return {
        "is_full_access": False,
        "homeroom_class_ids": [2],
        "grade_ids": [],
        "subject_class_pairs": [(1, 106)],
    }


def test_fact_gradebooks_grade_filter_via_homeroom_class(monkeypatch):
    """fact_gradebooks không có cột grade_id -> lọc qua dim_homeroom_class, không inject grade_id."""
    monkeypatch.setattr(
        sql_validator,
        "get_user_assignment_constraints",
        lambda uid, role: _grade_head_grade6(),
    )
    secured = validate_and_secure_sql(
        "SELECT * FROM s360.fact_gradebooks",
        1,
        user_id=99,
        user_role="GRADE_HEAD_PRIMARY",
    )
    assert (
        "homeroom_class_id IN (SELECT id FROM s360.dim_homeroom_class WHERE grade_id IN (6))"
        in secured
    )
    # BUG cũ: inject grade_id vào bảng không có cột này -> phải tuyệt đối không xuất hiện
    assert "fact_gradebooks.grade_id" not in secured


def test_fact_gradebooks_moet_direct_grade_filter(monkeypatch):
    """fact_gradebooks_moet có cột grade_id -> inject trực tiếp grade_id IN (...)."""
    monkeypatch.setattr(
        sql_validator,
        "get_user_assignment_constraints",
        lambda uid, role: _grade_head_grade6(),
    )
    secured = validate_and_secure_sql(
        "SELECT * FROM s360.fact_gradebooks_moet",
        1,
        user_id=99,
        user_role="GRADE_HEAD_PRIMARY",
    )
    assert "fact_gradebooks_moet.grade_id IN (6)" in secured


def test_fact_so_assignment_grade_filters(monkeypatch):
    """fact_so_assignment_grade không có class/grade/subject -> resolve qua các dim."""
    monkeypatch.setattr(
        sql_validator,
        "get_user_assignment_constraints",
        lambda uid, role: {
            "is_full_access": False,
            "homeroom_class_ids": [101],
            "grade_ids": [6],
            "subject_class_pairs": [(101, 2)],
        },
    )
    secured = validate_and_secure_sql(
        "SELECT * FROM s360.fact_so_assignment_grade",
        1,
        user_id=99,
        user_role="SUBJECT_TEACHER",
    )
    assert (
        "fact_so_assignment_grade.student_code IN (SELECT student_code FROM s360.dim_homeroom_class_student "
        "WHERE homeroom_class_id IN (101))" in secured
    )
    assert (
        "fact_so_assignment_grade.assignment_id IN (SELECT assignment_id FROM s360.dim_so_assignment "
        "WHERE grade_id IN (6))" in secured
    )
    assert "dim_so_assignment" in secured
    assert "dim_homeroom_class_student" in secured
    # Không inject nhầm cột không tồn tại trên fact_so_assignment_grade
    assert "fact_so_assignment_grade.grade_id" not in secured
    assert "fact_so_assignment_grade.homeroom_class_id" not in secured
    assert "fact_so_assignment_grade.subject_id" not in secured


def test_fact_gradebooks_moet_merged_homeroom_subject_or(monkeypatch):
    """QUYỀN HỢP NHẤT (giáo viên kiêm nhiệm) phải được ghép bằng OR.

    Regression cho bug: teacher_kiem_nhiem (homeroom 6A2 + môn Toán 6A1) bị từ chối
    khi tra "môn Văn của 6A2" vì class_id mồ côi 101/102. Với quyền hợp nhất, clause RBAC
    phải là: (homeroom_class_id IN (2)) OR (homeroom_class_id = 1 AND subject_id = 106)
    -> toàn quyền 6A2 bao phủ mọi môn kể cả Văn; không được AND chặn nhau.
    """
    monkeypatch.setattr(
        sql_validator,
        "get_user_assignment_constraints",
        lambda uid, role: _kiem_nhiem_merged(),
    )
    secured = validate_and_secure_sql(
        "SELECT * FROM s360.fact_gradebooks_moet",
        1,
        user_id=99,
        user_role="HOMEROOM_TEACHER_SECONDARY",
    )
    # Toàn quyền lớp 6A2 (homeroom_class_id=2) -> truy cập mọi môn của 6A2 kể cả Văn
    assert "fact_gradebooks_moet.homeroom_class_id IN (2)" in secured
    # Quyền môn Toán lớp 6A1 (class_id=1, subject_id=106)
    assert (
        "(fact_gradebooks_moet.homeroom_class_id = 1 AND fact_gradebooks_moet.subject_id = 106)"
        in secured
    )
    # Hai quyền phải hợp nhất bằng OR (bug cũ: 6A2+Văn bị từ chối vì thiếu nhánh này)
    assert " OR " in secured


def test_no_assignments_raises_permission_denied(monkeypatch):
    """User có role nhưng không có phân công khớp với bảng -> PermissionDeniedError."""
    monkeypatch.setattr(
        sql_validator,
        "get_user_assignment_constraints",
        lambda uid, role: {
            "is_full_access": False,
            "homeroom_class_ids": [],
            "grade_ids": [],
            "subject_class_pairs": [],
        },
    )
    with pytest.raises(PermissionDeniedError):
        validate_and_secure_sql(
            "SELECT * FROM s360.fact_gradebooks",
            1,
            user_id=99,
            user_role="SUBJECT_TEACHER",
        )


def test_full_access_no_rbac(monkeypatch):
    """ADMIN/PRINCIPAL -> is_full_access=True -> KHÔNG chèn RBAC, vẫn giữ tenant filter."""
    monkeypatch.setattr(
        sql_validator,
        "get_user_assignment_constraints",
        lambda uid, role: {"is_full_access": True},
    )
    secured = validate_and_secure_sql(
        "SELECT * FROM s360.fact_gradebooks",
        1,
        user_id=1,
        user_role="ADMIN",
    )
    assert "grade_id IN (6)" not in secured
    assert "homeroom_class_id IN (SELECT id FROM s360.dim_homeroom_class" not in secured
    # Tenant isolation vẫn phải hoạt động
    assert "fact_gradebooks.so_school_id = 1" in secured

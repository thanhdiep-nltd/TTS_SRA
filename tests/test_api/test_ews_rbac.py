"""Tests RBAC cho Dashboard EWS (src/api/v1/ews.py).

Kiểm tra helper `_ews_rbac_filter` — logic giới hạn dữ liệu EWS theo phân quyền user
(cùng nguồn `get_user_assignment_constraints` với chatbot). Chạy offline, không chạm DB.
"""

from types import SimpleNamespace

from src.api.v1 import ews as ews_module


def _user(role: str, so_school_id: int = 1, user_id: int = 99) -> SimpleNamespace:
    return SimpleNamespace(id=user_id, role=role, so_school_id=so_school_id)


def _patch_constraints(monkeypatch, constraints: dict):
    monkeypatch.setattr(ews_module, "get_user_assignment_constraints", lambda uid, role: constraints)


def test_full_access_only_school_filter(monkeypatch):
    """ADMIN/PRINCIPAL (full access) -> chỉ giới hạn theo so_school_id, không theo khối/lớp."""
    _patch_constraints(monkeypatch, {"is_full_access": True})
    where, params = ews_module._ews_rbac_filter(None, _user("ADMIN", so_school_id=7))
    assert "hcs.so_school_id = :school_id" in where
    assert params == {"school_id": 7}
    assert "grade_id" not in where
    assert "homeroom_class_id" not in where


def test_grade_head_filters_by_grade(monkeypatch):
    """Trưởng khối 6 -> lọc hcs.grade_id IN (6) + school_id."""
    _patch_constraints(
        monkeypatch,
        {
            "is_full_access": False,
            "homeroom_class_ids": [],
            "grade_ids": [6],
            "subject_class_pairs": [],
        },
    )
    where, params = ews_module._ews_rbac_filter(None, _user("GRADE_HEAD_PRIMARY"))
    assert "hcs.so_school_id = :school_id" in where
    assert "hcs.grade_id IN (:g0)" in where
    assert params["g0"] == 6
    assert params["school_id"] == 1


def test_homeroom_filters_by_class(monkeypatch):
    """GV chủ nhiệm lớp 6A2 (class_id=2) -> lọc hcs.homeroom_class_id IN (2)."""
    _patch_constraints(
        monkeypatch,
        {
            "is_full_access": False,
            "homeroom_class_ids": [2],
            "grade_ids": [],
            "subject_class_pairs": [],
        },
    )
    where, params = ews_module._ews_rbac_filter(None, _user("HOMEROOM_PRIMARY"))
    assert "hcs.homeroom_class_id IN (:c0)" in where
    assert params["c0"] == 2


def test_subject_teacher_filters_by_class_and_subject(monkeypatch):
    """GV bộ môn Toán 6A1 (class 1, subject 106) -> lọc (homeroom_class_id=1 AND subject_id=106)."""
    _patch_constraints(
        monkeypatch,
        {
            "is_full_access": False,
            "homeroom_class_ids": [],
            "grade_ids": [],
            "subject_class_pairs": [(1, 106)],
        },
    )
    where, params = ews_module._ews_rbac_filter(None, _user("SUBJECT_TEACHER"))
    assert "hcs.homeroom_class_id = :pc0 AND rp.subject_id = :ps0" in where
    assert params["pc0"] == 1
    assert params["ps0"] == 106


def test_no_assignment_returns_no_rows(monkeypatch):
    """User có role nhưng không có phân công -> không thấy dữ liệu (1 = 0)."""
    _patch_constraints(
        monkeypatch,
        {
            "is_full_access": False,
            "homeroom_class_ids": [],
            "grade_ids": [],
            "subject_class_pairs": [],
        },
    )
    where, params = ews_module._ews_rbac_filter(None, _user("SUBJECT_TEACHER"))
    assert "1 = 0" in where
    assert params == {"school_id": 1}


def test_merged_grade_and_class_scope(monkeypatch):
    """Kiêm nhiệm: trưởng khối 6 + chủ nhiệm lớp 2 -> OR giữa grade và class."""
    _patch_constraints(
        monkeypatch,
        {
            "is_full_access": False,
            "homeroom_class_ids": [2],
            "grade_ids": [6],
            "subject_class_pairs": [],
        },
    )
    where, params = ews_module._ews_rbac_filter(None, _user("GRADE_HEAD_PRIMARY"))
    assert "hcs.grade_id IN (:g0)" in where
    assert "hcs.homeroom_class_id IN (:c0)" in where
    assert " OR " in where
    assert params["g0"] == 6
    assert params["c0"] == 2

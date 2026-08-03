"""Tests RBAC template tools (Phản biện 1): get_student_grades / get_class_grades / get_student_info.

Chạy offline: mock SessionLocal + get_user_assignment_constraints, set ContextVars
(current_user_id / current_user_role / current_user_school_id), không chạm DB thật.
"""

import json
from unittest.mock import MagicMock

import pytest

from src.agents.context import current_user_id, current_user_role, current_user_school_id
from src.agents.data_service_agent import tools as ds_tools

RBAC_GRADE6 = {
    "is_full_access": False,
    "homeroom_class_ids": [],
    "grade_ids": [6],
    "subject_class_pairs": [],
    "scope_summary": "grade_ids={6}",
}

# Giáo viên kiêm nhiệm: Toàn quyền lớp 6A2 (class_id=2) + Quyền môn Toán 6A1 (class 1, subject 106)
RBAC_KIEM_NHIEM = {
    "is_full_access": False,
    "homeroom_class_ids": [2],
    "grade_ids": [],
    "subject_class_pairs": [(1, 106)],
    "scope_summary": "lớp CLASS_1_6A2; môn Toán học Khối 6",
}


@pytest.fixture
def rbac_grade6(monkeypatch):
    """Set ContextVars + mock get_user_assignment_constraints trả grade_ids=[6]."""
    token_id = current_user_id.set(99)
    token_role = current_user_role.set("GRADE_HEAD_PRIMARY")
    token_school = current_user_school_id.set(1)
    monkeypatch.setattr(ds_tools, "get_user_assignment_constraints", lambda uid, role: RBAC_GRADE6)
    yield
    current_user_id.reset(token_id)
    current_user_role.reset(token_role)
    current_user_school_id.reset(token_school)


@pytest.fixture
def fake_session(monkeypatch):
    """Patch SessionLocal trong suốt vòng đời test; trả hàm dựng session giả.

    - execute(...).fetchone() -> (id, grade_id) dùng cho truy vấn lớp/học sinh
    - execute(...).fetchall() -> rows dùng cho truy vấn điểm thật
    """
    mock_session_local = MagicMock()
    monkeypatch.setattr(ds_tools, "SessionLocal", mock_session_local)

    def _make(class_grade_id, rows=None):
        session = MagicMock()
        session.execute.return_value.fetchone.return_value = (1001, class_grade_id)
        session.execute.return_value.fetchall.return_value = rows or []
        mock_session_local.return_value.__enter__.return_value = session
        return session

    return _make


def test_get_class_grades_out_of_scope_denied(rbac_grade6, fake_session):
    """Trưởng khối 6 hỏi lớp 7A1 -> ACCESS_DENIED (không trả dữ liệu lớp 7)."""
    fake_session(class_grade_id=7)  # 7A1 thuộc khối 7 -> ngoài phạm vi grade 6
    result = ds_tools.get_class_grades.invoke({"class_name": "7A1"})
    assert "ACCESS_DENIED" in result
    assert "ngoài phạm vi" in result


def test_get_class_grades_in_scope_allowed(rbac_grade6, fake_session):
    """Trưởng khối 6 hỏi lớp 6A1 -> hợp lệ, trả dữ liệu điểm thật (không ACCESS_DENIED)."""
    row = ("HS1001", "Nguyễn Văn A", "Toán học", "6A1", 2, "Cuối kỳ", 8.5, "A", "DAT", "SCORED")
    fake_session(class_grade_id=6, rows=[row])
    result = ds_tools.get_class_grades.invoke({"class_name": "6A1", "year": 2025, "semester": 2, "subject": "Toán học"})
    assert "ACCESS_DENIED" not in result
    assert "Nguyễn Văn A" in result
    assert "8.5" in result


def test_get_student_grades_out_of_scope_denied(rbac_grade6, fake_session):
    """Học sinh thuộc khối 7 -> từ chối trước khi truy vấn điểm (không rò rỉ điểm)."""
    fake_session(class_grade_id=7)  # (grade_id=7, homeroom_class_id=1001) ngoài phạm vi
    result = ds_tools.get_student_grades.invoke({"student_code": "HS1002"})
    assert "ACCESS_DENIED" in result


def test_get_student_info_out_of_scope_denied(rbac_grade6, fake_session):
    """Học sinh khối 7 bị lọc khỏi kết quả tìm kiếm -> ACCESS_DENIED (không lộ thông tin)."""
    rows = [
        ("HS1003", "Trần Thị B", "7A1", "Khối 7", 2025, 7, 2001),
    ]
    fake_session(class_grade_id=7, rows=rows)
    result = ds_tools.get_student_info.invoke({"name_or_id": "Trần Thị B"})
    assert "ACCESS_DENIED" in result


def test_execute_read_only_query_permission_denied(rbac_grade6, monkeypatch):
    """PermissionDeniedError từ validator -> trả ACCESS_DENIED thay vì 'Lỗi thực thi SQL'."""
    from src.core.security.sql_validator import PermissionDeniedError

    def _raise(*args, **kwargs):
        raise PermissionDeniedError("Ngoài phạm vi phân công.")

    monkeypatch.setattr(ds_tools, "validate_and_secure_sql", _raise)
    result = ds_tools.execute_read_only_query.invoke({"sql_query": "SELECT * FROM s360.fact_gradebooks"})
    assert "ACCESS_DENIED" in result
    assert "Lỗi thực thi truy vấn SQL" not in result


def test_is_scope_allowed_kiem_nhiem_merged_rights():
    """Giáo viên kiêm nhiệm (homeroom 6A2 + môn Toán 6A1) — quyền hợp nhất bằng OR.

    Regression bug: user bị từ chối khi tra "môn Văn của 6A2" dù có toàn quyền lớp 6A2.
    Với homeroom_class_ids=[2], 6A2 + mọi môn (kể cả Văn, subject_id=2) phải được phép;
    6A1 + Văn phải bị từ chối (chỉ được môn Toán 6A1).
    """
    meta = RBAC_KIEM_NHIEM
    # Toàn quyền lớp 6A2 -> mọi môn của 6A2 hợp lệ, kể cả Văn (subject_id=2) — bug cũ
    assert ds_tools._is_scope_allowed(meta, homeroom_class_id=2, subject_id=2) is True
    assert ds_tools._is_scope_allowed(meta, homeroom_class_id=2, subject_id=106) is True
    assert ds_tools._is_scope_allowed(meta, homeroom_class_id=2) is True
    # Quyền môn Toán lớp 6A1 (class 1 + subject 106)
    assert ds_tools._is_scope_allowed(meta, homeroom_class_id=1, subject_id=106) is True
    # 6A1 + Văn -> ngoài phạm vi (chỉ có Toán 6A1)
    assert ds_tools._is_scope_allowed(meta, homeroom_class_id=1, subject_id=2) is False


@pytest.fixture
def rbac_kiem_nhiem(monkeypatch):
    """Set ContextVars tài khoản kiêm nhiệm (id 36) + mock get_user_assignment_constraints."""
    token_id = current_user_id.set(36)
    token_role = current_user_role.set("HOMEROOM_TEACHER_SECONDARY")
    token_school = current_user_school_id.set(1)
    monkeypatch.setattr(ds_tools, "get_user_assignment_constraints", lambda uid, role: RBAC_KIEM_NHIEM)
    yield
    current_user_id.reset(token_id)
    current_user_role.reset(token_role)
    current_user_school_id.reset(token_school)


def _captured_sql_texts(session) -> str:
    """Gom toàn bộ SQL (TextClause) được truyền vào session.execute trong các lượt gọi."""
    parts = []
    for call in session.execute.call_args_list:
        arg = call.args[0]
        if hasattr(arg, "text"):
            parts.append(arg.text)
    return "\n".join(parts)


def test_get_class_grades_kiem_nhiem_moet_union_queries_both_tables(rbac_kiem_nhiem, monkeypatch):
    """Regression bug runtime: tài khoản kiêm nhiệm tra "môn Văn của 6A2" bị từ chối vì
    get_class_grades chỉ đọc fact_gradebooks (môn quốc tế) nên Văn (MOET) trả "không có dữ liệu"
    và agent hiểu nhầm thành từ chối phân quyền.

    Fix: tool truy vấn CẢ fact_gradebooks + fact_gradebooks_moet (UNION ALL) cho truy vấn trong
    phạm vi quyền — kiểm tra câu SQL chứa cả 2 bảng + UNION ALL, không ACCESS_DENIED.
    """
    session = MagicMock()
    # class lookup -> (homeroom_class_id=2, grade_id=6); subject lookup -> subject_id=2 (Ngữ văn)
    session.execute.return_value.fetchone.side_effect = [(2, 6), (2,)]
    row = ("HS1001", "Nguyễn Văn A", "Ngữ văn", "6A2", 2, "Kiểm tra Giữa Học kỳ 2", 6.0, None, None, "SCORED")
    session.execute.return_value.fetchall.return_value = [row]

    mock_session_local = MagicMock()
    mock_session_local.return_value.__enter__.return_value = session
    monkeypatch.setattr(ds_tools, "SessionLocal", mock_session_local)

    result = ds_tools.get_class_grades.invoke({"class_name": "6A2", "semester": 2, "subject": "Ngữ văn"})
    assert "ACCESS_DENIED" not in result
    assert "Ngữ văn" in result
    assert "6.0" in result

    joined = _captured_sql_texts(session)
    assert "fact_gradebooks" in joined
    assert "fact_gradebooks_moet" in joined
    assert "UNION ALL" in joined


def test_get_student_grades_kiem_nhiem_moet_union_queries_both_tables(rbac_kiem_nhiem, monkeypatch):
    """Tương tự cho get_student_grades: phải truy vấn cả 2 bảng nguồn điểm (UNION ALL)."""
    session = MagicMock()
    # student lookup -> (grade_id=6, homeroom_class_id=2)
    session.execute.return_value.fetchone.return_value = (6, 2)
    row = (
        "HS1001",
        "Nguyễn Văn A",
        "Ngữ văn",
        "6A2",
        "Năm học 2025-2026",
        2,
        "Kiểm tra Giữa Học kỳ 2",
        6.0,
        None,
        None,
        "SCORED",
    )
    session.execute.return_value.fetchall.return_value = [row]

    mock_session_local = MagicMock()
    mock_session_local.return_value.__enter__.return_value = session
    monkeypatch.setattr(ds_tools, "SessionLocal", mock_session_local)

    result = ds_tools.get_student_grades.invoke({"student_code": "HS1001", "semester": 2, "subject": "Ngữ văn"})
    assert "ACCESS_DENIED" not in result
    assert "Ngữ văn" in result
    assert "6.0" in result

    joined = _captured_sql_texts(session)
    assert "fact_gradebooks" in joined
    assert "fact_gradebooks_moet" in joined
    assert "UNION ALL" in joined


def test_execute_read_only_query_empty_result_neutral_note(rbac_kiem_nhiem, monkeypatch):
    """Regression bug note sai: 0 dòng bị tool dẫn dắt LLM kết luận "bị chặn phân quyền"
    (note cũ: 'Nếu dữ liệu được yêu cầu nằm ngoài phạm vi này, đây là do quyền truy cập,
    không phải do dữ liệu không tồn tại'). Đây chính là lý do agent kiêm nhiệm trả lời sai
    "điểm Vinschool/học bạ không truy cập được, chỉ được môn Toán khối 6" dù thực tế 6A2
    được toàn quyền mọi môn và 0 dòng chỉ vì môn MOET (Ngữ văn) không có ở sổ điểm Vinschool.

    Fix: note trung lập — 0 dòng = "không tìm thấy dữ liệu", chỉ ACCESS_DENIED mới là hết quyền.
    """
    monkeypatch.setattr(
        ds_tools,
        "validate_and_secure_sql",
        lambda q, sid, user_id=None, user_role=None, **kwargs: q,
    )
    mock_engine = MagicMock()
    mock_conn = mock_engine.connect.return_value.__enter__.return_value
    mock_conn.execute.return_value.fetchall.return_value = []
    mock_conn.execute.return_value.keys.return_value = []
    monkeypatch.setattr(ds_tools, "engine", mock_engine)

    result = ds_tools.execute_read_only_query.invoke({"sql_query": "SELECT * FROM s360.fact_gradebooks"})
    payload = json.loads(result)
    assert payload["data"] == []
    note = payload["note"]
    assert "chưa có dữ liệu" in note
    assert "không tìm thấy dữ liệu" in note
    # KHÔNG còn cụm từ cũ dẫn dắt LLM suy diễn 0 dòng = do phân quyền
    assert "do quyền truy cập" not in note
    assert "do dữ liệu không tồn tại" not in note

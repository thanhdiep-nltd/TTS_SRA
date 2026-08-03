from unittest.mock import MagicMock, patch
from uuid import uuid4

from src.agents.context import current_user_id, current_user_role, current_user_school_id
from src.agents.data_service_agent.tools import execute_read_only_query
from src.agents.knowledge_agent.tools import search_textbook
from src.core.security.sql_validator import validate_and_secure_sql


def test_sql_limit_guardrail():
    """Kiểm tra xem Limit Guardrail có tự động ép LIMIT 100 vào SQL hay không."""
    school_id = "00000000-0000-0000-0000-000000000001"

    # 1. Trường hợp không có LIMIT -> Tự động thêm LIMIT 100
    sql1 = "SELECT * FROM students"
    res1 = validate_and_secure_sql(sql1, school_id)
    assert "LIMIT 100" in res1

    # 2. Trường hợp LIMIT lớn hơn 100 -> Ghi đè thành LIMIT 100
    sql2 = "SELECT * FROM students LIMIT 1000"
    res2 = validate_and_secure_sql(sql2, school_id)
    assert "LIMIT 100" in res2
    assert "LIMIT 1000" not in res2

    # 3. Trường hợp LIMIT nhỏ hơn hoặc bằng 100 -> Giữ nguyên
    sql3 = "SELECT * FROM students LIMIT 50"
    res3 = validate_and_secure_sql(sql3, school_id)
    assert "LIMIT 50" in res3
    assert "LIMIT 100" not in res3


def test_sql_limit_guardrail_max_rows_override():
    """max_rows cho phép caller (tool bảng điểm lớp/khối) nới trần dòng trả về."""
    school_id = "00000000-0000-0000-0000-000000000001"

    # 1. max_rows=2000: không có LIMIT -> ép LIMIT 2000
    res1 = validate_and_secure_sql("SELECT * FROM students", school_id, max_rows=2000)
    assert "LIMIT 2000" in res1

    # 2. max_rows=2000: LIMIT 1000 (< trần) -> giữ nguyên
    res2 = validate_and_secure_sql("SELECT * FROM students LIMIT 1000", school_id, max_rows=2000)
    assert "LIMIT 1000" in res2
    assert "LIMIT 2000" not in res2

    # 3. max_rows=2000: LIMIT 5000 (> trần) -> hạ về 2000
    res3 = validate_and_secure_sql("SELECT * FROM students LIMIT 5000", school_id, max_rows=2000)
    assert "LIMIT 2000" in res3
    assert "LIMIT 5000" not in res3


def test_sql_agent_role_blocking():
    """RBAC trong kiến trúc hiện tại: `execute_read_only_query` chặn user ngoài phạm vi.

    - User có phân quyền giới hạn + truy vấn ngoài phạm vi -> validator raise
      `PermissionDeniedError` -> tool trả ACCESS_DENIED (KHÔNG retry/đi tiếp).
    - User PRINCIPAL (full access) -> đi tiếp tới DB execution (engine.connect được gọi).
    """
    from src.agents.data_service_agent import tools as ds_tools
    from src.core.security.sql_validator import PermissionDeniedError

    school_id = uuid4()
    token_school = current_user_school_id.set(school_id)
    token_id = current_user_id.set(100)
    token_role = current_user_role.set("SUBJECT_TEACHER")
    try:
        # 1. Truy vấn ngoài phạm vi -> ACCESS_DENIED
        def _raise(*args, **kwargs):
            raise PermissionDeniedError("Ngoài phạm vi phân công.")

        with patch.object(ds_tools, "validate_and_secure_sql", _raise):
            res = execute_read_only_query.invoke({"sql_query": "SELECT * FROM students"})
        assert "ACCESS_DENIED" in res
        assert "Lỗi thực thi truy vấn SQL" not in res

        # 2. PRINCIPAL (full access) -> đi tiếp tới DB execution
        current_user_role.set("PRINCIPAL")
        fake_conn = MagicMock()
        fake_result = MagicMock()
        fake_result.keys.return_value = ["student_code"]
        fake_result.fetchall.return_value = [{"student_code": "HS1"}]
        fake_conn.execute.return_value = fake_result
        with patch.object(ds_tools, "engine") as mock_engine:
            mock_engine.connect.return_value.__enter__.return_value = fake_conn
            out = execute_read_only_query.invoke({"sql_query": "SELECT * FROM students"})
            mock_engine.connect.assert_called()
        assert '"student_code"' in out
    finally:
        current_user_school_id.reset(token_school)
        current_user_id.reset(token_id)
        current_user_role.reset(token_role)


def test_rag_score_threshold_guardrail():
    """Kiểm tra xem RAG Threshold có lọc chính xác các kết quả tương đồng thấp (< 0.45) hay không."""

    # Giả lập Qdrant trả về các kết quả có score thấp và cao
    mock_hits = [
        {"mon": "toan", "lop": "6", "heading": "Chương 1", "text": "Kiến thức chuẩn", "score": 0.85},
        {"mon": "toan", "lop": "6", "heading": "Chương 2", "text": "Kiến thức nhiễu", "score": 0.30},
    ]

    with patch("src.services.retrieval.search_textbook", return_value=mock_hits):
        res = search_textbook.invoke({"query": "Toán lớp 6"})

        # Chỉ giữ lại kết quả có score >= 0.45 (Nguồn 1)
        assert "[Nguồn 1]" in res
        assert "Kiến thức chuẩn" in res
        # Loại bỏ kết quả score < 0.45 (Nguồn 2)
        assert "[Nguồn 2]" not in res
        assert "Kiến thức nhiễu" not in res

    # Trường hợp tất cả kết quả đều có score < 0.45
    mock_low_hits = [
        {"mon": "toan", "lop": "6", "heading": "Chương 2", "text": "Nhiễu hoàn toàn", "score": 0.30},
    ]
    with patch("src.services.retrieval.search_textbook", return_value=mock_low_hits):
        res_empty = search_textbook.invoke({"query": "Toán lớp 6"})
        assert "Không tìm thấy nội dung phù hợp" in res_empty

from unittest.mock import patch
from uuid import uuid4

from src.agents.context import current_user_role, current_user_school_id
from src.agents.knowledge_agent.tools import search_textbook
from src.agents.sql_agent.tools import execute_read_only_query
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


def test_sql_agent_role_blocking():
    """Kiểm tra xem SQL Analyst Agent có chặn tài khoản Giáo viên (non-PRINCIPAL) hay không."""
    school_id = uuid4()

    # Giả lập vai trò SUBJECT_TEACHER
    current_user_school_id.set(school_id)
    current_user_role.set("SUBJECT_TEACHER")

    res = execute_read_only_query.invoke({"sql_query": "SELECT * FROM students"})
    assert "Lỗi bảo mật" in res
    assert "chỉ dành riêng cho Ban Giám Hiệu" in res

    # Giả lập vai trò PRINCIPAL -> Cho phép đi tiếp (sẽ lỗi kết nối DB thật nhưng không chặn quyền ở tool level)
    current_user_role.set("PRINCIPAL")
    with patch("src.agents.sql_agent.tools.engine.connect") as mock_connect:
        # Mock connection to bypass real database execute
        execute_read_only_query.invoke({"sql_query": "SELECT * FROM students"})
        assert mock_connect.called


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

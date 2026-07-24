import json

from langchain_core.tools import tool
from sqlalchemy import text

from src.agents.context import current_user_role, current_user_school_id
from src.core.security.sql_validator import validate_and_secure_sql
from src.db.session import engine


@tool
def execute_read_only_query(sql_query: str) -> str:
    """Thực thi câu lệnh SQL SELECT an toàn để lấy dữ liệu thô dạng JSON phục vụ cho việc phân tích dữ liệu.

    Chỉ dùng công cụ này khi cần lấy các thống kê phức tạp hoặc tương quan điểm số động
    mà các công cụ chuyên biệt của Data/Stat Agent không hỗ trợ.

    Args:
        sql_query: Câu truy vấn SQL SELECT hợp lệ (ví dụ: 'SELECT * FROM students').
    """
    school_id = current_user_school_id.get()
    user_role = current_user_role.get()

    if not school_id:
        return "Lỗi: Không xác định được trường của người dùng. Vui lòng đăng nhập."

    # Chặn nếu vai trò người dùng không phải là BGH hoặc ADMIN
    if user_role not in ("PRINCIPAL", "ADMIN"):
        return "Lỗi bảo mật: Công cụ phân tích SQL thô chỉ dành riêng cho Ban Giám Hiệu."

    try:
        # 1. Bảo mật và lọc theo school_id sử dụng SQLGlot
        secured_query = validate_and_secure_sql(sql_query, str(school_id))

        # 2. Thực thi câu lệnh SQL thô trên Neon.tech
        with engine.connect() as conn:
            # Thiết lập Statement Timeout là 5 giây (5000ms) để tránh treo DB
            conn.execute(text("SET statement_timeout = 5000;"))
            result = conn.execute(text(secured_query))
            columns = result.keys()
            rows = [dict(zip(columns, row)) for row in result.fetchall()]

            # Trả về kết quả JSON mã hóa an toàn (chuyển đổi datetime, uuid, decimal sang str)
            return json.dumps(rows, default=str, ensure_ascii=False, indent=2)

    except Exception as e:
        return f"Lỗi thực thi truy vấn SQL: {str(e)}"

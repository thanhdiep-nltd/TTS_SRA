import json
import re
from langchain_core.tools import tool
from sqlalchemy import text

from src.agents.context import current_user_role, current_user_school_id
from src.core.security.sql_validator import validate_and_secure_sql
from src.db.session import SessionLocal, engine


@tool
def get_student_info(name_or_id: str) -> str:
    """Tìm kiếm thông tin cá nhân của học sinh trong trường dựa trên Họ tên hoặc Mã học sinh.

    Args:
        name_or_id: Họ tên học sinh (ví dụ: 'Ngô Ngọc Hoa') hoặc Mã học sinh (ví dụ: 'HS25071001').

    Returns:
        Một chuỗi JSON chứa danh sách các học sinh khớp thông tin.
    """
    school_id = current_user_school_id.get() or 1

    query = name_or_id.strip()
    with SessionLocal() as session:
        sql = text("""
            SELECT student_code, student_name, class_name, grade_name, school_year_id
            FROM s360.dim_homeroom_class_student
            WHERE so_school_id = :sid 
              AND (student_code = :q OR student_name ILIKE :q_like)
            LIMIT 20
        """)
        rows = session.execute(sql, {"sid": school_id, "q": query, "q_like": f"%{query}%"}).fetchall()
        if not rows:
            return f"Không tìm thấy học sinh nào khớp với thông tin '{name_or_id}' tại trường của bạn."

        results = [
            {
                "Mã học sinh": r[0],
                "Họ và Tên": r[1],
                "Lớp": r[2],
                "Khối": r[3],
                "Năm học ID": r[4],
            }
            for r in rows
        ]
        return json.dumps(results, ensure_ascii=False, indent=2)


@tool
def get_student_grades(student_code: str, year: int | None = None, semester: int | None = None, subject: str | None = None) -> str:
    """Tra cứu điểm số và kết quả đánh giá của một học sinh theo Mã học sinh.

    Args:
        student_code: Mã học sinh duy nhất (bắt buộc). Ví dụ: 'HS125071002'.
                      CHỈ nhập Mã học sinh. TUYỆT ĐỐI KHÔNG nhập tên học sinh.
                      Nếu chỉ có tên mà không có mã, hãy chọn 'NONE'.
        year: ID năm học (ví dụ: 2025).
        semester: Học kỳ (tùy chọn: 1 hoặc 2).
        subject: Tên môn học (tùy chọn: 'Toán học', 'Ngữ văn', 'Âm nhạc', 'Mỹ thuật').

    Returns:
        Chuỗi JSON chứa danh sách điểm số và kết quả đánh giá chi tiết của học sinh.
    """
    school_id = current_user_school_id.get() or 1
    student_code = student_code.strip()

    with SessionLocal() as session:
        query_str = """
            SELECT g.student_code, st.student_name, s.name as subject_name, c.fullname as class_name,
                   y.fullname as year_name, g.semester_index, COALESCE(e.exam_name, 'Đánh giá định kỳ') as exam_name,
                   g.final_grade, g.final_grade_letter, g.pass_fail_status, s.assessment_type
            FROM s360.fact_gradebooks g
            JOIN s360.dim_subject s ON g.subject_id = s.id
            JOIN s360.dim_homeroom_class c ON g.homeroom_class_id = c.id
            JOIN s360.dim_school_year y ON g.school_year_id = y.id
            LEFT JOIN s360.dim_homeroom_class_student st ON g.student_code = st.student_code AND g.homeroom_class_id = st.homeroom_class_id
            LEFT JOIN s360.dim_exam e ON g.so_exam_id = e.id
            WHERE g.so_school_id = :sid AND g.student_code = :scode
        """
        params = {"sid": school_id, "scode": student_code}

        if year:
            query_str += " AND g.school_year_id = :year"
            params["year"] = int(year)
        if semester:
            query_str += " AND g.semester_index = :sem"
            params["sem"] = int(semester)
        if subject:
            query_str += " AND s.name ILIKE :sub"
            params["sub"] = f"%{subject.strip()}%"

        query_str += " ORDER BY s.name, g.semester_index LIMIT 100"

        rows = session.execute(text(query_str), params).fetchall()
        if not rows:
            return f"Không tìm thấy dữ liệu điểm cho Mã học sinh '{student_code}' với bộ lọc đã cho."

        results = []
        for r in rows:
            pf_val = str(r[9]).upper() if r[9] else None
            pf_str = "ĐẠT" if pf_val == "DAT" else ("CHƯA ĐẠT" if pf_val == "CHUA_DAT" else "N/A")
            is_remark = (r[10] == "REMARK")

            item = {
                "Mã học sinh": r[0],
                "Họ và Tên": r[1] or "",
                "Môn học": r[2],
                "Lớp": r[3],
                "Năm học": r[4],
                "Học kỳ": r[5],
                "Bài kiểm tra": r[6],
                "Hình thức đánh giá": "Đánh giá bằng nhận xét (REMARK)" if is_remark else "Chấm điểm số (SCORED)",
                "Điểm số": float(r[7]) if r[7] is not None else ("N/A (Đánh giá nhận xét)" if is_remark else "N/A"),
                "Kết quả (Đạt/Chưa đạt)": pf_str,
            }
            if r[8]:
                item["Điểm chữ"] = r[8]
            results.append(item)

        return json.dumps(results, ensure_ascii=False, indent=2)


@tool
def get_class_grades(class_name: str, year: int | None = None, semester: int | None = None, subject: str | None = None) -> str:
    """Tra cứu danh sách điểm trung bình/điểm thi/kết quả đánh giá của tất cả học sinh trong một lớp học cụ thể (ví dụ: '7A1', '10A1').

    Args:
        class_name: Tên lớp học cụ thể (ví dụ: '7A1', '10A1'). Không nhập tên Khối (như 'Khối 10').
        year: ID năm học (ví dụ: 2025).
        semester: Học kỳ (1 hoặc 2).
        subject: Tên môn học (tùy chọn: 'Toán học', 'Âm nhạc', 'Mỹ thuật').

    Returns:
        Chuỗi JSON chứa danh sách điểm số và kết quả đánh giá của lớp học.
    """
    school_id = current_user_school_id.get() or 1
    c_name = class_name.strip()

    with SessionLocal() as session:
        query_str = """
            SELECT g.student_code, COALESCE(st.student_name, 'Học sinh') as student_name,
                   s.name as subject_name, c.fullname as class_name, g.semester_index,
                   COALESCE(e.exam_name, 'Đánh giá định kỳ') as exam_name, g.final_grade,
                   g.final_grade_letter, g.pass_fail_status, s.assessment_type
            FROM s360.fact_gradebooks g
            JOIN s360.dim_homeroom_class c ON g.homeroom_class_id = c.id
            JOIN s360.dim_subject s ON g.subject_id = s.id
            LEFT JOIN s360.dim_homeroom_class_student st ON g.student_code = st.student_code AND g.homeroom_class_id = st.homeroom_class_id
            LEFT JOIN s360.dim_exam e ON g.so_exam_id = e.id
            WHERE g.so_school_id = :sid AND (c.code ILIKE :cname OR c.fullname ILIKE :cname_like)
        """
        params = {"sid": school_id, "cname": c_name, "cname_like": f"%{c_name}%"}

        if year:
            query_str += " AND g.school_year_id = :year"
            params["year"] = int(year)
        if semester:
            query_str += " AND g.semester_index = :sem"
            params["sem"] = int(semester)
        if subject:
            query_str += " AND s.name ILIKE :sub"
            params["sub"] = f"%{subject.strip()}%"

        query_str += " ORDER BY st.student_name, s.name LIMIT 200"

        rows = session.execute(text(query_str), params).fetchall()
        if not rows:
            return f"Không tìm thấy dữ liệu điểm cho lớp '{class_name}' môn '{subject}' trong học kỳ {semester}."

        results = []
        for r in rows:
            pf_val = str(r[8]).upper() if r[8] else None
            pf_str = "ĐẠT" if pf_val == "DAT" else ("CHƯA ĐẠT" if pf_val == "CHUA_DAT" else "N/A")
            is_remark = (r[9] == "REMARK")

            item = {
                "Mã học sinh": r[0],
                "Họ và Tên": r[1],
                "Môn học": r[2],
                "Lớp": r[3],
                "Học kỳ": r[4],
                "Bài kiểm tra": r[5],
                "Hình thức đánh giá": "Đánh giá bằng nhận xét (REMARK)" if is_remark else "Chấm điểm số (SCORED)",
                "Điểm số": float(r[6]) if r[6] is not None else ("N/A (Đánh giá nhận xét)" if is_remark else "N/A"),
                "Kết quả (Đạt/Chưa đạt)": pf_str,
            }
            if r[7]:
                item["Điểm chữ"] = r[7]
            results.append(item)

        return json.dumps(results, ensure_ascii=False, indent=2)


@tool
def execute_read_only_query(sql_query: str) -> str:
    """Thực thi câu lệnh SQL SELECT an toàn để lấy dữ liệu thô dạng JSON phục vụ cho việc phân tích dữ liệu.

    Args:
        sql_query: Câu truy vấn SQL SELECT hợp lệ (ví dụ: 'SELECT * FROM s360.fact_gradebooks').
    """
    school_id = current_user_school_id.get() or 1
    user_role = current_user_role.get()

    # Pre-check: Phát hiện multi-statement SQL (semicolon split)
    cleaned = re.sub(r"--.*$", "", sql_query, flags=re.MULTILINE)       # Xoá line comment -- ...
    cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)        # Xoá block comment /* ... */
    cleaned = re.sub(r"'(?:[^'\\]|\\.)*'", "", cleaned)                  # Xoá string literals
    cleaned = cleaned.rstrip(";")                                        # Strip trailing ; (hợp lệ)
    if ";" in cleaned:
        return "LỖI: Phát hiện nhiều câu lệnh SQL trong 1 lượt gọi. " \
               "Mỗi lượt gọi chỉ được gửi DUY NHẤT 1 câu lệnh SELECT. " \
               "Vui lòng chia thành các câu lệnh đơn riêng biệt."

    try:
        # 1. Bảo mật và lọc theo school_id sử dụng SQLGlot
        secured_query = validate_and_secure_sql(sql_query, str(school_id))

        # 2. Thực thi câu lệnh SQL thô trên DB
        with engine.connect() as conn:
            conn.execute(text("SET statement_timeout = 5000;"))
            result = conn.execute(text(secured_query))
            columns = result.keys()
            rows = [dict(zip(columns, row)) for row in result.fetchall()]
            return json.dumps(rows, default=str, ensure_ascii=False, indent=2)

    except Exception as e:
        return f"Lỗi thực thi truy vấn SQL: {str(e)}"

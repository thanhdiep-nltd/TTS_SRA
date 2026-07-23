from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, SystemMessage

from src.agents.context import current_user_id, current_user_role, current_user_school_id
from src.agents.sql_agent.tools import execute_read_only_query
from src.agents.state import MultiAgentState
from src.services.entity_linker import resolve_entities
from src.services.llm import get_llm

SQL_AGENT_PROMPT = """Bạn là SQL Analyst Agent, một chuyên gia phân tích dữ liệu chuyên nghiệp sử dụng SQL và phân tích số liệu thô.
Nhiệm vụ của bạn là giải quyết các câu hỏi phức tạp về mối tương quan, phân tích phân phối, hoặc các tính toán tùy biến đặc biệt mà các Agent khác không hỗ trợ bằng cách viết và thực thi câu lệnh SQL SELECT tối ưu.

SƠ ĐỒ CƠ SỞ DỮ LIỆU KHO DỮ LIỆU HỌC SINH STUDENT 360 (S360 & PUBLIC SCHEMAS):

[SCHEMA: public]
1. Bảng `public.users`: Người dùng (Giáo viên, Học sinh, BGH). 
   - Các cột: `id` (BIGINT PK), `so_school_id` (INT - Mã trường), `teacher_code`, `student_code`, `so_student_id`, `full_name`, `role` ('ADMIN', 'PRINCIPAL', 'SUBJECT_HEAD', 'TEACHER', 'STUDENT', 'PARENT'), `is_active` (BOOLEAN).

2. Bảng `public.classroom_recordings`: Ghi âm & đánh giá bài giảng AI.
   - Các cột: `id` (BIGINT PK), `so_school_id` (INT), `teacher_id` (FK -> public.users.id), `subject_id` (FK -> s360.dim_subject.id), `class_id` (FK -> s360.dim_homeroom_class.id), `lesson_name`, `period`, `date`, `rank_assessment` ('EXCELLENT', 'GOOD', 'PASS', 'NEEDS_IMPROVEMENT').

[SCHEMA: s360 - DIMENSIONS]
3. Bảng `s360.dim_school_year`: Danh mục Năm học.
   - Các cột: `id` (INT PK, vd: 2025), `code` (vd: '2025_2026'), `fullname` (vd: 'Năm học 2025 - 2026').

4. Bảng `s360.dim_homeroom_class`: Lớp học chủ nhiệm.
   - Các cột: `id` (INT PK), `school_year_id` (FK -> s360.dim_school_year.id), `so_school_id` (INT), `grade_id` (INT, Khối 6 đến 12), `code` (Mã lớp, vd: '10A1', '8A1'), `fullname` (Tên lớp, vd: 'Lớp 10A1', 'Lớp 8A1'). (LƯU Ý: Cột tên lớp là `fullname` và mã lớp là `code`, KHÔNG dùng class_code/class_name/grade_number!).

5. Bảng `s360.dim_homeroom_class_student`: Danh sách Học sinh thuộc lớp chủ nhiệm.
   - Các cột: `id` (BIGINT PK), `homeroom_class_id` (FK -> s360.dim_homeroom_class.id), `so_student_id`, `student_code`, `student_name` (Họ tên học sinh - BẮT BUỘC DÙNG CỘT NÀY CHO TÊN HỌC SINH!), `class_name`, `grade_id`, `gender` ('MALE', 'FEMALE'), `is_active` (1/0).

6. Bảng `s360.dim_subject`: Danh mục Môn học.
   - Các cột: `id` (INT PK), `code` (vd: 'ROBOTICS', 'TOAN_10'), `name` (vd: 'STEM & Robotics', 'Toán học Khối 10', 'Ngữ văn'), `assessment_type` ('SCORED' cho điểm, 'REMARK' Đạt/Chưa đạt), `default_scale_name`.

7. Bảng `s360.dim_exam`: Danh mục Kỳ thi & Đầu điểm kiểm tra định kỳ LMS Vinschool.
   - Các cột: `id` (BIGINT PK), `so_exam_id`, `school_year_id`, `subject_id` (FK), `grade_id`, `exam_code`, `exam_name` (vd: 'Progress Check 1 HK1 Khối 10 - Môn STEM & Robotics'), `coefficient`, `moet_semester_index` (1 hoặc 2), `max_grade`.

8. Bảng `s360.dim_exam_moet`: Đầu điểm kiểm tra định kỳ chuẩn Bộ GD&ĐT (MOET).
   - Các cột: `gradebook_type_item_id` (BIGINT PK), `gradebook_type_items_fullname` (tên đầu điểm), `moet_semester_index` (1 hoặc 2).

9. Bảng `s360.dim_so_assignment`: Bài tập tuần trên LMS.
   - Các cột: `assignment_id` (BIGINT PK), `so_school_id` (INT), `grade_id`, `semester_index`, `subject_id` (FK), `code`, `fullname` (vd: 'Bài tập LMS Tuần 1'), `max_grade`.

10. Bảng `s360.dim_grade_scale_detail`: Ma trận Thang điểm quy đổi Vinschool & MOET.
    - Các cột: `id` (BIGINT PK), `so_school_id` (INT), `scale_name` ('SCALE_10', 'SCALE_100', 'LETTER_A_F', 'GPA_4', 'PASS_FAIL'), `grade_letter`, `grade_label` ('Xuất sắc', 'Giỏi', 'Khá', 'Trung bình', 'Yếu', 'Kém').

[SCHEMA: s360 - FACTS]
11. Bảng `s360.fact_gradebooks`: Sổ điểm kiểm tra định kỳ Vinschool trên lớp.
    - Các cột: `id` (BIGINT PK), `so_school_id` (INT), `school_year_id` (FK), `semester_index` (1 hoặc 2), `student_code`, `homeroom_class_id` (FK), `subject_id` (FK), `so_exam_id` (FK -> s360.dim_exam.id), `final_grade` (Điểm số), `final_grade_letter`, `pass_fail_status`.
    - LẤY HỌ TÊN HỌC SINH BẰNG CÁCH JOIN: `LEFT JOIN s360.dim_homeroom_class_student st ON fg.student_code = st.student_code AND fg.homeroom_class_id = st.homeroom_class_id` (lấy `st.student_name`).

12. Bảng `s360.fact_gradebooks_moet`: Sổ điểm chuẩn Bộ GD&ĐT (MOET).
    - Các cột: `id` (BIGINT PK), `so_school_id` (INT), `school_year_id` (FK), `semester_index` (1 hoặc 2), `grade_id`, `subject_id` (FK), `student_code`, `homeroom_class_id` (FK), `gradebook_type_item_id` (FK -> s360.dim_exam_moet.gradebook_type_item_id), `final_grade` (0.0 đến 10.0).

13. Bảng `s360.fact_so_assignment_grade`: Điểm bài tập tuần LMS.
    - Các cột: `id` (BIGINT PK), `so_school_id` (INT), `assignment_id` (FK -> s360.dim_so_assignment.assignment_id), `student_code`, `final_grade` (0.0 đến 10.0).

14. Bảng `s360.fact_subject_academic_records`: Học bạ tổng kết theo môn học.
    - Các cột: `id` (BIGINT PK), `overall_record_id` (FK -> s360.fact_overall_academic_records.id), `subject_id` (FK), `student_code`, `final_grade` (ĐTB môn cả năm), `s1_final_grade` (ĐTB môn HK1), `s2_final_grade` (ĐTB môn HK2).

15. Bảng `s360.fact_overall_academic_records`: Học bạ tổng kết toàn diện (Học lực, Hạnh kiểm, ĐTB toàn diện).
    - Các cột: `id` (BIGINT PK), `so_school_id` (INT), `school_year_id` (FK), `grade_id`, `homeroom_class_id` (FK), `student_id` (FK -> public.users.id), `student_code`, `final_grade` (ĐTB cả năm), `s1_final_grade` (HK1), `s2_final_grade` (HK2), `conduct`, `s1_conduct`, `s2_conduct`, `learning_capacity`, `s1_learning_capacity`, `s2_learning_capacity`.

QUY TẮC VẬN HÀNH BẮT BUỘC:
1. CHẾ ĐỘ SINGLE-SHOT QUERY EXECUTION:
   - Bạn BẮT BUỘC phải viết trực tiếp câu lệnh SQL SELECT lấy dữ liệu mục tiêu ngay trong lượt thực thi đầu tiên dựa trên các EXACT VALUES/IDs được cung cấp trong khối context "THÔNG TIN DANH MỤC ĐÃ ĐƯỢC CHUẨN HÓA".
   - CẤM TUYỆT ĐỐI việc tự ý sinh các câu SQL phụ dạng SELECT DISTINCT hay ILIKE để tự đi dò tìm danh mục trên CSDL khi Context đã có thông tin chuẩn hóa.
2. CƠ CHẾ SELF-CORRECTION:
   - KHI VÀ CHỈ KHI CSDL PostgreSQL trả về lỗi thực thi (Runtime Error), bạn mới được phép tự soi schema (via information_schema.columns) hoặc sửa lại câu lệnh SQL để thử lại.
3. Bạn có công cụ `execute_read_only_query` để chạy truy vấn SQL SELECT thô duy nhất đó.
4. Trình bày kết quả phân tích rõ ràng, mạch lạc dựa trên dữ liệu thực thu thập được.
"""

# Khởi tạo agent trễ (lazy initialization) để tránh gọi get_llm() lúc import file,
# giúp dễ dàng mock LLM khi viết unit test.
_sql_agent = None


def get_sql_agent():
    global _sql_agent
    if _sql_agent is None:
        tools = [execute_read_only_query]
        _sql_agent = create_react_agent(get_llm(), tools=tools, prompt=SQL_AGENT_PROMPT)
    return _sql_agent


async def sql_agent_node(state: MultiAgentState) -> dict:
    """Node trong Graph điều hướng chạy SQL Analyst Agent."""
    # Đồng bộ ContextVars từ school_context trong state để an toàn tuyệt đối
    school_ctx = state.get("school_context", {})
    so_school_id = 1
    if school_ctx:
        if school_ctx.get("school_id"):
            current_user_school_id.set(school_ctx.get("school_id"))
            try:
                so_school_id = int(school_ctx.get("school_id"))
            except Exception:
                pass
        if school_ctx.get("role"):
            current_user_role.set(school_ctx.get("role"))
        if school_ctx.get("user_id"):
            current_user_id.set(school_ctx.get("user_id"))

    # Kích hoạt Dynamic Entity Resolution (Hybrid Search) để trích xuất Exact Values/IDs
    messages = list(state.get("messages", []))
    query = state.get("query", "")
    if not query and messages:
        last_msg = messages[-1]
        query = last_msg.content if hasattr(last_msg, "content") else str(last_msg)

    entity_ctx = resolve_entities(query, so_school_id)

    if messages and entity_ctx.formatted_prompt_context:
        last_msg = messages[-1]
        raw_text = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
        new_content = f"{entity_ctx.formatted_prompt_context}\n\n[YÊU CẦU NGUỜI DÙNG]: {raw_text}"
        messages[-1] = HumanMessage(content=new_content)

    # Chạy ReAct loop thông qua compiled agent
    agent_instance = get_sql_agent()
    prepended_len = len(messages) - 1
    result = await agent_instance.ainvoke({"messages": messages})

    # Chỉ trả về phần tin nhắn mới được sinh ra bởi Agent này
    new_messages = result["messages"][prepended_len:]
    return {
        "messages": new_messages,
    }

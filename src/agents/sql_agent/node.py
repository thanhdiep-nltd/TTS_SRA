from langgraph.prebuilt import create_react_agent

from src.agents.context import current_user_id, current_user_role, current_user_school_id
from src.agents.sql_agent.tools import execute_read_only_query
from src.agents.state import MultiAgentState
from src.services.llm import get_llm

SQL_AGENT_PROMPT = """Bạn là SQL Analyst Agent, một chuyên gia phân tích dữ liệu chuyên nghiệp sử dụng SQL và phân tích số liệu thô.
Nhiệm vụ của bạn là giải quyết các câu hỏi phức tạp về mối tương quan, phân tích phân phối, hoặc các tính toán tùy biến đặc biệt mà các Agent khác không hỗ trợ bằng cách viết và thực thi câu lệnh SQL SELECT tối ưu.

SƠ ĐỒ CƠ SỞ DỮ LIỆU ĐỂ BẠN TRUY VẤN (Tất cả khóa chính là 'id' dạng UUID):
1. Bảng `grades`: khối lớp. Các cột: `id`, `grade_number` (khối lớp: 6 đến 12), `school_id`
2. Bảng `classes`: lớp học. Các cột: `id`, `grade_id` (foreign key trỏ đến grades.id), `name` (tên lớp: ví dụ '8A1', '10A2')
3. Bảng `students`: học sinh. Các cột: `id`, `student_code` (mã HS), `full_name` (họ tên), `school_id`
4. Bảng `subjects`: môn học. Các cột: `id`, `name` (tên môn: ví dụ 'Toán học', 'Vật lý', 'Ngữ văn', 'Hóa học', 'Sinh học', 'Tiếng Anh', 'Khoa học tự nhiên'), `school_id`
5. Bảng `semesters`: học kỳ. Các cột: `id`, `name` (Tên học kỳ: chỉ nhận 'HK1' hoặc 'HK2'), `number` (1 hoặc 2), `academic_year_id`
6. Bảng `academic_years`: năm học. Các cột: `id`, `name` (ví dụ: '2023-2024')
7. Bảng `scores`: điểm số. Các cột:
   - `student_id` (foreign key trỏ đến students.id)
   - `subject_id` (foreign key trỏ đến subjects.id)
   - `class_id` (foreign key trỏ đến classes.id)
   - `semester_id` (foreign key trỏ đến semesters.id)
   - `score_category` (Enum nhận các giá trị: 'ORAL' - miệng, 'REGULAR' - thường xuyên/hệ 1, 'MIDTERM' - giữa kỳ/hệ 2, 'FINAL' - cuối kỳ/hệ 3)
   - `column_index` (chỉ số cột điểm: 1, 2, 3...)
   - `value` (giá trị điểm số từ 0.00 đến 10.00)
   - `status` (Enum trạng thái điểm: chỉ lọc các dòng có status = 'APPROVED')

CÔNG THỨC TÍNH ĐIỂM TRUNG BÌNH MÔN HỌC KỲ (ĐTB):
ĐTB = (Tổng các điểm hệ 1 + 2 * Điểm Giữa Kỳ + 3 * Điểm Cuối Kỳ) / (Số lượng điểm hệ 1 + 5)
Trong đó, điểm hệ 1 bao gồm cả 'ORAL' và 'REGULAR'.

Quy tắc làm việc:
1. Bạn có công cụ `execute_read_only_query` để chạy truy vấn SQL SELECT thô và lấy dữ liệu thô dạng JSON.
2. Dựa vào sơ đồ cơ sở dữ liệu trên, hãy tự thiết lập câu lệnh SQL SELECT (sử dụng JOIN chính xác) để lấy đúng và đủ dữ liệu cần thiết (tránh SELECT quá nhiều dữ liệu không cần thiết).
3. Nếu thực thi SQL gặp lỗi (lỗi cú pháp, sai tên cột, hoặc do cơ chế bảo mật hạn chế của hệ thống), hãy đọc kỹ thông báo lỗi, tự debug phân tích nguyên nhân và điều chỉnh câu lệnh SQL để chạy lại (self-correction) cho đến khi thành công.
4. Sau khi nhận được kết quả dữ liệu thô dạng JSON, hãy phân tích dữ liệu trực tiếp dựa trên kết quả đó (tính toán các chỉ số thống kê, tìm mối tương quan, nhận xét phân phối...). Trình bày kết quả một cách mạch lạc, chính xác.
5. Chỉ hiển thị dữ liệu thực thu thập được, không bịa ra thông tin. KHÔNG sử dụng hoặc đề cập đến thư viện Pandas hay viết code Python trong câu trả lời của bạn.
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
    if school_ctx:
        if school_ctx.get("school_id"):
            current_user_school_id.set(school_ctx.get("school_id"))
        if school_ctx.get("role"):
            current_user_role.set(school_ctx.get("role"))
        if school_ctx.get("user_id"):
            current_user_id.set(school_ctx.get("user_id"))

    # Chạy ReAct loop thông qua compiled agent
    agent_instance = get_sql_agent()
    result = await agent_instance.ainvoke({"messages": state["messages"]})

    # Chỉ trả về phần tin nhắn mới được thêm bởi Agent này để tránh trùng lặp trong State
    input_len = len(state.get("messages", []))
    new_messages = result["messages"][input_len:]
    return {
        "messages": new_messages,
    }

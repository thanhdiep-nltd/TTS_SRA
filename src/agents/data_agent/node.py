from langgraph.prebuilt import create_react_agent

from src.agents.context import current_user_id, current_user_role, current_user_school_id
from src.agents.data_agent.tools import get_class_grades, get_student_grades, get_student_info
from src.agents.state import MultiAgentState
from src.services.llm import get_llm

DATA_AGENT_PROMPT = """Bạn là Data Agent chuyên truy xuất dữ liệu thông tin học sinh và bảng điểm thô từ cơ sở dữ liệu.
Nhiệm vụ của bạn là giải quyết các câu hỏi về tra cứu thông tin cá nhân của học sinh, xem điểm chi tiết của học sinh theo môn/học kỳ/năm học hoặc xem bảng điểm của một lớp.

Quy tắc làm việc:
- Sử dụng các công cụ được cung cấp để lấy dữ liệu chính xác nhất.
- Trả về dữ liệu thô hoặc kết quả trực tiếp, định dạng rõ ràng (sử dụng Markdown table nếu cần).
- Tránh đưa ra các nhận xét, đánh giá hoặc phân tích học lực sâu (tác vụ đó thuộc về Stat Agent).
- Chỉ hiển thị dữ liệu có thực, không tự bịa ra thông tin.
"""

# Khởi tạo agent trễ (lazy initialization) để tránh gọi get_llm() lúc import file,
# giúp dễ dàng mock LLM khi viết unit test.
_data_agent = None


def get_data_agent():
    global _data_agent
    if _data_agent is None:
        tools = [get_student_info, get_student_grades, get_class_grades]
        _data_agent = create_react_agent(get_llm(), tools=tools, prompt=DATA_AGENT_PROMPT)
    return _data_agent


async def data_agent_node(state: MultiAgentState) -> dict:
    """Node trong Graph điều hướng chạy Data Agent."""
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
    agent_instance = get_data_agent()
    result = await agent_instance.ainvoke({"messages": state["messages"]})

    # Chỉ trả về phần tin nhắn mới được thêm bởi Agent này để tránh trùng lặp trong State
    input_len = len(state.get("messages", []))
    new_messages = result["messages"][input_len:]
    return {
        "messages": new_messages,
    }

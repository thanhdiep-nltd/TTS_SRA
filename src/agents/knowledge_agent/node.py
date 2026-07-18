from langgraph.prebuilt import create_react_agent

from src.agents.knowledge_agent.tools import search_textbook
from src.agents.state import MultiAgentState
from src.services.llm import get_llm

KNOWLEDGE_AGENT_PROMPT = """Bạn là Knowledge Agent, chuyên tra cứu và giải thích NỘI DUNG KIẾN THỨC
trong sách giáo khoa (Toán, Ngữ Văn, Khoa học tự nhiên, Lịch sử-Địa lí, Tiếng Anh, Tin học,
Công nghệ, GDCD, HĐTN — khối 6 đến 9).

Nhiệm vụ: trả lời các câu hỏi về định nghĩa, công thức, khái niệm, cách giải, nội dung bài học.
KHÔNG xử lý câu hỏi về điểm số/hồ sơ học sinh (việc đó của các agent khác).

Quy tắc làm việc (BẮT BUỘC):
1. LUÔN gọi công cụ `search_textbook` để lấy ngữ liệu trước khi trả lời. Nếu câu hỏi nêu rõ
   môn/lớp, hãy truyền tham số `mon`/`lop` để thu hẹp kết quả.
2. Chỉ trả lời DỰA TRÊN nội dung truy xuất được. Tuyệt đối KHÔNG bịa thêm kiến thức ngoài ngữ liệu.
3. LUÔN trích dẫn nguồn (môn, lớp, tên mục) cho thông tin đưa ra.
4. Nếu công cụ báo không tìm thấy nội dung phù hợp, hãy nói rõ là không có dữ liệu trong sách giáo
   khoa cho yêu cầu này, KHÔNG tự bịa câu trả lời.
5. Nếu kết quả chưa đủ, có thể gọi lại công cụ với từ khóa/môn/lớp khác để tìm thêm.
"""

# Lazy-init để tránh gọi get_llm() lúc import (dễ mock trong test).
_knowledge_agent = None


def get_knowledge_agent():
    global _knowledge_agent
    if _knowledge_agent is None:
        _knowledge_agent = create_react_agent(get_llm(), tools=[search_textbook], prompt=KNOWLEDGE_AGENT_PROMPT)
    return _knowledge_agent


async def knowledge_agent_node(state: MultiAgentState) -> dict:
    """Node chạy Knowledge Agent (RAG). Tri thức SGK toàn cục → KHÔNG cần ContextVar tenant."""
    agent_instance = get_knowledge_agent()
    result = await agent_instance.ainvoke({"messages": state["messages"]})

    # Chỉ trả message MỚI để tránh trùng lặp trong State (giống các sub-agent khác).
    input_len = len(state.get("messages", []))
    new_messages = result["messages"][input_len:]
    return {"messages": new_messages}

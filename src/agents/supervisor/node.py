import re

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.agents.context import current_user_id, current_user_role, current_user_school_id
from src.agents.state import MultiAgentState
from src.observability import logger
from src.services.llm import get_llm


class RouterDecision(BaseModel):
    next_agent: str = Field(
        description=(
            "Chọn agent tiếp theo cần gọi: 'data_service_agent' (cho TẤT CẢ tra cứu CSDL, thông tin/điểm số thô, bảng điểm cá nhân, bảng điểm lớp, hoặc truy vấn thống kê toàn khối lớp), "
            "'stat_agent' (cho phân tích thống kê/chỉ số sâu GDI, Delta G, Momentum, độ khó đề thi EDI/CDI), "
            "'knowledge_agent' (cho tra cứu NỘI DUNG kiến thức môn học từ sách giáo khoa: định nghĩa, công thức, giải thích bài học), "
            "'report_agent' (cho lập báo cáo, xem trước hoặc tải về báo cáo Word, PDF), "
            "'CLARIFICATION' (nếu cần hỏi lại để làm rõ thông tin thiếu hoặc khi câu hỏi chỉ là chào hỏi xã giao thông thường), "
            "hoặc 'FINISH' nếu đã thu thập đủ thông tin để tổng hợp trả lời."
        )
    )
    instruction: str = Field(
        description="Hướng dẫn chi tiết cho agent tiếp theo về nhiệm vụ cần làm hoặc thông tin cần lấy."
    )
    response: str | None = Field(
        default=None,
        description=(
            "Nếu chọn 'CLARIFICATION' hoặc 'FINISH' và đây là câu hỏi thường/chào hỏi/xã giao hoặc câu hỏi không liên quan đến học vụ trường học "
            "(không cần gọi bất kỳ sub-agent nào), hãy viết câu trả lời hoặc câu hỏi làm rõ trực tiếp đầy đủ và thân thiện cho người dùng tại đây."
        ),
    )


SUPERVISOR_PROMPT = """Bạn là Supervisor điều phối hệ thống phân tích kết quả học tập toàn trường (Trợ Lý A.I EduOwl).
1. `data_service_agent`: Chuyên trách TẤT CẢ các tác vụ liên quan đến CSDL (tra cứu điểm số cá nhân, điểm lớp học, sĩ số, danh sách học sinh, học bạ, hoặc phân tích truy vấn SQL). Viết instruction rõ ràng truyền đạt nhiệm vụ cần tra cứu và bảo toàn nguyên văn các từ khóa họ tên học sinh, tên lớp, môn học của người dùng.
2. `stat_agent`: Chuyên trách tính toán thống kê, tìm thủ khoa/học sinh yếu, phân tích xu hướng học tập, so sánh các lớp, tính toán chỉ số GDI, Delta G, Momentum, và phân tích tam giác hóa độ khó đề thi (đối chiếu độ tin cậy điểm số EDI vs độ khó đề thi CDI). ĐẶC BIỆT LƯU Ý: Mọi câu hỏi của người dùng hỏi về "độ khó của đề thi", "đánh giá đề thi", "nhận xét đề thi", hoặc "đề thi khó hay dễ" đều ứng với nghiệp vụ tam giác hóa độ khó đề thi và BẮT BUỘC phải định tuyến sang `stat_agent` (không chuyển sang data_service_agent). Ngoài ra, nếu người dùng hỏi về một lớp học cụ thể (ví dụ: lớp 6A1), hãy suy luận ra khối lớp tương ứng (ví dụ: Khối 6) và điều hướng sang stat_agent vì đề thi và ma trận đề (CDI) được quản lý chung theo khối lớp.
3. `knowledge_agent`: Chuyên trách tra cứu NỘI DUNG KIẾN THỨC trong sách giáo khoa (định nghĩa, công thức, khái niệm, giải thích bài học của các môn Toán, Ngữ Văn, KHTN, Sử-Địa...). Dùng cho câu hỏi về nội dung học thuật, KHÔNG dùng cho điểm số/hồ sơ học sinh.
4. `report_agent`: Chuyên trách tổng hợp số liệu báo cáo, tạo bảng hiển thị xem trước báo cáo thống kê, hoặc cung cấp đường link tải xuống các tệp báo cáo thống kê (Word, HTML/PDF). Hãy gọi agent này khi người dùng yêu cầu xuất báo cáo, tải báo cáo, lập báo cáo, hoặc khi muốn xem số liệu tổng quan của một loại báo cáo cụ thể.
5. `CLARIFICATION`: Chọn trạng thái này khi bạn cần hỏi lại người dùng để làm rõ thông tin thiếu (như thiếu năm học, thiếu học kỳ, mơ hồ lớp học) HOẶC khi câu hỏi chỉ là chào hỏi xã giao bình thường. Bắt buộc viết nội dung phản hồi trực tiếp vào trường `response`.
6. `FINISH`: Chọn trạng thái này KHI VÀ CHỈ KHI bạn đã thu thập đầy đủ thông tin từ các Sub-Agent để tổng hợp trả lời câu hỏi gốc của người dùng.

Quy trình & Quy tắc tối ưu hóa phản hồi:
- Đọc câu hỏi của người dùng và lịch sử đối thoại.
- Tuyệt đối KHÔNG sử dụng bất kỳ biểu tượng cảm xúc (emoji/icon) nào như 📊, 🎯, 📌, ⚠️, 🔴, 🟢, 🏆, 📈, 📉, 🥇... trong toàn bộ văn bản phản hồi. Hãy trình bày văn bản trang trọng, học thuật thuần túy chỉ dùng các yếu tố markdown chuẩn (in đậm, danh sách, bảng) thay thế cho emoji.
- KIỂM TRA ĐẦU VÀO VÀ CHỦ ĐỘNG HỎI LẠI (Active Clarification Principles):
  Trước khi định tuyến sang bất kỳ sub-agent nào, hãy kiểm tra xem yêu cầu của người dùng đã đầy đủ thông tin chưa hay có bị mơ hồ không. Chọn `next_agent` = 'CLARIFICATION' khi rơi vào một trong các trường hợp mơ hồ sau:

  1. MƠ HỒ THỜI GIAN (Temporal Uncertainty):
     - Thiếu Niên khóa (VD: `2024-2025`, `2025-2026`) hoặc Học kỳ (HK1, HK2, Cả năm) khi tra cứu điểm số / lập báo cáo. Cơ sở dữ liệu lưu năm học dạng khoảng, nếu người dùng chỉ nói 1 năm đơn lẻ (VD: "năm 2025") hoặc không nói năm học, BẮT BUỘC chọn 'CLARIFICATION' để hỏi người dùng.
  2. MƠ HỒ PHẠM VI & THỰC THỂ (Scope & Entity Uncertainty):
     - Chưa rõ Phạm vi: Giữa toàn bộ Khối lớp (VD: Khối 10) vs một Lớp cụ thể (VD: 10A1). Lưu ý: Nếu người dùng đề cập đến TOÀN BỘ KHỐI LỚP (VD: "toàn bộ Khối 10", "Khối 6"), hãy định tuyến trực tiếp sang `data_service_agent` để truy vấn CSDL. Nếu người dùng chỉ nói chung chung "lớp 10" mà chưa rõ là một lớp cụ thể hay toàn khối, hãy chọn 'CLARIFICATION'.
     - Chưa rõ Thực thể: Tên học sinh trùng lặp, hoặc tên môn học/đợt thi chưa đủ chi tiết.
  3. MƠ HỒ TIÊU CHÍ & ĐỊNH DẠNG (Criteria & Output Uncertainty):
     - Thiếu tiêu chí đánh giá (VD: Điểm TB GPA vs Hạnh kiểm/Điểm rèn luyện) hoặc định dạng mong muốn (Tải file Báo cáo Word/PDF vs Xem tóm tắt trên Chat).
  4. YÊU CẦU CHƯA ĐỦ CÂU / CHÀO HỎI (Incomplete Query / Greetings):
     - Câu hỏi rời rạc 1-2 từ không rõ ý định, hoặc các câu chào hỏi xã giao thông thường.
  5. ĐỊNH DẠNG THẺ LỰA CHỌN TƯƠNG TÁC (INTERACTIVE OPTION CARD):
     Khi chọn `next_agent` là 'CLARIFICATION' để hỏi người dùng chọn lựa chọn (ví dụ: chọn năm học, học kỳ, khối lớp hay danh mục quy trình), bạn BẮT BUỘC phải bổ sung khối `[OPTIONS_CARD]` trong trường `response` theo đúng cấu trúc JSON sau:
     [OPTIONS_CARD]
     {
       "title": "Tiêu đề tùy chọn làm rõ",
       "prompt": "Lời dẫn hỏi người dùng chọn...",
       "options": ["Lựa chọn 1", "Lựa chọn 2", "Lựa chọn 3"]
     }
     [/OPTIONS_CARD]
     Ví dụ:
     Thầy/cô vui lòng chọn năm học và học kỳ cần tra cứu:
     [OPTIONS_CARD]
     {
       "title": "Vui lòng chọn năm học",
       "prompt": "Hệ thống hỗ trợ dữ liệu các năm học dưới đây:",
       "options": ["Năm học 2024-2025", "Năm học 2025-2026", "Tất cả các năm học"]
     }
     [/OPTIONS_CARD]
- QUY TẮC PHÂN QUYỀN BẢO MẬT GIÁO VIÊN (RBAC Security Guardrail):
  Nếu sub-agent trả về kết quả chứa `ACCESS_DENIED` hoặc có nội dung "nằm ngoài phạm vi phân quyền"/"không có quyền truy cập" (ví dụ: Giáo viên hỏi lớp/khối/môn không được phân công), hãy chọn `FINISH` NGAY và phản hồi lịch sự:
  "Rất tiếc, theo chính sách phân quyền học vụ, tài khoản của bạn không có quyền truy cập dữ liệu của lớp/khối/môn học này."
  TUYỆT ĐỐI KHÔNG xem ACCESS_DENIED là "không có dữ liệu", KHÔNG yêu cầu sub-agent thử lại lần nữa, KHÔNG hướng dẫn nhập liệu.

QUY TẮC ĐỊNH DẠNG BẮT BUỘC:
- Bạn phải LUÔN LUÔN đưa ra quyết định bằng cách gọi công cụ `RouterDecision`.
- Nếu môi trường chạy không hỗ trợ gọi công cụ trực tiếp (tool calling), bạn BẮT BUỘC phải trả về một khối JSON hợp lệ chứa các thông tin này trong câu trả lời của mình:
```json
{
  "next_agent": "tên_agent_hoặc_FINISH_hoặc_CLARIFICATION",
  "instruction": "hướng_dẫn_cho_agent",
  "response": "câu_trả_lời_trực_tiếp_nếu_next_agent_là_CLARIFICATION_hoặc_FINISH_và_không_cần_sub_agent_xử_lý"
}
```
- Ví dụ sai (CẤM): {"report_type": "academic_conduct", "grade_level": "6"}
- Ví dụ đúng: {"next_agent": "report_agent", "instruction": "Lập báo cáo học kỳ 1 năm học 2025-2026 cho khối 6 dạng docx bằng cách gọi công cụ get_report_data_summary", "response": ""}
Tuyệt đối KHÔNG trả lời bằng lời thoại trò chuyện thông thường ở lượt điều phối đầu tiên.

🔴 QUY TẮC PHÂN BIỆT CHỦ ĐỀ (TOPIC BOUNDARY RULE):
1. <current_user_query>: Chứa câu hỏi HIỆN TẠI của người dùng (đã reformulate thành standalone). Đây là ưu tiên cao nhất để quyết định routing.
2. <conversation_history_FOR_REFERENCE_ONLY>: Chứa lịch sử các lượt hội thoại TRƯỚC đây (các câu hỏi - câu trả lời cũ).
   - Chỉ dùng thẻ này khi câu hỏi hiện tại thiếu thành phần (ẩn chủ ngữ, đại từ chỉ định: "bạn ấy", "em đó").
   - Nếu câu hỏi hiện tại là một câu hỏi hoàn chỉnh về đối tượng/lớp/khối hoàn toàn mới → BỎ QUA thẻ này, không tự ý gán học sinh/question cũ vào câu hỏi mới.
3. <current_turn_collected_data>: Chứa dữ liệu các Sub-Agent vừa thu thập được trong lượt xử lý HIỆN TẠI.
   - Đây là thẻ QUAN TRỌNG NHẤT để quyết định FINISH hay route tiếp.
   - Nếu trong thẻ này đã có kết quả dữ liệu từ Sub-Agent (số liệu, bảng, câu trả lời cụ thể) → BẮT BUỘC chọn FINISH để tổng hợp.
   - Nếu thẻ này CHỈ chứa instruction của Supervisor (chưa có kết quả thực tế) → route tiếp Sub-Agent phù hợp.
"""

# ── LLM Query Contextualizer: Helper functions ──────────────────────────────

def _build_recent_context(messages_list: list, max_turns: int = 2) -> str:
    """Build text context từ 2-3 turn gần nhất để làm đầu vào cho Contextualizer."""
    human_indices = []
    for idx, msg in enumerate(messages_list):
        if getattr(msg, "type", None) == "human" or msg.__class__.__name__ in ("HumanMessage", "HumanMessageChunk"):
            human_indices.append(idx)

    if len(human_indices) > max_turns:
        start_idx = human_indices[-max_turns]
    else:
        start_idx = 0

    recent_msgs = messages_list[start_idx:]

    lines = []
    for msg in recent_msgs:
        msg_type = getattr(msg, "type", "unknown")
        content = str(getattr(msg, "content", "") or "")
        if content.strip():
            role_label = "Người dùng" if msg_type == "human" else "AI"
            lines.append(f"{role_label}: {content[:500]}")

    return "\n".join(lines)


async def _reformulate_standalone_query(
    past_messages: list,
    current_query: str,
) -> str:
    """
    LLM Query Contextualizer: Quy đổi User Query + Chat History thành
    Standalone Query độc lập tự thân (Hướng 1: Enterprise Safety Standard).

    CHỈ nhận past_messages (các lượt hội thoại TRƯỚC câu hỏi hiện tại).
    KHÔNG nhận current_turn_messages để tránh nhiễu từ dữ liệu sub-agent vừa cào về.

    - Turn 1 (past_messages rỗng): Return current_query ngay (tiết kiệm 100% latency)
    - Turn 2+ (có history): Gọi LLM Contextualizer nếu cần
    """
    # Turn 1: không có past messages -> return ngay
    if not past_messages:
        return current_query

    # Build context từ 2 turn gần nhất trong past_messages
    recent_history = _build_recent_context(past_messages, max_turns=2)
    if not recent_history.strip():
        return current_query

    llm = get_llm()
    prompt = (
        "Bạn là Chuyên gia Tinh chỉnh Cấu trúc Câu hỏi (Standalone Query Reformulator).\n\n"
        "Nhiệm vụ: Dựa vào [Lịch sử hội thoại] và [Câu hỏi hiện tại], hãy chuyển đổi câu hỏi hiện tại "
        "thành một CÂU HỎI ĐỘC LẬP TỰ THÂN (Standalone Query) có thể đứng một mình mà người đọc "
        "vẫn hiểu đầy đủ ý định mà KHÔNG cần xem lại lịch sử.\n\n"
        "NGUYÊN TẮC NỀN TẢNG (CORE PRINCIPLES):\n\n"
        "1. KHÔI PHÚC THÀNH PHẦN ẨN & THỪA KẾ NGỮ CẢNH (Anaphora & Ellipsis Resolution):\n"
        "   - Nếu câu hỏi hiện tại bị khuyết thành phần (ẩn chủ ngữ, ẩn đối tượng, thiếu phạm vi) "
        "hoặc sử dụng các từ chỉ định/nối tiếp: Hãy trích xuất đúng các thực thể (Entities), mốc thời gian "
        "và điều kiện ràng buộc tương ứng từ [Lịch sử hội thoại] để điền đầy đủ vào câu hỏi mới.\n\n"
        "2. PHÁT HIỆN CHUYỂN ĐỔI CHỦ ĐỀ & XÓA BỎ DỮ LIỆU CŨ (Topic Shift Handling):\n"
        "   - Nếu câu hỏi hiện tại chủ động đưa ra một Thực thể/Đối tượng trọng tâm MỚI thay thế cho đối tượng cũ: "
        "Hãy tập trung hoàn toàn vào thực thể mới đó và KHÔNG đưa các thực thể cũ từ lịch sử vào câu hỏi mới.\n"
        "   - Nếu câu hỏi hiện tại đã tự thân đầy đủ ngữ cảnh và không phụ thuộc lịch sử: GIỮ NGUYÊN câu hỏi gốc.\n\n"
        "3. BẢO TOÀN Ý ĐỊNH & KHÔNG TỰ BỊA (Intent Preservation):\n"
        "   - Giữ nguyên mục đích truy vấn gốc của người dùng (hỏi điểm số, hỏi danh sách, hỏi nhận xét, so sánh...).\n"
        "   - Tuyệt đối KHÔNG tự thêm bớt các yêu cầu mới hoặc tự đoán các thông tin không có trong lịch sử hay câu hỏi gốc.\n\n"
        "ĐẦU RA: Trả về DUY NHẤT một câu hỏi đã tinh chỉnh. Không kèm lời giải thích hay định dạng thừa."
    )

    try:
        result = await llm.ainvoke([
            SystemMessage(content=prompt),
            HumanMessage(content=(
                f"[LỊCH SỬ CHAT (2 TURN GẦN NHẤT)]:\n{recent_history}\n\n"
                f"[CÂU HỎI HIỆN TẠI]: {current_query}\n\n"
                f"Hãy viết lại [CÂU HỎI HIỆN TẠI] thành Standalone Query:"
            ))
        ])
        standalone = (result.content or "").strip()
        return standalone if standalone else current_query
    except Exception as e:
        logger.warning(f"Contextualizer failed, using original query: {e}")
        return current_query


def _get_sliding_window(messages_list: list, max_turns: int = 3) -> list:
    """Lấy max_turns turn gần nhất, bảo toàn Message Object structure."""
    human_indices = []
    for idx, msg in enumerate(messages_list):
        if getattr(msg, "type", None) == "human" or msg.__class__.__name__ in ("HumanMessage", "HumanMessageChunk"):
            human_indices.append(idx)

    if len(human_indices) > max_turns:
        start_idx = human_indices[-max_turns]
    else:
        start_idx = 0

    return messages_list[start_idx:]


def _messages_to_text(messages: list) -> str:
    """Chuyển messages thành text an toàn (giữ được content, skip tool call chi tiết)."""
    lines = []
    for msg in messages:
        msg_type = getattr(msg, "type", "unknown")
        content = str(getattr(msg, "content", "") or "")
        if content.strip():
            role_label = {"human": "Người dùng", "ai": "AI", "tool": "Công cụ"}.get(msg_type, msg_type)
            lines.append(f"{role_label}: {content}")
    return "\n".join(lines)


# ── Helper Functions for Boundary Separation ────────────────────────────────


def _find_last_human_idx(messages_list: list) -> int:
    """Tìm index của HumanMessage cuối cùng trong messages_list."""
    for idx in range(len(messages_list) - 1, -1, -1):
        msg = messages_list[idx]
        if getattr(msg, "type", None) == "human" or msg.__class__.__name__ in ("HumanMessage", "HumanMessageChunk"):
            return idx
        if isinstance(msg, dict) and (msg.get("type") == "human" or msg.get("role") in ("user", "human")):
            return idx
        if getattr(msg, "role", None) in ("user", "human"):
            return idx
    return -1


def _is_non_supervisor_ai_message(msg) -> bool:
    """Check if message is from a sub-agent (not supervisor instruction)."""
    is_ai = (
        getattr(msg, "type", None) == "ai"
        or msg.__class__.__name__ in ("AIMessage", "AIMessageChunk")
        or (isinstance(msg, dict) and (msg.get("type") == "ai" or msg.get("role") in ("assistant", "ai")))
    )
    if not is_ai:
        return False
    content = str(getattr(msg, "content", "") or "")
    if "Chuyển yêu cầu sang" in content or "[Supervisor]:" in content:
        return False
    return True


def _collect_current_turn_answers(current_turn_messages: list) -> list[str]:
    """Lấy tất cả sub-agent responses từ current_turn_messages."""
    answers = []
    for msg in current_turn_messages:
        if _is_non_supervisor_ai_message(msg):
            content = str(getattr(msg, "content", "") or "").strip()
            if content:
                answers.append(content)
    return answers


# ── Supervisor Node ─────────────────────────────────────────────────────────


async def supervisor_node(state: MultiAgentState) -> dict:
    """Supervisor điều phối cuộc hội thoại và phân bổ công việc."""
    # Đồng bộ ContextVars
    school_ctx = state.get("school_context", {})
    if school_ctx:
        if school_ctx.get("school_id"):
            current_user_school_id.set(school_ctx.get("school_id"))
        if school_ctx.get("role"):
            current_user_role.set(school_ctx.get("role"))
        if school_ctx.get("user_id"):
            current_user_id.set(school_ctx.get("user_id"))

    # ── Bước 1: Lấy messages và query ──
    messages_list = state.get("messages", [])
    query = state.get("query", "")

    # Khởi tạo tin nhắn HumanMessage đầu tiên nếu lịch sử rỗng
    has_initial_message = len(messages_list) > 0
    if not has_initial_message and query:
        messages_list = [HumanMessage(content=query)]

    # ── Bước 2: Boundary Separation ──
    last_human_idx = _find_last_human_idx(messages_list)
    if last_human_idx > 0:
        past_messages = messages_list[:last_human_idx]
    else:
        past_messages = []
    if last_human_idx != -1:
        current_turn_messages = messages_list[last_human_idx + 1:]
    else:
        current_turn_messages = []

    # ── Bước 3: Standalone Query với Caching ──
    standalone_query = state.get("standalone_query")
    if not standalone_query:
        standalone_query = await _reformulate_standalone_query(past_messages, query)
    logger.info(
        "supervisor_standalone_query",
        original=query,
        standalone=standalone_query,
        cached=state.get("standalone_query") is not None,
    )

    # ── Lấy thông tin học kỳ hiện tại từ DB để bổ sung ngữ cảnh năm học/học kỳ ──
    current_year_str = "2025-2026"
    current_semester_str = "HK2"
    try:
        from sqlalchemy import text

        from src.db.session import SessionLocal
        with SessionLocal() as db_session:
            row = db_session.execute(text("""
                SELECT fullname FROM s360.dim_school_year ORDER BY id DESC LIMIT 1
            """)).first()
            if row and row[0]:
                current_year_str = row[0]
    except Exception as e:
        logger.warning(f"Note: using default academic year context ({current_year_str}): {e}")

    # ── Bước 4: Build SystemPrompt với 2 XML tags riêng biệt ──
    system_prompt = SUPERVISOR_PROMPT + (
        f"\n\nTHÔNG TIN NGỮ CẢNH HỆ THỐNG HIỆN TẠI:\n"
        f"- Niên khóa hiện tại: {current_year_str}\n"
        f"- Học kỳ hiện tại: {current_semester_str}\n"
        f"- Câu hỏi hiện tại (sau reformulate): {standalone_query}\n"
        f"Nếu người dùng hỏi về điểm số, báo cáo, hay đề thi của học kỳ hiện tại hoặc không chỉ định rõ niên khóa/năm học, "
        f"hãy tự động sử dụng thông tin niên khóa và học kỳ hiện tại này làm mặc định để phân tích/lập báo cáo."
    )

    # 4a: <conversation_history_FOR_REFERENCE_ONLY> — CHỈ past_messages (các lượt TRƯỚC)
    if past_messages:
        past_text = _messages_to_text(past_messages)
        system_prompt += (
            f"\n\n<conversation_history_FOR_REFERENCE_ONLY>\n"
            f"{past_text}\n"
            f"</conversation_history_FOR_REFERENCE_ONLY>"
        )

    # 4b: <current_turn_collected_data> — dữ liệu sub-agent trong lượt HIỆN TẠI
    if current_turn_messages:
        current_turn_text = _messages_to_text(current_turn_messages)
        system_prompt += (
            f"\n\n<current_turn_collected_data>\n"
            f"{current_turn_text}\n"
            f"</current_turn_collected_data>\n\n"
            f"HƯỚNG DẪN ĐÁNH GIÁ <current_turn_collected_data>:\n"
            f"- Đây là dữ liệu MỚI NHẤT mà các Sub-Agent vừa thu thập được trong lượt xử lý HIỆN TẠI.\n"
            f"\n"
            f"- ĐÁNH GIÁ SỰ ĐẦY ĐỦ (SUFFICIENCY ASSESSMENT):\n"
            f"  * Dữ liệu đã ĐỦ để trả lời câu hỏi gốc (có số liệu, bảng kết quả, câu trả lời cụ thể) "
            f"-> BẮT BUỘC chọn FINISH để tổng hợp.\n"
            f"  * Dữ liệu MỚI CHỈ ĐỦ 1 PHẦN -> Tiếp tục gọi Sub-Agent với instruction MỚI CHỈ RÕ phần dữ liệu còn thiếu. "
            f"Tuyệt đối KHÔNG yêu cầu lấy lại phần dữ liệu đã thu thập.\n"
            f"\n"
            f"- ĐÁNH GIÁ PHÂN QUYỀN (ACCESS_DENIED HANDLING):\n"
            f"  * Nếu Sub-Agent phản hồi chứa 'ACCESS_DENIED' hoặc 'nằm ngoài phạm vi phân quyền' "
            f"-> ĐÂY LÀ VẤN ĐỀ QUYỀN TRUY CẬP, KHÔNG phải 'không có dữ liệu'.\n"
            f"  * BẮT BUỘC chọn FINISH để phản hồi lịch sự theo RBAC Security Guardrail.\n"
            f"  * TUYỆT ĐỐI KHÔNG thử lại, KHÔNG sinh instruction truy vấn khác, KHÔNG khuyến nghị nhập liệu.\n"
            f"\n"
            f"- ĐÁNH GIÁ KHI KHÔNG CÓ DỮ LIỆU (NO DATA HANDLING):\n"
            f"  * Nếu Sub-Agent phản hồi 'Không tìm thấy...', 'Dữ liệu trống', 'Không có học sinh/lớp học này' "
            f"-> BẮT BUỘC chọn FINISH để phản hồi lịch sự cho người dùng.\n"
            f"  * TUYỆT ĐỐI KHÔNG thử lại hoặc sinh instruction truy vấn thông tin này nữa.\n"
            f"\n"
            f"- NGUYÊN TẮC CHỐNG LẶP (NO DUPLICATE INSTRUCTION):\n"
            f"  * Đọc lại toàn bộ các [Supervisor] instruction đã phát ra trong lượt hiện tại "
            f"(các dòng có chứa 'Chuyển yêu cầu sang').\n"
            f"  * TUYỆT ĐỐI KHÔNG tạo ra một instruction có nội dung hoặc mục tiêu trùng lặp "
            f"với bất kỳ lệnh nào đã phát ra trước đó."
        )

    # Tách user query (đã reformulate) sang HumanMessage riêng
    user_message = HumanMessage(
        content=f"<current_user_query>\n{standalone_query}\n</current_user_query>"
    )

    messages = [SystemMessage(content=system_prompt), user_message]

    llm = get_llm()
    from src.config import get_settings

    settings = get_settings()

    if settings.llm_provider == "deepseek":
        # DeepSeek không hỗ trợ response_format loại json_schema/function_calling của with_structured_output.
        llm_with_tools = llm.bind_tools([RouterDecision], tool_choice="RouterDecision")
        res = await llm_with_tools.ainvoke(messages)

        # Log raw reasoning content của supervisor LLM trước khi extract decision
        if res.content:
            logger.info("supervisor_reasoning", provider="deepseek", reasoning=res.content[:2000] if len(str(res.content)) > 2000 else res.content)
        if res.tool_calls:
            logger.info("supervisor_tool_calls", tool_calls=res.tool_calls)

        if res.tool_calls:
            try:
                tool_call = res.tool_calls[0]
                decision = RouterDecision(**tool_call["args"])
            except Exception:
                decision = None
        else:
            decision = None

        if decision is None:
            # Fallback nếu model không trả về tool_call
            import json

            text_content = res.content or ""
            decision = None

            json_match = re.search(r"\{.*\}", text_content, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group(0))
                    normalized_data = {}
                    for k, v in data.items():
                        if k.lower() == "next_agent" or "agent" in k.lower():
                            normalized_data["next_agent"] = v
                        elif k.lower() == "instruction" or "instruct" in k.lower():
                            normalized_data["instruction"] = v
                        elif k.lower() == "response" or "response" in k.lower() or "answer" in k.lower():
                            normalized_data["response"] = v

                    next_agent = normalized_data.get("next_agent")
                    instruction = normalized_data.get("instruction")

                    if not next_agent and ("report_type" in data or "grade_level" in data):
                        next_agent = "report_agent"
                        instruction = f"Lập báo cáo {data.get('report_type', 'academic_conduct')} cho khối {data.get('grade_level', 'all')}"

                    next_agent = next_agent or "FINISH"
                    valid_agents = [
                        "data_agent",
                        "stat_agent",
                        "sql_agent",
                        "knowledge_agent",
                        "report_agent",
                        "FINISH",
                        "CLARIFICATION",
                    ]
                    if next_agent not in valid_agents:
                        for va in valid_agents:
                            if va in str(next_agent).lower():
                                next_agent = va
                                break
                        else:
                            next_agent = "FINISH"

                    decision = RouterDecision(
                        next_agent=next_agent,
                        instruction=instruction or "Tổng hợp câu trả lời.",
                        response=normalized_data.get("response"),
                    )
                except Exception:
                    pass

            if not decision:
                next_agent = "FINISH"
                if "data_agent" in text_content:
                    next_agent = "data_agent"
                elif "stat_agent" in text_content:
                    next_agent = "stat_agent"
                elif "sql_agent" in text_content:
                    next_agent = "sql_agent"
                elif "knowledge_agent" in text_content:
                    next_agent = "knowledge_agent"
                elif "report_agent" in text_content:
                    next_agent = "report_agent"

                decision = RouterDecision(
                    next_agent=next_agent,
                    instruction="Tiến hành xử lý yêu cầu." if next_agent != "FINISH" else "Tổng hợp câu trả lời.",
                )
    else:
        # Đối với OpenAI/ChatGPT, sử dụng cơ chế structured output gốc
        structured_llm = llm.with_structured_output(RouterDecision)
        decision = await structured_llm.ainvoke(messages)

    logger.info("supervisor_routing", next_agent=decision.next_agent, instruction=decision.instruction)

    # ── Anti-Loop Guardrail: Circuit Breaker Only ──
    # LLM (Prompt Instruction) đảm nhiệm đánh giá đủ/thiếu/không có dữ liệu
    # Code chỉ đếm số lượt route để ngắt mạch nếu Supervisor kẹt loop
    max_sub_agent_turns = 4
    current_turn_sub_calls = sum(
        1 for msg in current_turn_messages
        if "Chuyển yêu cầu sang" in str(getattr(msg, "content", "") or "")
    )

    if decision.next_agent != "FINISH" and current_turn_sub_calls >= max_sub_agent_turns:
        logger.warning(
            "supervisor_anti_loop",
            msg=f"Reached max_sub_agent_turns ({max_sub_agent_turns}). "
                f"Forcing FINISH as safety circuit breaker. "
                f"next_agent was '{decision.next_agent}', instruction='{decision.instruction}'",
        )
        decision.next_agent = "FINISH"

    updates = {"next_agent": decision.next_agent, "standalone_query": standalone_query}

    if decision.next_agent == "CLARIFICATION":
        response_content = (decision.response or "").strip()
        if not response_content:
            response_content = "Xin lỗi, tôi chưa hiểu rõ yêu cầu. Thầy/cô vui lòng cung cấp thêm thông tin về năm học, học kỳ, hoặc lớp học cụ thể cần phân tích."

        updates["response"] = response_content

        ai_msg = AIMessage(content=response_content)
        if not has_initial_message and query:
            updates["messages"] = [HumanMessage(content=query), ai_msg]
        else:
            updates["messages"] = [ai_msg]

        return updates

    if decision.next_agent == "FINISH":
        # Sử dụng pre-computed current_turn_messages từ Boundary Separation ở trên
        has_file = False
        for msg in current_turn_messages:
            content_str = ""
            if isinstance(msg, dict):
                content_str = str(msg.get("content", ""))
            else:
                content_str = str(getattr(msg, "content", "") or "")
            if "/reports/download/" in content_str:
                has_file = True
                break

        sub_agent_responses = _collect_current_turn_answers(current_turn_messages)

        if has_file:
            response_content = (
                "Tôi đã khởi tạo thành công báo cáo theo yêu cầu của bạn. Dưới đây là tệp báo cáo chi tiết:"
            )
        elif not sub_agent_responses and getattr(decision, "response", None) and decision.response.strip():
            response_content = decision.response.strip()
        else:
            use_direct = False
            if len(sub_agent_responses) == 1:
                first_resp = sub_agent_responses[0]
                if "|" in first_resp or "/download/" in first_resp or "/reports/download/" in first_resp:
                    is_raw_json = (first_resp.strip().startswith("[") and first_resp.strip().endswith("]")) or (
                        first_resp.strip().startswith("{") and first_resp.strip().endswith("}")
                    )
                    if not is_raw_json:
                        use_direct = True

            if use_direct:
                response_content = sub_agent_responses[0]
            else:
                # Synthesis: chỉ dùng current_turn_messages, KHÔNG dùng toàn bộ messages_list
                synthesis_prompt = """Bạn là trợ lý AI chuyên nghiệp phân tích dữ liệu học vụ của nhà trường.
Nhiệm vụ của bạn là tổng hợp toàn bộ dữ liệu, kết quả tính toán, bảng biểu và phân tích thu được từ các Sub-Agent trong lịch sử hội thoại để trả lời người dùng.

LƯU Ý QUAN TRỌNG:
1. Người dùng CHƯA nhìn thấy các tin nhắn hoặc kết quả thô của các Sub-Agent. Bạn BẮT BUỘC phải đưa đầy đủ các số liệu, bảng kết quả (sử dụng định dạng bảng Markdown đẹp mắt), nhận xét và phân tích chi tiết vào câu trả lời cuối cùng này. Tuyệt đối không được bỏ sót dữ liệu hoặc trả lời chung chung.
2. Nếu trong các tin nhắn của Sub-Agent có chứa các đường liên kết tải xuống (ví dụ: các định dạng Markdown như `[Tải Báo Cáo Tại Đây](http://...)` hoặc các URL), bạn BẮT BUỘC phải giữ nguyên văn và in các đường liên kết này ở vị trí thích hợp hoặc ở cuối câu trả lời của bạn. Không được lược bỏ, và không được nói chung chung 'đã cung cấp đường link' mà không hiển thị link cụ thể.
3. Trình bày câu trả lời một cách chuyên nghiệp, thân thiện, có cấu trúc rõ ràng bằng tiếng Việt cho người dùng (thầy/cô).
4. Không nhắc đến tên của các Agent kỹ thuật (như "Data Agent", "Stat Agent", "Pandas Agent", "Supervisor") trong câu trả lời cuối cùng.
5. Tuyệt đối KHÔNG sao chép tin nhắn chuyển giao nhiệm vụ của Supervisor (ví dụ: '[Supervisor]: Chuyển yêu cầu sang...'). Bạn phải tự sinh văn bản trả lời tổng hợp và trình bày các dữ liệu thực tế thu được từ các Sub-Agent dưới dạng bảng và phân tích của riêng bạn.
6. Nếu dữ liệu thu được bị trống hoặc không tìm thấy, hãy thông báo lịch sự cho người dùng rằng không tìm thấy dữ liệu phù hợp trong hệ thống cho yêu cầu này, tuyệt đối không lặp lại tin nhắn chuyển tiếp của Supervisor. QUAN TRỌNG: Nếu dữ liệu/Sub-Agent báo chứa 'ACCESS_DENIED' hoặc 'nằm ngoài phạm vi phân quyền', hãy trả lời một cách ĐƠN GIẢN, TỰ NHIÊN như "Tài khoản của bạn không có quyền truy cập nội dung này" — KHÔNG nói "không có dữ liệu", KHÔNG khuyến nghị nhập liệu, KHÔNG đề nghị liên hệ Ban Giám Hiệu, KHÔNG nhắc đến tên bảng/biến/ID nội bộ (như grade_id, homeroom_class_id, subject_class_pairs).
7. Tuyệt đối KHÔNG sử dụng bất kỳ biểu tượng cảm xúc (emoji/icon) nào như 📊, 🎯, 📌, ⚠️, 🔴, 🟢, 🏆, 📈, 📉, 🥇... trong toàn bộ văn bản phản hồi. Hãy trình bày văn bản trang trọng, học thuật thuần túy chỉ dùng các yếu tố markdown chuẩn (in đậm, danh sách, bảng) thay thế cho emoji.
8. LỌC CỘT ĐIỂM: Nếu người dùng hỏi một kỳ thi/cột điểm cụ thể (như: "giữa kỳ 2", "giữa kỳ 1", "GK2", "GK1"), hãy đảm bảo chỉ tổng hợp thông tin, bảng biểu và phân tích của đúng cột điểm đó (ví dụ giữa kỳ 2 -> column_index = 2). Không hiển thị cột điểm khác của kỳ thi khác để tránh gây loãng thông tin. Phải phân biệt rõ "Học kỳ 2" (kỳ học) và "Giữa kỳ 2" (cột điểm column_index=2 của kỳ học đó). Khi hỏi "giữa kỳ 2 năm 2025-2026", tức là cột điểm Giữa kỳ 2 (column_index=2) của Học kỳ 2 (semester=2).
"""
                # Format conversation history — CHỈ dùng current_turn_messages (tránh context leak)
                transcript_parts = []
                for msg in current_turn_messages:
                    msg_type = getattr(msg, "type", "")
                    role_name = "Người dùng" if msg_type == "human" else "Hệ thống"

                    content_val = getattr(msg, "content", "")
                    if not content_val:
                        continue
                    content_str = str(content_val).strip()

                    if msg_type == "ai":
                        msg_name = getattr(msg, "name", None)
                        if not msg_name and hasattr(msg, "additional_kwargs"):
                            msg_name = msg.additional_kwargs.get("name")

                        if msg_name == "supervisor" or content_str.startswith("[Supervisor]: Chuyển yêu cầu sang"):
                            continue
                        role_name = "Trợ lý Phân tích"
                    elif msg_type == "tool":
                        continue

                    content_str = re.sub(r"<\|\|DSML\|\|[^>]*>", "", content_str)
                    content_str = content_str.strip()
                    if content_str:
                        transcript_parts.append(f"### {role_name}:\n{content_str}")

                transcript_text = "\n\n".join(transcript_parts)

                synthesis_input = f"""Dưới đây là lịch sử thông tin và dữ liệu thu thập được từ hệ thống:

{transcript_text}

Hãy tổng hợp toàn bộ thông tin trên để trả lời câu hỏi gốc của người dùng:
"{standalone_query}"
"""

                logger.info("supervisor_synthesis_debug", sub_agent_responses_count=len(sub_agent_responses), transcript_text=transcript_text, synthesis_input=synthesis_input)
                print(f"\n================ [SUPERVISOR SYNTHESIS DEBUG] ================\n[sub_agent_responses_count]: {len(sub_agent_responses)}\n[synthesis_input]:\n{synthesis_input}\n==============================================================\n")

                synthesis_messages = [SystemMessage(content=synthesis_prompt), HumanMessage(content=synthesis_input)]

                final_response = await llm.ainvoke(synthesis_messages, config={"tags": ["final_synthesis"]})

                response_content = final_response.content or ""
                is_repetition = "[Supervisor]:" in response_content or "Chuyển yêu cầu sang" in response_content

                has_table_in_sub = any("|" in r for r in sub_agent_responses)
                has_table_in_syn = "|" in response_content

                if (
                    not response_content.strip()
                    or is_repetition
                    or len(response_content.strip()) < 50
                    or (has_table_in_sub and not has_table_in_syn)
                ):
                    if sub_agent_responses:
                        response_content = sub_agent_responses[-1]

        download_links = []
        for msg in current_turn_messages:
            content_str = ""
            if isinstance(msg, dict):
                content_str = str(msg.get("content", ""))
            elif hasattr(msg, "content"):
                content_str = str(msg.content)
            if content_str:
                links_found = re.findall(r"(\[([^\]]+)\]\((https?://[^\s)]+/download/[^\s)]+)\))", content_str)
                for full_link, link_text, url in links_found:
                    if url not in response_content:
                        download_links.append((full_link, url))
                urls_found = re.findall(r"(https?://[^\s)]+/download/[a-zA-Z0-9_\-\.]+)", content_str)
                for url in urls_found:
                    if url not in response_content:
                        if not any(url == dl[1] for dl in download_links):
                            download_links.append((f"[Tải Báo Cáo Tại Đây]({url})", url))

        if download_links:
            append_text = "\n\n### Đường liên kết tải báo cáo:\n"
            for full_link, url in download_links:
                if full_link not in append_text:
                    append_text += f"- {full_link}\n"
            response_content = response_content.strip() + append_text

        updates["response"] = response_content
        if not has_initial_message and query:
            ai_msg = AIMessage(content=response_content)
            updates["messages"] = [HumanMessage(content=query), ai_msg]
        else:
            ai_msg = AIMessage(content=response_content)
            updates["messages"] = [ai_msg]
    else:
        # Nếu chưa hoàn thành, thêm tin nhắn định hướng từ Supervisor vào luồng để Sub-Agent đọc
        instruction_msg = AIMessage(
            content=f"[Supervisor]: Chuyển yêu cầu sang `{decision.next_agent}`. Nhiệm vụ: {decision.instruction}",
            name="supervisor",
        )
        if not has_initial_message and query:
            updates["messages"] = [HumanMessage(content=query), instruction_msg]
        else:
            updates["messages"] = [instruction_msg]

    return updates

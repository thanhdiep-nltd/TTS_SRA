import re

from langchain_core.messages import AIMessage, SystemMessage
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
1. `data_service_agent`: Chuyên trách TẤT CẢ các tác vụ liên quan đến CSDL. HƯỚNG DẪN ĐỊNH TUYẾN CHI TIẾT:
   - Nếu câu hỏi là tra cứu cá nhân 1 học sinh (họ tên/mã HS) hoặc 1 lớp chủ nhiệm cụ thể (như 7A1, 10A1): Viết instruction chỉ định chiến lược 'FAST_TEMPLATE' (ví dụ: "Dùng FAST_TEMPLATE tra cứu điểm cho học sinh...").
   - Nếu câu hỏi là tra cứu toàn khối lớp (như toàn bộ Khối 10, Khối 6) hoặc phân tích dữ liệu điểm số phức tạp bằng SQL: Viết instruction chỉ định chiến lược 'DYNAMIC_SQL' (ví dụ: "Dùng DYNAMIC_SQL truy vấn điểm cho toàn khối 10...").
2. `stat_agent`: Chuyên trách tính toán thống kê, tìm thủ khoa/học sinh yếu, phân tích xu hướng học tập, so sánh các lớp, tính toán chỉ số GDI, Delta G, Momentum, và phân tích tam giác hóa độ khó đề thi (đối chiếu độ tin cậy điểm số EDI vs độ khó đề thi CDI). ĐẶC BIỆT LƯU Ý: Mọi câu hỏi của người dùng hỏi về "độ khó của đề thi", "đánh giá đề thi", "nhận xét đề thi", hoặc "đề thi khó hay dễ" đều ứng với nghiệp vụ tam giác hóa độ khó đề thi và BẮT BUỘC phải định tuyến sang `stat_agent` (không chuyển sang data_service_agent). Ngoài ra, nếu người dùng hỏi về một lớp học cụ thể (ví dụ: lớp 6A1), hãy suy luận ra khối lớp tương ứng (ví dụ: Khối 6) và điều hướng sang stat_agent vì đề thi và ma trận đề (CDI) được quản lý chung theo khối lớp.
3. `knowledge_agent`: Chuyên trách tra cứu NỘI DUNG KIẾN THỨC trong sách giáo khoa (định nghĩa, công thức, khái niệm, giải thích bài học của các môn Toán, Ngữ Văn, KHTN, Sử-Địa...). Dùng cho câu hỏi về nội dung học thuật, KHÔNG dùng cho điểm số/hồ sơ học sinh.
4. `report_agent`: Chuyên trách tổng hợp số liệu báo cáo, tạo bảng hiển thị xem trước báo cáo thống kê, hoặc cung cấp đường link tải xuống các tệp báo cáo thống kê (Word, HTML/PDF). Hãy gọi agent này khi người dùng yêu cầu xuất báo cáo, tải báo cáo, lập báo cáo, hoặc khi muốn xem số liệu tổng quan của một loại báo cáo cụ thể.
5. `CLARIFICATION`: Chọn trạng thái này khi bạn cần hỏi lại người dùng để làm rõ thông tin thiếu (như thiếu năm học, thiếu học kỳ, mơ hồ lớp học) HOẶC khi câu hỏi chỉ là chào hỏi xã giao bình thường. Bắt buộc viết nội dung phản hồi trực tiếp vào trường `response`.
6. `FINISH`: Chọn trạng thái này KHI VÀ CHỈ KHI bạn đã thu thập đầy đủ thông tin từ các Sub-Agent để tổng hợp trả lời câu hỏi gốc của người dùng.

Quy trình & Quy tắc tối ưu hóa phản hồi:
- Đọc câu hỏi của người dùng và lịch sử đối thoại.
- Tuyệt đối KHÔNG sử dụng bất kỳ biểu tượng cảm xúc (emoji/icon) nào như 📊, 🎯, 📌, ⚠️, 🔴, 🟢, 🏆, 📈, 📉, 🥇... trong toàn bộ văn bản phản hồi. Hãy trình bày văn bản trang trọng, học thuật thuần túy chỉ dùng các yếu tố markdown chuẩn (in đậm, danh sách, bảng) thay thế cho emoji.
- KIỂM TRA ĐẦU VÀO VÀ CHỦ ĐỘNG HỎI LẠI (Active Clarification):
  Trước khi định tuyến sang bất kỳ sub-agent nào, hãy kiểm tra xem yêu cầu của người dùng đã đầy đủ thông tin cốt lõi chưa hoặc có bị mơ hồ không. Nếu thiếu, hãy chọn `next_agent` là 'CLARIFICATION' và đặt câu hỏi làm rõ lịch sự vào trường `response`:
  1. Thiếu Học kỳ khi lập Báo cáo/Thống kê điểm: Nếu người dùng yêu cầu xuất báo cáo/thống kê cho một năm học nhưng không nói rõ học kỳ nào, hãy chọn `next_agent` là 'CLARIFICATION' và đặt câu hỏi làm rõ lịch sự vào trường `response` (ví dụ: "Bạn muốn xuất báo cáo tình hình học tập của cả năm học hay của một học kỳ cụ thể (Học kỳ 1 / Học kỳ 2)?").
  2. THIẾU NĂM HỌC HOẶC MƠ HỒ NĂM HỌC (BẮT BUỘC HỎI LẠI):
     - Cơ sở dữ liệu lưu năm học dưới dạng khoảng (ví dụ: `2024-2025`, `2025-2026`). Nếu người dùng KHÔNG đề cập đến năm học dạng khoảng rõ ràng, HOẶC chỉ nói một năm đơn lẻ (ví dụ: "năm 2025", "năm 2026"), bạn TUYỆT ĐỐI KHÔNG ĐƯỢC TỰ Ý ĐOÁN năm học. Bạn BẮT BUỘC phải chọn `next_agent` là 'CLARIFICATION' và viết câu hỏi làm rõ vào trường `response` để yêu cầu người dùng xác nhận rõ niên khóa dạng khoảng.
     - Ví dụ: Với yêu cầu "Báo cáo chuyên sâu môn Toán lớp 8A1 HK1" (thiếu hoàn toàn năm học) hoặc "Báo cáo năm 2025 môn Toán lớp 8A1 HK1" (chỉ có năm đơn lẻ), bạn BẮT BUỘC phải phản hồi hỏi lại: "Thầy/cô vui lòng cho biết báo cáo của năm học nào (ví dụ: năm học 2024-2025 hay năm học 2025-2026)? Đồng thời bạn muốn xem học kỳ nào (Học kỳ 1, Học kỳ 2) hay cả năm học?"
  3. Mơ hồ Lớp học/Khối học: Nếu người dùng đề cập đến TOÀN BỘ KHỐI LỚP (ví dụ: "toàn bộ Khối 10", "Khối 6"), hãy định tuyến trực tiếp sang `data_service_agent` để truy vấn CSDL. Nếu người dùng chỉ nói chung chung "lớp 10" mà chưa rõ là một lớp cụ thể hay toàn khối, hãy chọn `next_agent` là 'CLARIFICATION' để hỏi người dùng. Khi viết phản hồi CLARIFICATION, tuyệt đối KHÔNG tự ý suy diễn hoặc tuyên bố thiếu dữ liệu khối lớp/môn học khi chưa truy vấn CSDL.
  4. Nếu các thông tin làm rõ đã được người dùng cung cấp trong lịch sử chat kế tiếp, hãy tổng hợp lại và tiến hành định tuyến sang sub-agent tương ứng bình thường.
- Nếu câu hỏi của người dùng là câu hỏi chào hỏi, xã giao, giới thiệu thông thường (ví dụ: "chào bạn", "hãy giới thiệu về bạn", "bạn làm được gì") mà không cần gọi sub-agent để phân tích số liệu: Hãy chọn `next_agent` là 'CLARIFICATION' và viết trực tiếp câu trả lời đầy đủ, thân thiện vào trường `response` của `RouterDecision`.
- Quyết định Sub-Agent tiếp theo cần chạy và đưa ra hướng dẫn cụ thể cho Agent đó nếu là câu hỏi cần phân tích dữ liệu.
- Nếu các thông tin thu thập được đã đủ, hãy chọn `FINISH` để kết thúc đồ thị.

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
"""


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

    # Lấy danh sách tin nhắn hiện tại và query
    messages_list = state.get("messages", [])
    query = state.get("query", "")

    # Khởi tạo tin nhắn HumanMessage đầu tiên nếu lịch sử rỗng
    has_initial_message = len(messages_list) > 0
    if not has_initial_message and query:
        from langchain_core.messages import HumanMessage

        messages_list = [HumanMessage(content=query)]

    # Lấy thông tin học kỳ hiện tại từ DB để bổ sung ngữ cảnh năm học/học kỳ
    current_year_str = "2025-2026"
    current_semester_str = "HK2"
    try:
        from src.db.session import SessionLocal
        from sqlalchemy import text
        with SessionLocal() as db_session:
            row = db_session.execute(text("""
                SELECT fullname FROM s360.dim_school_year ORDER BY id DESC LIMIT 1
            """)).first()
            if row and row[0]:
                current_year_str = row[0]
    except Exception as e:
        logger.warning(f"Note: using default academic year context ({current_year_str}): {e}")

    system_prompt = SUPERVISOR_PROMPT + (
        f"\n\nTHÔNG TIN NGỮ CẢNH HỆ THỐNG HIỆN TẠI:\n"
        f"- Niên khóa hiện tại: {current_year_str}\n"
        f"- Học kỳ hiện tại: {current_semester_str}\n"
        f"Nếu người dùng hỏi về điểm số, báo cáo, hay đề thi của học kỳ hiện tại hoặc không chỉ định rõ niên khóa/năm học, "
        f"hãy tự động sử dụng thông tin niên khóa và học kỳ hiện tại này làm mặc định để phân tích/lập báo cáo."
    )

    llm = get_llm()
    # Chuẩn bị tin nhắn gửi cho supervisor
    messages = [SystemMessage(content=system_prompt)] + messages_list

    from src.config import get_settings

    settings = get_settings()

    if settings.llm_provider == "deepseek":
        # DeepSeek không hỗ trợ response_format loại json_schema/function_calling của with_structured_output.
        # Chúng ta dùng bind_tools và gọi model trực tiếp, ép gọi RouterDecision bằng tool_choice, sau đó trích xuất kết quả thủ công.
        llm_with_tools = llm.bind_tools([RouterDecision], tool_choice="RouterDecision")
        res = await llm_with_tools.ainvoke(messages)

        if res.tool_calls:
            try:
                tool_call = res.tool_calls[0]
                decision = RouterDecision(**tool_call["args"])
            except Exception:
                decision = None
        else:
            decision = None

        if decision is None:
            # Fallback nếu model không trả về tool_call (trả về văn bản thường hoặc thiếu trường)
            import json

            text_content = res.content or ""
            decision = None

            # Thử tìm và phân tích cú pháp JSON trong text_content
            json_match = re.search(r"\{.*\}", text_content, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group(0))
                    # Chuẩn hóa keys phòng trường hợp model tự đặt tên khác hoặc trả về phẳng
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

                    # Nếu trả về flat object không có key next_agent/instruction nhưng có các trường báo cáo
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
        # Đối với OpenAI/ChatGPT, sử dụng cơ chế structured output gốc tin cậy tuyệt đối
        structured_llm = llm.with_structured_output(RouterDecision)
        decision = await structured_llm.ainvoke(messages)

    logger.info("supervisor_routing", next_agent=decision.next_agent, instruction=decision.instruction)

    updates = {"next_agent": decision.next_agent}

    if decision.next_agent == "CLARIFICATION":
        response_content = (decision.response or "").strip()
        if not response_content:
            response_content = "Xin lỗi, tôi chưa hiểu rõ yêu cầu. Thầy/cô vui lòng cung cấp thêm thông tin về năm học, học kỳ, hoặc lớp học cụ thể cần phân tích."

        updates["response"] = response_content

        from langchain_core.messages import AIMessage as LangChainAIMessage
        from langchain_core.messages import HumanMessage

        ai_msg = LangChainAIMessage(content=response_content)
        if not has_initial_message and query:
            updates["messages"] = [HumanMessage(content=query), ai_msg]
        else:
            updates["messages"] = [ai_msg]

        return updates

    if decision.next_agent == "FINISH":
        # Tìm tin nhắn HumanMessage cuối cùng để xác định điểm bắt đầu của lượt hiện tại
        last_human_index = -1
        for idx, msg in enumerate(messages_list):
            is_human = False
            if getattr(msg, "type", None) == "human":
                is_human = True
            elif msg.__class__.__name__ in ("HumanMessage", "HumanMessageChunk"):
                is_human = True
            elif isinstance(msg, dict) and (msg.get("type") == "human" or msg.get("role") in ("user", "human")):
                is_human = True
            elif getattr(msg, "role", None) in ("user", "human"):
                is_human = True

            if is_human:
                last_human_index = idx

        current_turn_messages = messages_list[last_human_index + 1 :] if last_human_index != -1 else messages_list

        # Check if a report file was generated in the current turn
        has_file = False
        for msg in current_turn_messages:
            content_str = ""
            if isinstance(msg, dict):
                content_str = str(msg.get("content", ""))
            else:
                content_str = str(getattr(msg, "content", ""))
            if "/reports/download/" in content_str:
                has_file = True
                break

        # Only find responses from sub-agents appearing AFTER the current turn's Human message
        sub_agent_responses = []
        for msg in current_turn_messages:
            is_ai = False
            if getattr(msg, "type", None) == "ai":
                is_ai = True
            elif msg.__class__.__name__ in ("AIMessage", "AIMessageChunk"):
                is_ai = True
            elif isinstance(msg, dict) and (msg.get("type") == "ai" or msg.get("role") in ("assistant", "ai")):
                is_ai = True
            elif getattr(msg, "role", None) in ("assistant", "ai"):
                is_ai = True

            content_val = None
            if is_ai:
                if isinstance(msg, dict):
                    content_val = msg.get("content")
                else:
                    content_val = getattr(msg, "content", None)

            if is_ai and content_val:
                content_str = str(content_val)
                if "[Supervisor]:" not in content_str and "Chuyển yêu cầu sang" not in content_str:
                    sub_agent_responses.append(content_str)

        if has_file:
            response_content = (
                "Tôi đã khởi tạo thành công báo cáo theo yêu cầu của bạn. Dưới đây là tệp báo cáo chi tiết:"
            )
        # Sử dụng câu trả lời trực tiếp từ Supervisor nếu có (chỉ cho câu hỏi thường, chào hỏi - không gọi sub-agent nào)
        elif not sub_agent_responses and getattr(decision, "response", None) and decision.response.strip():
            response_content = decision.response.strip()
        else:
            # Check if we should use the single sub-agent response directly
            use_direct = False
            if len(sub_agent_responses) == 1:
                first_resp = sub_agent_responses[0]
                # If it already contains a markdown table or a download link, use it directly to avoid lazy synthesis
                if "|" in first_resp or "/download/" in first_resp or "/reports/download/" in first_resp:
                    # Also make sure it is not just raw JSON
                    is_raw_json = (first_resp.strip().startswith("[") and first_resp.strip().endswith("]")) or (
                        first_resp.strip().startswith("{") and first_resp.strip().endswith("}")
                    )
                    if not is_raw_json:
                        use_direct = True

            if use_direct:
                response_content = sub_agent_responses[0]
            else:
                # Khi hoàn thành, gọi LLM một lần nữa để tổng hợp câu trả lời hoàn chỉnh
                synthesis_prompt = """Bạn là trợ lý AI chuyên nghiệp phân tích học vụ cho Ban Giám Hiệu.
Nhiệm vụ của bạn là tổng hợp toàn bộ dữ liệu, kết quả tính toán, bảng biểu và phân tích thu được từ các Sub-Agent trong lịch sử hội thoại để trả lời người dùng.

LƯU Ý QUAN TRỌNG:
1. Người dùng CHƯA nhìn thấy các tin nhắn hoặc kết quả thô của các Sub-Agent. Bạn BẮT BUỘC phải đưa đầy đủ các số liệu, bảng kết quả (sử dụng định dạng bảng Markdown đẹp mắt), nhận xét và phân tích chi tiết vào câu trả lời cuối cùng này. Tuyệt đối không được bỏ sót dữ liệu hoặc trả lời chung chung.
2. Nếu trong các tin nhắn của Sub-Agent có chứa các đường liên kết tải xuống (ví dụ: các định dạng Markdown như `[Tải Báo Cáo Tại Đây](http://...)` hoặc các URL), bạn BẮT BUỘC phải giữ nguyên văn và in các đường liên kết này ở vị trí thích hợp hoặc ở cuối câu trả lời của bạn. Không được lược bỏ, và không được nói chung chung 'đã cung cấp đường link' mà không hiển thị link cụ thể.
3. Trình bày câu trả lời một cách chuyên nghiệp, thân thiện, có cấu trúc rõ ràng bằng tiếng Việt cho Ban Giám Hiệu.
4. Không nhắc đến tên của các Agent kỹ thuật (như "Data Agent", "Stat Agent", "Pandas Agent", "Supervisor") trong câu trả lời cuối cùng.
5. Tuyệt đối KHÔNG sao chép tin nhắn chuyển giao nhiệm vụ của Supervisor (ví dụ: '[Supervisor]: Chuyển yêu cầu sang...'). Bạn phải tự sinh văn bản trả lời tổng hợp và trình bày các dữ liệu thực tế thu được từ các Sub-Agent dưới dạng bảng và phân tích của riêng bạn.
6. Nếu dữ liệu thu được bị trống hoặc không tìm thấy, hãy thông báo lịch sự cho Ban Giám Hiệu rằng không tìm thấy dữ liệu phù hợp trong hệ thống cho yêu cầu này, tuyệt đối không lặp lại tin nhắn chuyển tiếp của Supervisor.
7. Tuyệt đối KHÔNG sử dụng bất kỳ biểu tượng cảm xúc (emoji/icon) nào như 📊, 🎯, 📌, ⚠️, 🔴, 🟢, 🏆, 📈, 📉, 🥇... trong toàn bộ văn bản phản hồi. Hãy trình bày văn bản trang trọng, học thuật thuần túy chỉ dùng các yếu tố markdown chuẩn (in đậm, danh sách, bảng) thay thế cho emoji.
8. ĐỊNH NGHĨA CHỈ SỐ ĐỘ KHÓ (CHỐNG ẢO GIÁC):
   * EDI (Độ khó thực nghiệm): Phản ánh điểm số làm bài thực tế của học sinh (thang đo 0..1). EDI = 1 - (Điểm trung bình / 10). EDI thấp (gần 0) -> đề thi thực tế Dễ (học sinh đạt điểm trung bình cao); EDI cao (gần 1) -> đề thi thực tế Khó (học sinh đạt điểm trung bình thấp).
   * CDI (Độ khó nội dung): Phản ánh độ phức tạp kiến thức/mức độ Bloom theo thiết kế đề thi (thang đo 0..1). CDI thấp (gần 0) -> đề thi thiết kế Dễ (Bloom thấp); CDI cao (gần 1, ví dụ 0.75) -> đề thi thiết kế Khó/Rất khó (Bloom cao). TUYỆT ĐỐI KHÔNG giải thích nhầm lẫn "CDI = 0.75 nghĩa là 75% học sinh đạt". CDI = 0.75 đại diện cho độ khó Bloom trung bình là 4.5/6 (rất phức tạp và rất khó theo thiết kế).
   * Chỉ số phân kỳ D (Divergence): D = EDI - CDI.
     - D <= -0.25: Đề thiết kế khó nhưng học sinh đạt điểm rất cao (EDI thấp) -> Gắn cờ cảnh báo lạm phát điểm / lộ đề (INFLATION_OR_LEAK).
     - D >= 0.25: Đề thiết kế dễ nhưng học sinh đạt điểm rất kém (EDI cao) -> Gắn cờ cảnh báo lỗ hổng học tập (LEARNING_GAP).
     - |D| < 0.25: Kết quả điểm số phản ánh chính xác độ khó thiết kế của đề thi -> Hợp lệ (VALID).
9. LỌC CỘT ĐIỂM: Nếu người dùng hỏi một kỳ thi/cột điểm cụ thể (như: "giữa kỳ 2", "giữa kỳ 1", "GK2", "GK1"), hãy đảm bảo chỉ tổng hợp thông tin, bảng biểu và phân tích của đúng cột điểm đó (ví dụ giữa kỳ 2 -> column_index = 2). Không hiển thị cột điểm khác của kỳ thi khác để tránh gây loãng thông tin. Phải phân biệt rõ "Học kỳ 2" (kỳ học) và "Giữa kỳ 2" (cột điểm column_index=2 của kỳ học đó). Khi hỏi "giữa kỳ 2 năm 2025-2026", tức là cột điểm Giữa kỳ 2 (column_index=2) của Học kỳ 2 (semester=2).
"""
                # Format conversation history as a clean context transcript to prevent leakage/repetition
                transcript_parts = []
                for msg in messages_list:
                    # Determine message role
                    msg_type = getattr(msg, "type", "")
                    role_name = "Người dùng" if msg_type == "human" else "Hệ thống"

                    content_val = getattr(msg, "content", "")
                    if not content_val:
                        continue
                    content_str = str(content_val).strip()

                    if msg_type == "ai":
                        # Skip supervisor routing instructions (identified by name or prefix)
                        msg_name = getattr(msg, "name", None)
                        # Phòng trường hợp name bị đẩy vào additional_kwargs khi serialize/deserialize
                        if not msg_name and hasattr(msg, "additional_kwargs"):
                            msg_name = msg.additional_kwargs.get("name")

                        if msg_name == "supervisor" or content_str.startswith("[Supervisor]: Chuyển yêu cầu sang"):
                            continue
                        role_name = "Trợ lý Phân tích"
                    elif msg_type == "tool":
                        # Skip raw tool outputs to keep context clean and avoid XML/JSON clutter
                        continue

                    # Remove XML tags (like <||DSML||...>) from the content to avoid leaking reasoning tags
                    content_str = re.sub(r"<\|\|DSML\|\|[^>]*>", "", content_str)
                    content_str = content_str.strip()
                    if content_str:
                        transcript_parts.append(f"### {role_name}:\n{content_str}")

                transcript_text = "\n\n".join(transcript_parts)

                synthesis_input = f"""Dưới đây là lịch sử thông tin và dữ liệu thu thập được từ hệ thống:

{transcript_text}

Hãy tổng hợp toàn bộ thông tin trên để trả lời câu hỏi gốc của người dùng:
"{query}"
"""
                from langchain_core.messages import HumanMessage

                synthesis_messages = [SystemMessage(content=synthesis_prompt), HumanMessage(content=synthesis_input)]

                # Gắn tag final_synthesis để hỗ trợ lọc khi stream token
                final_response = await llm.ainvoke(synthesis_messages, config={"tags": ["final_synthesis"]})

                response_content = final_response.content or ""
                is_repetition = "[Supervisor]:" in response_content or "Chuyển yêu cầu sang" in response_content

                # If the synthesized response is too short/lazy, or if it doesn't contain a table when one of the sub-agent responses does
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
                # Find all markdown links with download urls
                links_found = re.findall(r"(\[([^\]]+)\]\((https?://[^\s)]+/download/[^\s)]+)\))", content_str)
                for full_link, link_text, url in links_found:
                    if url not in response_content:
                        download_links.append((full_link, url))
                # Also find raw download URLs just in case
                urls_found = re.findall(r"(https?://[^\s)]+/download/[a-zA-Z0-9_\-\.]+)", content_str)
                for url in urls_found:
                    if url not in response_content:
                        if not any(url == dl[1] for dl in download_links):
                            download_links.append((f"[Tải Báo Cáo Tại Đây]({url})", url))

        if download_links:
            append_text = "\n\n### 📥 Đường liên kết tải báo cáo:\n"
            for full_link, url in download_links:
                if full_link not in append_text:
                    append_text += f"- 👉 {full_link}\n"
            response_content = response_content.strip() + append_text

        updates["response"] = response_content
        if not has_initial_message and query:
            # Tạo tin nhắn AI tương ứng để lưu vào history
            from langchain_core.messages import AIMessage as LangChainAIMessage
            from langchain_core.messages import HumanMessage

            ai_msg = LangChainAIMessage(content=response_content)
            updates["messages"] = [HumanMessage(content=query), ai_msg]
        else:
            from langchain_core.messages import AIMessage as LangChainAIMessage

            ai_msg = LangChainAIMessage(content=response_content)
            updates["messages"] = [ai_msg]
    else:
        # Nếu chưa hoàn thành, thêm tin nhắn định hướng từ Supervisor vào luồng để Sub-Agent đọc
        instruction_msg = AIMessage(
            content=f"[Supervisor]: Chuyển yêu cầu sang `{decision.next_agent}`. Nhiệm vụ: {decision.instruction}",
            name="supervisor",
        )
        if not has_initial_message and query:
            from langchain_core.messages import HumanMessage

            updates["messages"] = [HumanMessage(content=query), instruction_msg]
        else:
            updates["messages"] = [instruction_msg]

    return updates

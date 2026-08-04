import json
import re

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

from src.agents.context import current_user_id, current_user_role, current_user_school_id
from src.agents.data_service_agent.prompts import DATA_SERVICE_AGENT_SQL_PROMPT
from src.agents.data_service_agent.tools import (
    execute_read_only_query,
    get_student_grades,
)
from src.agents.state import MultiAgentState
from src.observability import logger
from src.services.entity_linker import DynamicEntityContext, resolve_entities
from src.services.llm import get_llm

_sql_generator_agent = None


def get_sql_generator_agent():
    global _sql_generator_agent
    if _sql_generator_agent is None:
        tools = [execute_read_only_query]
        _sql_generator_agent = create_react_agent(get_llm(), tools=tools, prompt=DATA_SERVICE_AGENT_SQL_PROMPT)
    return _sql_generator_agent


def get_data_service_agent():
    return get_sql_generator_agent()


from pydantic import BaseModel, Field  # noqa: E402


class FastTemplateDecision(BaseModel):
    selected_tool: str = Field(
        description=(
            "Chọn 'get_student_grades' (nếu tra cứu điểm 1 học sinh — CHỈ dùng khi có student_code), "
            "hoặc 'NONE' (nếu là SĨ SỐ, SO SÁNH, THỐNG KÊ, DANH SÁCH LỚP, hoặc truy vấn phức tạp cần SQL)."
        )
    )
    extracted_param: str | None = Field(
        default=None,
        description=(
            "Chỉ nhập Mã học sinh (vd 'HS125071002'). "
            "TUYỆT ĐỐI KHÔNG nhập tên học sinh. "
            "Nếu câu hỏi không chứa mã số cụ thể, hãy chọn 'NONE' để chuyển sang Dynamic SQL Generator."
        )
    )
    semester: int | None = Field(
        default=None,
        description="Học kỳ (1 hoặc 2). Chỉ điền nếu câu hỏi đề cập rõ học kỳ. Ví dụ: 'học kỳ 1', 'HK1' -> semester=1, 'học kỳ 2', 'HK2' -> semester=2."
    )
    subject: str | None = Field(
        default=None,
        description="Tên môn học cụ thể. Chỉ điền nếu câu hỏi đề cập rõ môn học. Ví dụ: 'Toán học', 'Ngữ văn', 'Âm nhạc', 'Mỹ thuật'."
    )


async def data_service_agent_node(state: MultiAgentState) -> dict:
    """Unified Data Service Agent Node: LLM Fast Router Tầng 1 + Dual-Level Fallback sang Dynamic SQL Generator Tầng 2."""
    # 1. Đồng bộ ContextVars
    school_ctx = state.get("school_context", {})
    if school_ctx:
        if school_ctx.get("school_id"):
            current_user_school_id.set(school_ctx.get("school_id"))
        if school_ctx.get("role"):
            current_user_role.set(school_ctx.get("role"))
        if school_ctx.get("user_id"):
            current_user_id.set(school_ctx.get("user_id"))

    query = state.get("query", "")
    # CONTEXT ISOLATION: Dùng standalone_query từ Supervisor (đã được LLM Contextualizer reformulate)
    # thay vì dùng messages[-1] để tránh context leak từ lịch sử hội thoại.
    standalone_query = state.get("standalone_query", query)
    context_for_agent = standalone_query or query

    # ============================================================
    # 2. ENTITY RESOLUTION + STRATEGIC DECISION (trước Tier 1)
    # ============================================================
    # resolve_entities() chạy 1 lần duy nhất, share cho cả Tier 1 và Tier 2
    # Fail-soft: nếu entity linker lỗi/timeout → dùng context rỗng, hệ thống vẫn hoạt động
    so_school_id = 1
    if school_ctx and school_ctx.get("school_id"):
        try:
            so_school_id = int(school_ctx.get("school_id"))
        except Exception:
            pass

    entity_ctx = DynamicEntityContext()  # fallback mặc định rỗng
    try:
        entity_ctx = resolve_entities(context_for_agent, so_school_id)
    except Exception as e:
        logger.warning(f"[data_service_agent] Entity linker failed-soft: {e} -> tiếp tục với context rỗng")

    # Strategic Decision: có nên chạy Tier 1 không?
    student_code = None
    skip_tier1 = False

    # Identifier Priority Rule: nếu có exact 1 student_code → dùng cho Tier 1
    if len(entity_ctx.students) == 1:
        student_code = entity_ctx.students[0]["code"]
        logger.info(f"[data_service_agent] Entity linker: 1 student resolved -> code={student_code}")
    elif len(entity_ctx.students) > 1:
        codes = [s["code"] for s in entity_ctx.students]
        logger.info(f"[data_service_agent] Entity linker: {len(entity_ctx.students)} students ambiguous {codes} -> skip Tier 1")
        skip_tier1 = True

    # Multi-subject detection: 2+ explicit subjects → skip Tier 1
    # entity_ctx.subjects chỉ chứa subjects từ subject_keywords (những gì user nói rõ)
    # Nếu user nói "bảng điểm" → subject_keywords=[] → 0 subjects → không skip
    n_subjects = len(entity_ctx.subjects)
    if n_subjects >= 2:
        subject_names = [s["name"] for s in entity_ctx.subjects]
        logger.info(f"[data_service_agent] Entity linker: {n_subjects} explicit subjects {subject_names} -> skip Tier 1")
        skip_tier1 = True

    # ============================================================
    # 3. TẦNG 1: Fast LLM Router (chỉ chạy nếu không ambiguous)
    # ============================================================
    template_result = None
    if not skip_tier1:
        try:
            llm = get_llm()
            llm_router = llm.bind_tools([FastTemplateDecision], tool_choice="FastTemplateDecision")

            # Enrich prompt với resolved context (Identifier Priority Rule)
            tier1_context = context_for_agent
            if entity_ctx.formatted_prompt_context:
                tier1_context = f"{entity_ctx.formatted_prompt_context}\n\nYÊU CẦU HIỆN TẠI: {context_for_agent}"

            router_res = await llm_router.ainvoke([
                SystemMessage(content=(
                    "Bạn là Fast Router Tầng 1. Nhiệm vụ của bạn là chọn đúng công cụ Fast Template hoặc chọn 'NONE'.\n"
                    "QUY TẮC BẮT BUỘC:\n"
                    "- Nếu câu hỏi tra cứu điểm 1 học sinh -> chọn 'get_student_grades'.\n"
                    "- Nếu câu hỏi về SĨ SỐ, SO SÁNH, THỐNG KÊ, DANH SÁCH LỚP -> BẮT BUỘC CHỌN 'NONE'.\n"
                    "- Identifier Priority Rule: Nếu đã có student_code chính xác trong phần THÔNG TIN DANH MỤC ở trên, "
                    "hãy dùng student_code đó làm extracted_param (thay vì tên học sinh). Student_code luôn unique, tên có thể trùng.\n"
                    "- Nếu câu hỏi đề cập rõ HỌC KỲ -> điền vào field 'semester'.\n"
                    "- Nếu câu hỏi đề cập rõ MÔN HỌC -> điền vào field 'subject'."
                )),
                HumanMessage(content=tier1_context)
            ])

            decision = None
            if hasattr(router_res, "tool_calls") and router_res.tool_calls:
                try:
                    tc = router_res.tool_calls[0]
                    decision = FastTemplateDecision(**tc["args"])
                except Exception:
                    decision = None

            if decision is None:
                # Fallback parse JSON text
                text_c = getattr(router_res, "content", "") or ""
                j_match = re.search(r"\{.*\}", text_c, re.DOTALL)
                if j_match:
                    try:
                        data = json.loads(j_match.group(0))
                        decision = FastTemplateDecision(
                            selected_tool=data.get("selected_tool", "NONE"),
                            extracted_param=data.get("extracted_param"),
                            semester=data.get("semester"),
                            subject=data.get("subject"),
                        )
                    except Exception:
                        pass

            if decision:
                logger.info(f"[data_service_agent] Tầng 1 Fast Router Decision: tool={decision.selected_tool}, param={decision.extracted_param}, semester={decision.semester}, subject={decision.subject}")

                if decision.selected_tool == "get_student_grades" and (decision.extracted_param or student_code):
                    # Identifier Priority: dùng student_code nếu entity linker đã resolve
                    kwargs = {"student_code": (student_code or decision.extracted_param.strip())}
                    if decision.semester:
                        kwargs["semester"] = decision.semester
                    if decision.subject:
                        kwargs["subject"] = decision.subject
                    logger.info(f"[data_service_agent] Tầng 1: Chạy get_student_grades student_code={kwargs['student_code']} semester={decision.semester} subject={decision.subject}")
                    template_result = get_student_grades.invoke(kwargs)

                if template_result and not template_result.startswith("Không tìm thấy"):
                    # Thành công Tầng 1 -> Trả về ngay
                    ai_msg = AIMessage(content=f"Kết quả tra cứu dữ liệu:\n\n```json\n{template_result}\n```")
                    return {"messages": [ai_msg]}

                if decision.selected_tool != "NONE":
                    logger.info("[data_service_agent] Tầng 1 trả về rỗng/không khớp -> Fallback sang Tầng 2 (Dynamic SQL Generator).")
        except Exception as err:
            logger.warning(f"[data_service_agent] Lỗi Tầng 1 Fast Router ({err}) -> Fallback sang Tầng 2 (Dynamic SQL Generator).")

    # ============================================================
    # 4. TẦNG 2: Dynamic SQL Generator Fallback
    # ============================================================
    # Entity context đã có sẵn từ bước 2 → KHÔNG resolve lại
    logger.info("[data_service_agent] Kích hoạt Hybrid Search (pgvector + pg_trgm) để chuẩn hóa Exact IDs...")

    # CONTEXT ISOLATION: Thay vì truyền toàn bộ messages[] lịch sử,
    # chỉ tạo 1 HumanMessage sạch với standalone_query + entity context.
    # Điều này ngăn hoàn toàn context leak từ các turn trước.
    combined_context = f"[YÊU CẦU ĐỘC LẬP]: {standalone_query}"
    if query and query != standalone_query:
        combined_context += f"\n[YÊU CẦU GỐC]: {query}"

    if entity_ctx.formatted_prompt_context:
        exec_messages = [HumanMessage(content=f"{entity_ctx.formatted_prompt_context}\n\n{combined_context}")]
    else:
        exec_messages = [HumanMessage(content=combined_context)]

    logger.info("[data_service_agent] Thực thi Tầng 2 (Dynamic SQL Generator)...")
    agent_instance = get_sql_generator_agent()
    # Giới hạn vòng lặp ReAct để tránh retry lãng phí (vd: lặp lại "Lỗi thực thi truy vấn SQL")
    result = await agent_instance.ainvoke(
        {"messages": exec_messages}, config={"recursion_limit": 12}
    )

    input_len = 0  # Vì exec_messages là list mới (không phải messages gốc)
    new_messages = result["messages"][input_len:]

    # Đảm bảo new_messages luôn kết thúc bằng một AIMessage chứa văn bản để Supervisor dễ dàng nhận biết
    has_final_ai = False
    if new_messages:
        last_m = new_messages[-1]
        if isinstance(last_m, AIMessage) and last_m.content and not getattr(last_m, "tool_calls", None):
            has_final_ai = True

    if not has_final_ai and new_messages:
        tool_res_str = ""
        for m in reversed(new_messages):
            content_val = getattr(m, "content", "")
            if content_val and (getattr(m, "type", None) == "tool" or m.__class__.__name__ in ("ToolMessage", "ToolMessageChunk")):
                tool_res_str = str(content_val)
                break

        if tool_res_str:
            summary_msg = AIMessage(content=f"Đã hoàn thành truy vấn CSDL. Kết quả dữ liệu nhận được:\n\n```json\n{tool_res_str}\n```")
            new_messages.append(summary_msg)

    return {"messages": new_messages}

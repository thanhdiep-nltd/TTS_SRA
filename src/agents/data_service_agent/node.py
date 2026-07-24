import json
import re

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

from src.agents.context import current_user_id, current_user_role, current_user_school_id
from src.agents.data_service_agent.prompts import DATA_SERVICE_AGENT_SQL_PROMPT
from src.agents.data_service_agent.tools import (
    execute_read_only_query,
    get_class_grades,
    get_student_grades,
    get_student_info,
)
from src.agents.state import MultiAgentState
from src.observability import logger
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


from pydantic import BaseModel, Field


class FastTemplateDecision(BaseModel):
    selected_tool: str = Field(
        description=(
            "Chọn 'get_student_grades' (nếu tra cứu điểm cá nhân 1 học sinh), "
            "'get_class_grades' (nếu tra cứu danh sách bảng điểm/sổ điểm thi của 1 lớp chủ nhiệm cụ thể), "
            "'get_student_info' (nếu tra cứu hồ sơ/thông tin 1 học sinh), "
            "hoặc 'NONE' (nếu là bài toán sĩ số/đếm học sinh, so sánh giữa các lớp/năm, thống kê rủi ro, hoặc truy vấn phức tạp cần viết SQL)."
        )
    )
    extracted_param: str | None = Field(
        default=None,
        description="Mã/họ tên học sinh hoặc mã lớp bóc tách được (ví dụ: '7A1', '10A1', 'HS25071001', 'Bùi Thành Hải')."
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

    messages = state.get("messages", [])
    query = state.get("query", "")
    if not query and messages:
        query = messages[-1].content

    # Lấy thông tin instruction hoặc câu thoại gần nhất từ Supervisor
    last_text = " ".join([m.content for m in messages[-2:] if hasattr(m, "content") and m.content])
    combined_context = f"{query} {last_text}"

    # 2. TẦNG 1: LLM Fast Router Decision (~0.2s với Tool Binding siêu nhẹ)
    template_result = None
    try:
        llm = get_llm()
        llm_router = llm.bind_tools([FastTemplateDecision], tool_choice="FastTemplateDecision")
        router_res = await llm_router.ainvoke([
            SystemMessage(content=(
                "Bạn là Fast Router Tầng 1. Nhiệm vụ của bạn là chọn đúng công cụ Fast Template Tầng 1 hoặc chọn 'NONE'.\n"
                "QUY TẮC BẮT BUỘC:\n"
                "- Nếu câu hỏi tra cứu điểm/hồ sơ cá nhân 1 học sinh -> chọn 'get_student_grades' hoặc 'get_student_info'.\n"
                "- Nếu câu hỏi tra cứu danh sách sổ điểm thi của 1 lớp -> chọn 'get_class_grades'.\n"
                "- CHÚ Ý CỰC KỲ QUAN TRỌNG: Nếu câu hỏi về SĨ SỐ HỌC SINH (ví dụ: 'Lớp 7A1 có bao nhiêu học sinh?'), SO SÁNH NĂM HỌC/LỚP HỌC, THỐNG KÊ RỦI RO -> BẮT BUỘC CHỌN 'NONE'."
            )),
            HumanMessage(content=combined_context)
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
                        extracted_param=data.get("extracted_param")
                    )
                except Exception:
                    pass

        if decision:
            logger.info(f"[data_service_agent] Tầng 1 Fast Router Decision: tool={decision.selected_tool}, param={decision.extracted_param}")

            if decision.selected_tool == "get_class_grades" and decision.extracted_param:
                logger.info(f"[data_service_agent] Tầng 1: Chạy get_class_grades cho lớp {decision.extracted_param}")
                template_result = get_class_grades.invoke({"class_name": decision.extracted_param.strip()})
            elif decision.selected_tool == "get_student_grades" and decision.extracted_param:
                logger.info(f"[data_service_agent] Tầng 1: Chạy get_student_grades cho HS {decision.extracted_param}")
                template_result = get_student_grades.invoke({"student_id": decision.extracted_param.strip()})
            elif decision.selected_tool == "get_student_info" and decision.extracted_param:
                logger.info(f"[data_service_agent] Tầng 1: Chạy get_student_info cho HS {decision.extracted_param}")
                template_result = get_student_info.invoke({"student_id": decision.extracted_param.strip()})

            if template_result and not template_result.startswith("Không tìm thấy"):
                # Thành công Tầng 1 -> Trả về ngay
                ai_msg = AIMessage(content=f"Kết quả tra cứu dữ liệu:\n\n```json\n{template_result}\n```")
                return {"messages": [ai_msg]}

            if decision.selected_tool != "NONE":
                logger.info("[data_service_agent] Tầng 1 trả về rỗng/không khớp -> Fallback Nấc 2 sang Tầng 2 (Dynamic SQL Generator).")
    except Exception as err:
        logger.warning(f"[data_service_agent] Lỗi Tầng 1 Fast Router ({err}) -> Fallback sang Tầng 2 (Dynamic SQL Generator).")

    # 4. TẦNG 2: Dynamic SQL Generator Fallback (Chạy khi Tầng 1 rỗng, lỗi, hoặc tra cứu toàn Khối)
    logger.info("[data_service_agent] Kích hoạt Hybrid Search (pgvector + pg_trgm) để chuẩn hóa Exact IDs...")
    from src.services.entity_linker import resolve_entities

    so_school_id = 1
    if school_ctx and school_ctx.get("school_id"):
        try:
            so_school_id = int(school_ctx.get("school_id"))
        except Exception:
            pass

    entity_ctx = resolve_entities(combined_context, so_school_id)
    exec_messages = list(messages)
    if exec_messages and entity_ctx.formatted_prompt_context:
        last_msg = exec_messages[-1]
        raw_text = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
        new_content = f"{entity_ctx.formatted_prompt_context}\n\n[YÊU CẦU NGƯỜI DÙNG & HƯỚNG DẪN]: {raw_text}"
        exec_messages[-1] = HumanMessage(content=new_content)

    logger.info("[data_service_agent] Thực thi Tầng 2 (Dynamic SQL Generator)...")
    agent_instance = get_sql_generator_agent()
    result = await agent_instance.ainvoke({"messages": exec_messages})

    input_len = len(messages)
    new_messages = result["messages"][input_len:]
    return {"messages": new_messages}

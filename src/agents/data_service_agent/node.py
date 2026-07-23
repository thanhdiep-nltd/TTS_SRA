import json
import re

from langchain_core.messages import AIMessage
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


async def data_service_agent_node(state: MultiAgentState) -> dict:
    """Unified Data Service Agent Node: Supervisor Guidance + Fast 2-Tier Execution (0 extra LLM calls for Tier 1)."""
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

    # 2. Phân loại chiến lược từ Supervisor Guidance & Regex
    is_explicit_dynamic_sql = "DYNAMIC_SQL" in combined_context or bool(
        re.search(r"\b(toàn bộ khối|toàn khối|khối\s+\d+)\b", combined_context, re.IGNORECASE)
    )
    is_fast_template_requested = "FAST_TEMPLATE" in combined_context or bool(
        re.search(r"\b(\d{1,2}[a-zA-Z]\d?|hs\d+)\b", combined_context, re.IGNORECASE)
    )

    template_result = None

    # 3. TẦNG 1: Fast Template Lookup (Code Python thuần - 0 lượt gọi LLM)
    if is_fast_template_requested and not is_explicit_dynamic_sql:
        try:
            # Match mã lớp học cụ thể (vd: 10A1, 7A1, 6A2)
            class_match = re.search(r"\b(\d{1,2}[a-zA-Z]\d?)\b", combined_context)
            # Match mã học sinh (vd: HS25071001)
            student_code_match = re.search(r"\b(HS\d+)\b", combined_context, re.IGNORECASE)

            if class_match:
                class_name = class_match.group(1).upper()
                logger.info(f"[data_service_agent] Tầng 1: Chạy get_class_grades cho lớp {class_name}")
                template_result = get_class_grades.invoke({"class_name": class_name})
            elif student_code_match:
                student_id = student_code_match.group(1).upper()
                logger.info(f"[data_service_agent] Tầng 1: Chạy get_student_grades cho HS {student_id}")
                template_result = get_student_grades.invoke({"student_id": student_id})

            if template_result and not template_result.startswith("Không tìm thấy"):
                # Thành công Tầng 1 -> Trả về ngay (Latency siêu nhanh ~1.5s!)
                ai_msg = AIMessage(content=f"Kết quả tra cứu dữ liệu:\n\n```json\n{template_result}\n```")
                return {"messages": [ai_msg]}

            logger.info("[data_service_agent] Tầng 1 trả về rỗng/không khớp -> Tự động Fallback bằng code Python sang Tầng 2 (Dynamic SQL Generator).")
        except Exception as err:
            logger.warning(f"[data_service_agent] Lỗi thực thi Tầng 1 ({err}) -> Chuyển sang Tầng 2 (Dynamic SQL Generator).")

    # 4. TẦNG 2: Dynamic SQL Generator Fallback (Chạy khi Tầng 1 rỗng, lỗi, hoặc tra cứu toàn Khối)
    logger.info("[data_service_agent] Kích hoạt Hybrid Search (pgvector + pg_trgm) để chuẩn hóa Exact IDs...")
    from langchain_core.messages import HumanMessage
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

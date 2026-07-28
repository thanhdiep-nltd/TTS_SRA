import asyncio
import json
import time
from datetime import UTC
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from src.agents.context import current_user_role, current_user_school_id
from src.agents.graph import agent
from src.api.deps import CurrentUser, get_db
from src.models import enums
from src.models.schemas import (
    AiMessageResponse,
    AiSessionAttachmentResponse,
    AiSessionResponse,
    AiSessionUpdate,
    AiTelemetryStatsResponse,
    ChatRequest,
    MessageFeedbackRequest,
    ObservabilityHistoryResponse,
    ObservabilitySummaryResponse,
    SchoolTelemetryResponse,
)
from src.observability import (
    TOOL_AGENT_MAP,
    logger,
    agent_latency_seconds,
    agent_requests_total,
    agent_routes_total,
    agent_step_seconds,
    agent_tokens_total,
    agent_ttft_seconds,
    breakdown_counter,
    classify_response_guardrail,
    cost_per_task,
    get_langfuse_handler,
    histogram_quantile,
    merge_counts_with_snapshot_fallback,
    merge_p95_with_snapshot_fallback,
    sql_guardrail_rejections_total,
    sum_counter,
    tool_calls_total,
    tool_latency_seconds,
)
from src.repositories import chat_repo
from src.services import chat_attachments, storage
from src.services.alerting import (
    check_agent_runaway,
    get_recent_alerts,
    get_recent_eval_avg,
    get_recent_faithfulness_avg,
    track_cost,
    track_request_result,
)
from src.services.eval import judge_faithfulness, judge_groundedness, should_sample
from src.services.observability_snapshot import capture_snapshot

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.get("/sessions", response_model=list[AiSessionResponse])
def get_sessions(user: CurrentUser, db: Session = Depends(get_db)):
    """Lấy danh sách các phiên chat đang hoạt động của người dùng."""
    return chat_repo.get_active_sessions(db, user.id)


@router.post("/sessions", response_model=AiSessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(user: CurrentUser, db: Session = Depends(get_db)):
    """Tạo trước 1 phiên chat trống (chưa có tin nhắn) — dùng khi người dùng đính kèm file
    trước khi gửi câu hỏi đầu tiên."""
    return chat_repo.create_session(db, user_id=user.id, title=None)


def _build_attachment_block(db: Session, session_id: UUID) -> str | None:
    """Ghép nội dung trích xuất của mọi file đính kèm trong session thành 1 khối văn bản
    để chèn làm SystemMessage. None nếu session chưa có file đính kèm nào."""
    attachments = chat_repo.get_session_attachments(db, session_id)
    if not attachments:
        return None
    blocks = []
    for a in attachments:
        note = " (đã cắt ngắn)" if a.truncated else ""
        blocks.append(f"[Tệp đính kèm: {a.file_name}{note}]\n{a.extracted_text or '(không trích xuất được nội dung)'}")
    return (
        "Người dùng đã đính kèm (các) file sau trong phiên chat này. Hãy dùng nội dung này để "
        "trả lời khi câu hỏi liên quan:\n\n" + "\n\n---\n\n".join(blocks)
    )


def _check_session_ownership(db: Session, session_id: UUID, user_id: int):
    session = chat_repo.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phiên chat")
    if session.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền truy cập phiên chat này",
        )
    return session


@router.post(
    "/sessions/{session_id}/attachments",
    response_model=AiSessionAttachmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_attachment(
    session_id: UUID,
    user: CurrentUser,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Đính kèm file (PDF/DOC/DOCX/ảnh) vào phiên chat để AI đọc nội dung. Nội dung trích xuất
    được chèn vào MỌI lượt hỏi tiếp theo trong cùng session (xem hàm `_build_attachment_block`)."""
    _check_session_ownership(db, session_id, user.id)

    from src.config import get_settings

    settings = get_settings()
    if chat_repo.count_attachments(db, session_id) >= settings.chat_attachment_max_files_per_session:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Mỗi phiên chat tối đa {settings.chat_attachment_max_files_per_session} file đính kèm.",
        )

    try:
        stored, _size, file_type = storage.save_chat_attachment(file)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    raw_text = chat_attachments.extract_attachment_text(storage.chat_attachment_path(stored), file_type)
    text, truncated = chat_attachments.truncate_for_prompt(raw_text, settings.chat_attachment_max_chars)

    return chat_repo.create_attachment(
        db,
        session_id=session_id,
        uploaded_by=user.id,
        file_name=file.filename or stored,
        stored_name=stored,
        file_type=file_type,
        extracted_text=text,
        char_count=len(raw_text),
        truncated=truncated,
    )


@router.get("/sessions/{session_id}/attachments", response_model=list[AiSessionAttachmentResponse])
def list_attachments(session_id: UUID, user: CurrentUser, db: Session = Depends(get_db)):
    """Lấy danh sách file đã đính kèm trong phiên chat (để hiển thị lại khi mở lại session)."""
    _check_session_ownership(db, session_id, user.id)
    return chat_repo.get_session_attachments(db, session_id)


@router.delete("/sessions/{session_id}/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attachment(session_id: UUID, attachment_id: int, user: CurrentUser, db: Session = Depends(get_db)):
    """Xoá 1 file đính kèm khỏi phiên chat (không còn được chèn vào các lượt hỏi sau)."""
    _check_session_ownership(db, session_id, user.id)
    attachment = chat_repo.get_attachment(db, attachment_id)
    if not attachment or attachment.session_id != session_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy file đính kèm")
    storage.delete_chat_attachment(attachment.stored_name)
    chat_repo.delete_attachment(db, attachment)


@router.get("/sessions/{session_id}/messages", response_model=list[AiMessageResponse])
def get_session_messages(session_id: UUID, user: CurrentUser, db: Session = Depends(get_db)):


    """Lấy lịch sử tin nhắn của một phiên chat cụ thể (yêu cầu sở hữu)."""
    session = chat_repo.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phiên chat")
    if str(session.user_id) != str(user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền truy cập phiên chat này",
        )

    return chat_repo.get_session_messages(db, session_id, limit=20)


@router.patch("/sessions/{session_id}", response_model=AiSessionResponse)
def rename_session(
    session_id: UUID,
    payload: AiSessionUpdate,
    user: CurrentUser,
    db: Session = Depends(get_db),
):
    """Đổi tên tiêu đề của phiên chat (yêu cầu sở hữu)."""
    session = chat_repo.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phiên chat")
    if session.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền chỉnh sửa phiên chat này",
        )

    return chat_repo.update_session_title(db, session, payload.title)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: UUID, user: CurrentUser, db: Session = Depends(get_db)):
    """Ẩn/Xóa mềm một phiên chat (yêu cầu sở hữu)."""
    session = chat_repo.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phiên chat")
    if session.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền xóa phiên chat này",
        )

    chat_repo.soft_delete_session(db, session)


@router.post("")
async def chat(request: ChatRequest, user: CurrentUser, db: Session = Depends(get_db)) -> StreamingResponse:
    """Gửi câu hỏi phân tích đến AI Agent (trả về dưới dạng Streaming SSE và phân quyền trường)."""
    session_id = request.session_id

    # 1. Quản lý/Khởi tạo phiên chat
    if session_id is None:
        title = request.message[:50] + "..." if len(request.message) > 50 else request.message
        session = chat_repo.create_session(db, user_id=user.id, title=title)
        session_id = session.id
    else:
        session = chat_repo.get_session(db, session_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phiên chat")
        if session.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền truy cập phiên chat này",
            )
        if not session.is_active:
            session.is_active = True
            db.commit()

    # 2. Lấy lịch sử chat gửi lên Agent (tối đa 10 tin nhắn gần nhất)
    db_history = chat_repo.get_session_messages(db, session_id, limit=10)
    langchain_messages = []
    for msg in db_history:
        if msg.role == enums.AiSessionRole.user:
            langchain_messages.append(HumanMessage(content=msg.content))
        elif msg.role == enums.AiSessionRole.assistant:
            langchain_messages.append(AIMessage(content=msg.content))

    # Thêm tin nhắn hiện tại của người dùng vào context
    langchain_messages.append(HumanMessage(content=request.message))

    # Chèn nội dung file đính kèm (nếu có) vào ĐẦU danh sách — đọc lại từ DB mỗi lượt
    # (không phụ thuộc cửa sổ lịch sử 10 tin nhắn) để "nhớ" file suốt session.
    attachment_block = _build_attachment_block(db, session_id)
    if attachment_block:
        langchain_messages.insert(0, SystemMessage(content=attachment_block))

    async def event_generator():
        # Đồng bộ ContextVars để các tool tự động nhận diện phạm vi dữ liệu bảo mật
        token_school = current_user_school_id.set(user.so_school_id)
        token_role = current_user_role.set(user.role.value if hasattr(user.role, "value") else str(user.role))

        # Gửi trước session_id để Frontend đồng bộ URL và quản lý session
        yield f"data: {json.dumps({'type': 'session_id', 'content': str(session_id)}, ensure_ascii=False)}\n\n"

        generated_sql = None
        final_response_accumulated = ""
        response_text = ""

        # Telemetry variables
        total_input_tokens = 0
        total_output_tokens = 0
        thought_logs = []
        model_used = "unknown"
        provider = "unknown"
        start_time = time.time()
        first_token_time = None
        tool_start_times: dict[str, float] = {}
        agent_step_start_times: dict[str, float] = {}
        rag_context: str | None = None
        groundedness_context_parts: list[str] = []
        supervisor_step_count = 0
        agent_node_names = {"supervisor", "data_service_agent", "stat_agent", "knowledge_agent", "report_agent"}

        try:
            # Lưu trước tin nhắn của người dùng vào CSDL
            chat_repo.create_message(
                db,
                session_id=session_id,
                role=enums.AiSessionRole.user,
                content=request.message,
            )

            start_time = time.time()

            # 0. Phát log Ngữ cảnh Phân quyền Đa trường (Tenant Scope)
            scope_msg = (
                f"🏫 [Ngữ cảnh Phân quyền]: Trường ID = {user.so_school_id} | "
                f"Vai trò = {user.role.value if hasattr(user.role, 'value') else user.role} | "
                f"User ID = {user.id}"
            )
            thought_logs.append({"type": "thought", "content": scope_msg, "timestamp": time.time()})
            yield f"data: {json.dumps({'type': 'thought', 'content': scope_msg}, ensure_ascii=False)}\n\n"

            # Pre-run Entity Linker trace để log thông tin bóc tách & danh mục chuẩn hóa truyền cho LLM
            try:
                from src.services.entity_linker import resolve_entities, extract_entity_slots_llm
                slots = extract_entity_slots_llm(request.message.strip())
                entity_ctx = resolve_entities(request.message, so_school_id=user.so_school_id)

                slots_msg = (
                    f"🔍 [Entity Linker - Từ khóa Bóc tách từ Câu hỏi]:\n"
                    f"   - Môn học / Chuẩn: {slots.subject_keywords}\n"
                    f"   - Lớp / Khối: {slots.class_keywords}\n"
                    f"   - Học sinh: {slots.student_keywords}\n"
                    f"   - Năm học: {slots.school_year_keywords}\n"
                    f"   - Kỳ thi: {slots.exam_keywords}"
                )
                thought_logs.append({"type": "thought", "content": slots_msg, "timestamp": time.time()})
                yield f"data: {json.dumps({'type': 'thought', 'content': slots_msg}, ensure_ascii=False)}\n\n"

                matched_msg = (
                    f"🔍 [Entity Linker - Thực thể Khớp CSDL PostgreSQL (Trường {user.so_school_id})]:\n"
                    f"   - Năm học IDs: {[y['id'] for y in entity_ctx.school_years]}\n"
                    f"   - Lớp học IDs: {[c['id'] for c in entity_ctx.homeroom_classes]}\n"
                    f"   - Môn học IDs: {[s['id'] for s in entity_ctx.subjects]}\n"
                    f"   - Mã Học sinh: {[st['code'] for st in entity_ctx.students]}\n"
                    f"   - Khối ID suy luận: {entity_ctx.target_grade_id}"
                )
                thought_logs.append({"type": "thought", "content": matched_msg, "timestamp": time.time()})
                yield f"data: {json.dumps({'type': 'thought', 'content': matched_msg}, ensure_ascii=False)}\n\n"

                if entity_ctx.formatted_prompt_context:
                    ctx_msg = (
                        f"📝 [Entity Linker - Prompt Context Chèn Cho LLM]:\n"
                        f"{entity_ctx.formatted_prompt_context}"
                    )
                    thought_logs.append({"type": "thought", "content": ctx_msg, "timestamp": time.time()})
                    yield f"data: {json.dumps({'type': 'thought', 'content': ctx_msg}, ensure_ascii=False)}\n\n"
            except Exception as err:
                logger.warning(f"Entity Linker trace log error: {err}")

            # Langfuse Callback Handler (fail-soft: None nếu chưa cấu hình LANGFUSE_*)
            # SDK v4: session_id/user_id/tags gắn qua metadata["langfuse_*"], không qua constructor.
            langfuse_handler = get_langfuse_handler()
            callbacks = [langfuse_handler] if langfuse_handler else []

            # Chạy LangGraph Agent dưới dạng stream_events
            async for event in agent.astream_events(
                {
                    "query": request.message,
                    "messages": langchain_messages,
                    "school_context": {
                        "school_id": str(user.so_school_id),
                        "role": user.role.value if hasattr(user.role, "value") else str(user.role),
                        "user_id": str(user.id),
                    },
                },
                config={
                    "recursion_limit": 50,
                    "callbacks": callbacks,
                    "metadata": {
                        "langfuse_session_id": str(session_id),
                        "langfuse_user_id": str(user.id),
                        "langfuse_tags": ["chat_session"],
                    },
                },
                version="v2",
            ):
                # 0. Phát thông báo trạng thái xử lý động (status transitions)
                if event["event"] == "on_chain_start":
                    name = event.get("name")
                    if name in agent_node_names:
                        agent_step_start_times[event["run_id"]] = time.time()
                        node_log = f"🔀 [Điều Phối Node]: Kích hoạt Node Agent '{name}'"
                        thought_logs.append({"type": "thought", "content": node_log, "timestamp": time.time()})
                        yield f"data: {json.dumps({'type': 'thought', 'content': node_log}, ensure_ascii=False)}\n\n"

                    status_msg = None
                    if name == "supervisor":
                        supervisor_step_count += 1
                        status_msg = "Đang phân tích yêu cầu của bạn..."
                    elif name == "data_service_agent":
                        status_msg = "Đang truy vấn cơ sở dữ liệu và điểm số..."
                    elif name == "stat_agent":
                        status_msg = "Đang tính toán thống kê và phân tích..."
                    elif name == "report_agent":
                        status_msg = "Đang lập dữ liệu cho báo cáo..."

                    if status_msg:
                        thought_logs.append({"type": "status", "content": status_msg, "timestamp": time.time()})
                        yield f"data: {json.dumps({'type': 'status', 'content': status_msg}, ensure_ascii=False)}\n\n"

                elif event["event"] == "on_tool_start":
                    name = event.get("name")
                    tool_start_times[event["run_id"]] = time.time()
                    status_msg = None
                    if name == "execute_read_only_query":
                        status_msg = "Đang thực thi truy vấn cơ sở dữ liệu..."
                    elif name == "validate_and_secure_sql":
                        status_msg = "Đang xác thực tính an toàn của truy vấn SQL..."

                    if status_msg:
                        thought_logs.append({"type": "status", "content": status_msg, "timestamp": time.time()})
                        yield f"data: {json.dumps({'type': 'status', 'content': status_msg}, ensure_ascii=False)}\n\n"

                # Deterministic reliability check cho data/stat/sql_agent (thay LLM Judge):
                # tỉ lệ thành công + latency của từng tool phản ánh agent có hoạt động đúng không.
                elif event["event"] == "on_tool_error":
                    name = event.get("name", "unknown")
                    duration = time.time() - tool_start_times.pop(event["run_id"], time.time())
                    agent_name = TOOL_AGENT_MAP.get(name, "unknown")
                    tool_latency_seconds.labels(tool_name=name, agent_name=agent_name).observe(duration)
                    tool_calls_total.labels(tool_name=name, agent_name=agent_name, status="error").inc()

                elif event["event"] == "on_chat_model_start":
                    tags = event.get("tags", [])
                    if "final_synthesis" in tags:
                        yield f"data: {json.dumps({'type': 'status', 'content': 'Đang tổng hợp kết quả trả về...'}, ensure_ascii=False)}\n\n"

                # A. Lấy Thought Trace khi model kết thúc hoặc quyết định chạy công cụ
                elif event["event"] == "on_chat_model_end":
                    msg = event["data"]["output"]
                    model_name = getattr(msg, "response_metadata", {}).get("model_name", "LLM") if hasattr(msg, "response_metadata") else "LLM"
                    if getattr(msg, "tool_calls", None):
                        for tc in msg.tool_calls:
                            thought = (
                                f"🤖 [AI Agent - Suy luận] (Model: {model_name}): Quyết định gọi công cụ `{tc['name']}`\n"
                                f"   Tham số: {json.dumps(tc['args'], ensure_ascii=False)}"
                            )
                            thought_logs.append({"type": "thought", "content": thought, "timestamp": time.time()})
                            yield f"data: {json.dumps({'type': 'thought', 'content': thought}, ensure_ascii=False)}\n\n"
                            if tc["name"] == "execute_read_only_query" and "sql_query" in tc["args"]:
                                generated_sql = tc["args"]["sql_query"]
                                guardrail_msg = (
                                    f"🛡️ [SQL Security Guardrail]: Cú pháp hợp lệ. "
                                    f"Đã kiểm duyệt AST & tự động chèn bộ lọc so_school_id = {user.so_school_id} & ép LIMIT 100."
                                )
                                thought_logs.append({"type": "thought", "content": guardrail_msg, "timestamp": time.time()})
                                yield f"data: {json.dumps({'type': 'thought', 'content': guardrail_msg}, ensure_ascii=False)}\n\n"
                    else:
                        tags = event.get("tags", [])
                        if "final_synthesis" not in tags:
                            raw_content = getattr(msg, "content", "") or ""
                            if raw_content.strip():
                                preview = raw_content[:600] + "\n   ..." if len(raw_content) > 600 else raw_content
                                thought = f"🧠 [AI Agent - Phản Hồi Nội Bộ / Suy Luận] (Model: {model_name}):\n   {preview}"
                                thought_logs.append({"type": "thought", "content": thought, "timestamp": time.time()})
                                yield f"data: {json.dumps({'type': 'thought', 'content': thought}, ensure_ascii=False)}\n\n"
                    # Accumulate input and output tokens from all LLMs in the graph run
                    if hasattr(msg, "usage_metadata") and msg.usage_metadata:
                        total_input_tokens += msg.usage_metadata.get("input_tokens", 0)
                        total_output_tokens += msg.usage_metadata.get("output_tokens", 0)

                # B. Lấy kết quả trả về của các công cụ (ToolMessage)
                elif event["event"] == "on_tool_end":
                    tool_name = event.get("name", "unknown")
                    duration = time.time() - tool_start_times.pop(event["run_id"], time.time())
                    agent_name = TOOL_AGENT_MAP.get(tool_name, "unknown")
                    tool_latency_seconds.labels(tool_name=tool_name, agent_name=agent_name).observe(duration)
                    tool_calls_total.labels(tool_name=tool_name, agent_name=agent_name, status="success").inc()

                    tool_output = str(event["data"]["output"])
                    if tool_name == "search_textbook":
                        # Lưu context RAG để chấm Faithfulness sau khi có câu trả lời cuối
                        rag_context = tool_output
                    elif agent_name in ("data_service_agent", "stat_agent", "report_agent"):
                        # Lưu dữ liệu thô để chấm Groundedness
                        groundedness_context_parts.append(f"[{tool_name}]: {tool_output}")

                    content_preview = tool_output[:400] + "\n   ..." if len(tool_output) > 400 else tool_output
                    thought = f"🔧 [Công cụ - Kết quả trả về] (Thời gian: {duration:.2f}s):\n   {content_preview}"
                    thought_logs.append({"type": "thought", "content": thought, "timestamp": time.time()})
                    yield f"data: {json.dumps({'type': 'thought', 'content': thought}, ensure_ascii=False)}\n\n"

                # C. Stream các token của câu trả lời cuối cùng (synthesis)
                elif event["event"] == "on_chat_model_stream":
                    tags = event.get("tags", [])
                    if "final_synthesis" in tags:
                        chunk = event["data"]["chunk"]
                        if hasattr(chunk, "content") and chunk.content:
                            if first_token_time is None:
                                first_token_time = time.time()
                            yield f"data: {json.dumps({'type': 'token', 'content': chunk.content}, ensure_ascii=False)}\n\n"
                            final_response_accumulated += chunk.content

                # D. Lắng nghe event kết thúc đồ thị để thu thập response_text cuối cùng
                elif event["event"] == "on_chain_end":
                    name = event.get("name")
                    output = event["data"].get("output")

                    # Đo thời gian xử lý từng node (supervisor/sub-agent) để biết agent nào chậm
                    if name in agent_node_names:
                        step_start = agent_step_start_times.pop(event["run_id"], None)
                        if step_start is not None:
                            agent_step_seconds.labels(agent_name=name).observe(time.time() - step_start)

                    # Đếm số lần Supervisor định tuyến sang mỗi sub-agent (bỏ qua FINISH)
                    if name == "supervisor" and isinstance(output, dict):
                        next_agent = output.get("next_agent", "FINISH")
                        instruction = output.get("instruction", "")
                        route_msg = (
                            f"🎯 [Supervisor Quyết Định Điều Hướng]:\n"
                            f"   - Next Agent: `{next_agent}`\n"
                            f"   - Chỉ Đạo (Instruction): \"{instruction}\""
                        )
                        thought_logs.append({"type": "thought", "content": route_msg, "timestamp": time.time()})
                        yield f"data: {json.dumps({'type': 'thought', 'content': route_msg}, ensure_ascii=False)}\n\n"

                        if next_agent and next_agent != "FINISH":
                            agent_routes_total.labels(target_agent=next_agent).inc()

                    if isinstance(output, dict) and "response" in output:
                        response_text = output["response"]

            total_latency = time.time() - start_time
            latency_ms = int(total_latency * 1000)
            print(f"⏱️ [Total Chat Endpoint Latency]: Xử lý agent.ainvoke hoàn tất sau {total_latency:.2f} s")

            # Sử dụng response_text đã được hậu xử lý/failsafe từ graph làm final_content lưu DB
            final_content = response_text or final_response_accumulated

            if final_response_accumulated and response_text:
                # Nếu có phần được thêm vào sau khi stream xong (như link tải từ failsafe), yield phần thừa đó ra
                if response_text.startswith(final_response_accumulated):
                    extra = response_text[len(final_response_accumulated) :]
                    if extra:
                        yield f"data: {json.dumps({'type': 'token', 'content': extra}, ensure_ascii=False)}\n\n"
                elif response_text != final_response_accumulated:
                    # Nếu có sự khác biệt lớn, yield toàn bộ phần mới để đảm bảo hiển thị đủ link
                    formatted_content = f"\n\n{response_text}"
                    yield f"data: {json.dumps({'type': 'token', 'content': formatted_content}, ensure_ascii=False)}\n\n"
            elif not final_response_accumulated and response_text:
                yield f"data: {json.dumps({'type': 'token', 'content': response_text}, ensure_ascii=False)}\n\n"

            # Xác định model và provider từ config để tính chi phí
            from src.config import get_settings

            settings = get_settings()
            provider = settings.llm_provider
            model_used = settings.deepseek_model_name if provider == "deepseek" else settings.model_name

            # Tính toán Cost (đầu vào/đầu ra trên 1M tokens)
            prices = {
                "openai": {
                    "gpt-4o-mini": (0.15, 0.60),
                    "default": (0.15, 0.60),
                },
                "deepseek": {
                    "deepseek-v4-flash": (0.14, 0.28),
                    "deepseek-chat": (0.14, 0.28),
                    "default": (0.14, 0.28),
                },
            }
            prov_prices = prices.get(provider.lower(), prices["openai"])
            in_price, out_price = prov_prices.get(model_used.lower(), prov_prices["default"])
            cost = (total_input_tokens * in_price / 1_000_000.0) + (total_output_tokens * out_price / 1_000_000.0)
            cost = round(cost, 6)

            # Ghi nhận Prometheus Metrics
            agent_requests_total.labels(model=model_used, status="success", feature="chat").inc()
            agent_latency_seconds.labels(model=model_used, feature="chat").observe(total_latency)
            if first_token_time is not None:
                agent_ttft_seconds.labels(model=model_used, feature="chat").observe(first_token_time - start_time)
            agent_tokens_total.labels(model=model_used, direction="input").inc(total_input_tokens)
            agent_tokens_total.labels(model=model_used, direction="output").inc(total_output_tokens)
            cost_per_task.labels(feature="chat").inc(cost)
            track_cost(cost)
            track_request_result(success=True)
            check_agent_runaway(str(session_id), supervisor_step_count)

            # Chụp snapshot ngay sau request thành công (bên cạnh job nền 30 phút) để
            # trend chart "Tình trạng hệ thống AI" cập nhật gần real-time khi traffic thấp (MVP).
            capture_snapshot()

            # Eval-as-a-Metric: chấm Faithfulness cho câu trả lời của knowledge_agent (RAG),
            # chạy nền (fire-and-forget) để không làm chậm response trả về người dùng.
            if rag_context and final_content and should_sample():
                asyncio.create_task(judge_faithfulness(request.message, rag_context, final_content))

            # Tương tự nhưng cho data_agent/stat_agent/sql_agent: chấm Groundedness — câu trả lời
            # có khớp với dữ liệu thô (bảng điểm/chỉ số/kết quả SQL) mà tool đã trả về không.
            if groundedness_context_parts and final_content and should_sample():
                groundedness_context = "\n\n".join(groundedness_context_parts)
                asyncio.create_task(judge_groundedness(request.message, groundedness_context, final_content))

            # Lưu tin nhắn phản hồi cuối cùng của AI vào CSDL

            if final_content:
                saved_msg = chat_repo.create_message(
                    db,
                    session_id=session_id,
                    role=enums.AiSessionRole.assistant,
                    content=final_content,
                    generated_sql=generated_sql,
                    model_used=model_used,
                    latency_ms=latency_ms,
                    thought_trace=thought_logs,
                    input_token_count=total_input_tokens,
                    output_token_count=total_output_tokens,
                    cost=cost,
                    llm_provider=provider,
                    guardrail_status=classify_response_guardrail(final_content),
                )
                yield f"data: {json.dumps({'type': 'message_id', 'content': str(saved_msg.id)}, ensure_ascii=False)}\n\n"

        except Exception as e:
            # Lưu vết lỗi xuống Database làm phản hồi lỗi của assistant
            try:
                latency_ms = int((time.time() - start_time) * 1000)
                chat_repo.create_message(
                    db,
                    session_id=session_id,
                    role=enums.AiSessionRole.assistant,
                    content=f"Error: {str(e)}",
                    model_used=model_used,
                    latency_ms=latency_ms,
                    thought_trace=thought_logs,
                    input_token_count=total_input_tokens,
                    output_token_count=0,
                    cost=0.0,
                    llm_provider=provider,
                )
            except Exception:
                pass

            # Ghi nhận Prometheus Metrics Lỗi
            agent_requests_total.labels(model="unknown", status="error", feature="chat").inc()
            track_request_result(success=False)
            # Phát sinh gói tin lỗi để Frontend bắt được
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"
        finally:
            current_user_school_id.reset(token_school)
            current_user_role.reset(token_role)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/messages/{message_id}/feedback", response_model=AiMessageResponse)
def give_message_feedback(
    message_id: int | str,
    payload: MessageFeedbackRequest,
    user: CurrentUser,
    db: Session = Depends(get_db),
):
    """Gửi đánh giá phản hồi (rating, nhãn phân loại feedback_tag và feedback_text) cho tin nhắn AI."""
    from src.models.tables import AiMessage, AiSession

    try:
        m_id: int | UUID | str = int(message_id)
    except (ValueError, TypeError):
        try:
            m_id = UUID(str(message_id))
        except (ValueError, TypeError):
            m_id = message_id

    message = db.get(AiMessage, m_id)
    if not message:
        raise HTTPException(status_code=404, detail="Không tìm thấy tin nhắn")

    session = db.get(AiSession, message.session_id)
    if not session or str(session.user_id) != str(user.id):
        raise HTTPException(status_code=403, detail="Bạn không có quyền đánh giá tin nhắn này")

    # Kiểm tra ràng buộc nhãn "Khác" bắt buộc nhập text đóng góp chi tiết
    if payload.feedback_tag == "Khác" and (not payload.feedback_text or not payload.feedback_text.strip()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Vui lòng nhập ý kiến đóng góp chi tiết khi chọn nhãn Khác"
        )

    updated = chat_repo.update_message_feedback(
        db, message_id, payload.rating, payload.feedback_tag, payload.feedback_text
    )
    if not updated:
        raise HTTPException(status_code=400, detail="Không thể lưu phản hồi")
    return updated


@router.get("/admin/telemetry", response_model=AiTelemetryStatsResponse)
def get_admin_telemetry(
    user: CurrentUser,
    days: int | None = None,
    skip: int = 0,
    limit: int = Query(default=2000, le=2000),
    db: Session = Depends(get_db),
):
    """[ADMIN] Thống kê tổng hợp (tính bằng SQL, không load hết bảng vào RAM) + danh sách tin
    nhắn AI phân trang (`skip`/`limit`) phục vụ trang Telemetry Dashboard."""
    if user.role != enums.UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Bạn không có quyền truy cập thông tin quản trị này")

    from datetime import datetime, timedelta

    from src.models.tables import AiMessage

    is_error_expr = AiMessage.content.like("Error:%")
    base_filter = [AiMessage.role == enums.AiSessionRole.assistant]
    if days is not None:
        since = datetime.now(UTC) - timedelta(days=days)
        base_filter.append(AiMessage.created_at >= since)

    agg_stmt = select(
        func.count().label("total_requests"),
        func.coalesce(func.sum(case((is_error_expr, 1), else_=0)), 0).label("total_errors"),
        func.coalesce(func.sum(AiMessage.cost), 0).label("total_cost"),
        func.coalesce(func.sum(case((is_error_expr, 0), else_=AiMessage.latency_ms)), 0).label("total_latency_ms"),
        func.coalesce(func.sum(AiMessage.input_token_count), 0).label("total_input_tokens"),
        func.coalesce(func.sum(AiMessage.output_token_count), 0).label("total_output_tokens"),
        func.count(func.distinct(AiMessage.session_id)).label("total_sessions"),
        func.coalesce(func.sum(case((AiMessage.rating == 1, 1), else_=0)), 0).label("helpful_count"),
        func.coalesce(func.sum(case((AiMessage.rating == -1, 1), else_=0)), 0).label("unhelpful_count"),
        func.coalesce(
            func.sum(case((AiMessage.guardrail_status == enums.GuardrailStatus.BLOCKED_PII, 1), else_=0)), 0
        ).label("pii_flagged_count"),
    ).where(*base_filter)
    agg = db.execute(agg_stmt).one()

    total_requests = agg.total_requests
    total_errors = agg.total_errors
    total_cost = float(agg.total_cost)
    non_error_count = total_requests - total_errors
    avg_latency = (agg.total_latency_ms / non_error_count) if non_error_count > 0 else 0.0
    total_input_tokens = agg.total_input_tokens
    total_output_tokens = agg.total_output_tokens
    total_tokens = total_input_tokens + total_output_tokens
    helpful_count = agg.helpful_count
    unhelpful_count = agg.unhelpful_count
    total_feedbacks = helpful_count + unhelpful_count
    # "Không bị chê" — coi tin nhắn CHƯA có phản hồi là "không tệ" (không phải "được khen").
    helpful_ratio = 1.0 - (unhelpful_count / total_requests) if total_requests else 1.0
    feedback_rate = (total_feedbacks / total_requests) if total_requests else 0.0
    positive_feedback_ratio = (helpful_count / total_feedbacks) if total_feedbacks else None
    error_rate = (total_errors / total_requests) if total_requests else 0.0
    avg_cost_per_request = (total_cost / total_requests) if total_requests else 0.0

    msg_stmt = select(AiMessage).where(*base_filter).order_by(AiMessage.created_at.desc()).offset(skip).limit(limit)
    msg_details = list(db.execute(msg_stmt).scalars().all())

    return {
        "total_cost": round(total_cost, 6),
        "avg_latency_ms": round(avg_latency, 2),
        "total_tokens": total_tokens,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "helpful_count": helpful_count,
        "unhelpful_count": unhelpful_count,
        "total_feedbacks": total_feedbacks,
        "helpful_ratio": round(helpful_ratio, 4),
        "feedback_rate": round(feedback_rate, 4),
        "positive_feedback_ratio": round(positive_feedback_ratio, 4) if positive_feedback_ratio is not None else None,
        "total_sessions": agg.total_sessions,
        "total_requests": total_requests,
        "total_errors": total_errors,
        "error_rate": round(error_rate, 4),
        "avg_cost_per_request": round(avg_cost_per_request, 6),
        "pii_flagged_count": agg.pii_flagged_count,
        "messages": msg_details,
    }


@router.get("/admin/telemetry-by-school", response_model=SchoolTelemetryResponse)
def get_admin_telemetry_by_school(
    user: CurrentUser,
    days: int | None = None,
    db: Session = Depends(get_db),
):
    """[ADMIN] Breakdown chi phí/lỗi/latency theo từng trường (tenant) — cho biết trường nào
    đang đốt ngân sách LLM hoặc gặp tỷ lệ lỗi cao nhất, thứ mà KPI tổng (`/admin/telemetry`)
    không tách ra được vì gộp chung mọi trường."""
    if user.role != enums.UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Bạn không có quyền truy cập thông tin quản trị này")

    from datetime import datetime, timedelta

    from src.models.tables import AiMessage, AiSession, User

    stmt = (
        select(User.so_school_id, AiMessage)
        .join(AiSession, AiMessage.session_id == AiSession.id)
        .join(User, AiSession.user_id == User.id)
        .where(AiMessage.role == enums.AiSessionRole.assistant)
    )
    if days is not None:
        since = datetime.now(UTC) - timedelta(days=days)
        stmt = stmt.where(AiMessage.created_at >= since)

    rows = db.execute(stmt).all()

    by_school: dict = {}
    for school_id, msg in rows:
        agg = by_school.setdefault(
            school_id,
            {
                "school_name": f"Trường #{school_id}",
                "total_requests": 0,
                "total_errors": 0,
                "total_cost": 0.0,
                "total_latency_ms": 0,
            },
        )
        is_error = msg.content.startswith("Error:") if msg.content else False
        agg["total_requests"] += 1
        agg["total_cost"] += float(msg.cost or 0.0)
        if is_error:
            agg["total_errors"] += 1
        else:
            agg["total_latency_ms"] += msg.latency_ms or 0

    schools = []
    for school_id, agg in by_school.items():
        non_error_count = agg["total_requests"] - agg["total_errors"]
        avg_latency = agg["total_latency_ms"] / non_error_count if non_error_count > 0 else 0.0
        error_rate = agg["total_errors"] / agg["total_requests"] if agg["total_requests"] > 0 else 0.0
        schools.append(
            {
                "school_id": school_id,
                "school_name": agg["school_name"],
                "total_requests": agg["total_requests"],
                "total_errors": agg["total_errors"],
                "error_rate": round(error_rate, 4),
                "total_cost": round(agg["total_cost"], 6),
                "avg_latency_ms": round(avg_latency, 2),
            }
        )

    schools.sort(key=lambda s: s["total_cost"], reverse=True)
    return {"schools": schools}


@router.get("/admin/observability-summary", response_model=ObservabilitySummaryResponse)
def get_observability_summary(user: CurrentUser, db: Session = Depends(get_db)):
    """[ADMIN] Snapshot AgentOps hiện tại: cost/ngân sách, latency P95, tool success, Faithfulness,
    Groundedness và danh sách cảnh báo Discord gần nhất.

    Ưu tiên đọc Prometheus REGISTRY + alerting state trong process (cập nhật theo thời gian thực,
    không cần Prometheus server). Các Counter/Histogram này RESET mỗi khi backend restart — để
    dashboard không "về 0" ngay sau khi restart, mọi chỉ số rơi vào None/0 sẽ fallback về snapshot
    gần nhất đã lưu DB (`ai_observability_snapshots`, ghi mỗi 30 phút + sau mỗi lượt chat thành
    công) làm "trạng thái cuối cùng đã biết". Riêng breakdown theo sub-agent (`agent_routes`,
    `agent_step_p95_ms`) fallback THEO TỪNG AGENT thay vì toàn-bộ-hoặc-không: nếu không, chỉ cần
    1 agent có lượt gọi mới sau restart là toàn bộ breakdown rơi về live-view thiếu dữ liệu, khiến
    các agent chưa được gọi lại hiện sai thành "0 lượt" dù lịch sử đã có nhiều. `daily_cost_usd`
    tính thẳng từ DB (tổng cost các tin nhắn hôm nay) để luôn chính xác dù server restart giữa ngày."""
    if user.role != enums.UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Bạn không có quyền truy cập thông tin quản trị này")

    from datetime import datetime as dt_cls
    from datetime import time as time_cls

    from sqlalchemy import func

    from src.config import get_settings
    from src.models.tables import AiMessage, AiObservabilitySnapshot

    settings = get_settings()
    p95_latency = histogram_quantile(agent_latency_seconds, 0.95, {"feature": "chat"})
    p95_ttft = histogram_quantile(agent_ttft_seconds, 0.95, {"feature": "chat"})
    success = sum_counter(tool_calls_total, {"status": "success"})
    error = sum_counter(tool_calls_total, {"status": "error"})
    total_tool_calls = success + error

    # Breakdown theo từng sub-agent — cho biết agent nào được gọi nhiều/chậm/hay lỗi nhất,
    # thay vì chỉ có 1 con số tổng cho toàn bộ multi-agent graph.
    agent_names = ["data_agent", "stat_agent", "sql_agent", "knowledge_agent", "report_agent"]
    agent_step_p95_ms = {}
    for agent_name in ["supervisor", *agent_names]:
        p95 = histogram_quantile(agent_step_seconds, 0.95, {"agent_name": agent_name})
        agent_step_p95_ms[agent_name] = round(p95 * 1000, 1) if p95 is not None else None

    sql_rejections = breakdown_counter(sql_guardrail_rejections_total, "reason")

    # Fallback: snapshot gần nhất trong DB, dùng khi process vừa restart nên chưa kịp tích lũy
    # mẫu nào (Counter/Histogram Prometheus và alerting._state đều mất theo vòng đời process).
    latest_snapshot = db.execute(
        select(AiObservabilitySnapshot).order_by(AiObservabilitySnapshot.captured_at.desc()).limit(1)
    ).scalar_one_or_none()

    latency_p95_ms = (
        round(p95_latency * 1000, 1)
        if p95_latency is not None
        else (latest_snapshot.latency_p95_ms if latest_snapshot else None)
    )
    ttft_p95_ms = (
        round(p95_ttft * 1000, 1)
        if p95_ttft is not None
        else (latest_snapshot.ttft_p95_ms if latest_snapshot else None)
    )
    faithfulness_avg = get_recent_faithfulness_avg()
    if faithfulness_avg is None and latest_snapshot and latest_snapshot.faithfulness_avg is not None:
        faithfulness_avg = float(latest_snapshot.faithfulness_avg)
    groundedness_avg = get_recent_eval_avg("groundedness")
    if groundedness_avg is None and latest_snapshot and latest_snapshot.groundedness_avg is not None:
        groundedness_avg = float(latest_snapshot.groundedness_avg)
    tool_success_rate = (success / total_tool_calls) if total_tool_calls > 0 else None
    if tool_success_rate is None and latest_snapshot and latest_snapshot.tool_success_rate is not None:
        tool_success_rate = float(latest_snapshot.tool_success_rate)

    # Backend vừa restart -> agent_routes_total/agent_step_seconds chưa tích lũy mẫu nào cho
    # TỪNG agent riêng lẻ -> merge theo từng key với snapshot gần nhất (xem docstring 2 hàm dưới).
    live_agent_routes = {k: int(v) for k, v in breakdown_counter(agent_routes_total, "target_agent").items()}
    agent_routes = merge_counts_with_snapshot_fallback(
        live_agent_routes, latest_snapshot.agent_routes if latest_snapshot else None
    )
    agent_step_p95_ms = merge_p95_with_snapshot_fallback(
        agent_step_p95_ms, latest_snapshot.agent_step_p95_ms if latest_snapshot else None
    )

    # Chi phí hôm nay: tính thẳng từ DB (không dựa vào in-process counter của alerting) để luôn
    # đúng dù server restart giữa ngày — counter in-process chỉ dùng để debounce cảnh báo Discord.
    today_start = dt_cls.combine(dt_cls.now(UTC).date(), time_cls.min, tzinfo=UTC)
    daily_cost_usd = float(
        db.execute(
            select(func.coalesce(func.sum(AiMessage.cost), 0)).where(
                AiMessage.role == enums.AiSessionRole.assistant, AiMessage.created_at >= today_start
            )
        ).scalar_one()
    )

    return {
        "daily_cost_usd": daily_cost_usd,
        "daily_budget_usd": settings.daily_llm_budget_usd,
        "latency_p95_ms": latency_p95_ms,
        "ttft_p95_ms": ttft_p95_ms,
        "faithfulness_avg": faithfulness_avg,
        "groundedness_avg": groundedness_avg,
        "tool_success_rate": tool_success_rate,
        "recent_alerts": get_recent_alerts(10),
        "agent_routes": agent_routes,
        "agent_step_p95_ms": agent_step_p95_ms,
        "sql_guardrail_rejections_total": int(sum(sql_rejections.values())),
    }


@router.get("/admin/observability-history", response_model=ObservabilityHistoryResponse)
def get_observability_history(
    user: CurrentUser,
    db: Session = Depends(get_db),
    days: int = 7,
):
    """[ADMIN] Lịch sử snapshot AgentOps `days` ngày gần nhất (ghi định kỳ bởi background job),
    phục vụ trend chart trong tab "Tình trạng hệ thống AI"."""
    if user.role != enums.UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Bạn không có quyền truy cập thông tin quản trị này")

    from datetime import datetime, timedelta

    from src.models.tables import AiObservabilitySnapshot

    since = datetime.now(UTC) - timedelta(days=days)
    stmt = (
        select(AiObservabilitySnapshot)
        .where(AiObservabilitySnapshot.captured_at >= since)
        .order_by(AiObservabilitySnapshot.captured_at.asc())
    )
    snapshots = db.execute(stmt).scalars().all()
    return {"snapshots": snapshots}

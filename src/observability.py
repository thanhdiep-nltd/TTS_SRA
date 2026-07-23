import os
import re
import uuid

import structlog
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from structlog.contextvars import bind_contextvars, clear_contextvars

# 1. Prometheus Metrics
# Buckets mặc định của prometheus_client (0.005s..10s) quá hẹp cho latency của LLM agent
# (có thể tới vài chục giây do multi-agent/RAG) -> khai báo buckets riêng theo giây.
# Mật độ dày ở dải 1-10s (nơi phần lớn lượt chat multi-agent thực tế rơi vào) để
# histogram_quantile() nội suy P95/P99 chính xác hơn — bucket thưa (vd 2->5->10) khiến nội
# suy tuyến tính lệch nặng khi dữ liệu thật tập trung giữa 2 mốc xa nhau (đã đo thực nghiệm
# lệch ~29% với buckets cũ trên phân phối latency giả lập giống thực tế).
_LATENCY_BUCKETS = (
    0.5,
    1,
    1.5,
    2,
    2.5,
    3,
    3.5,
    4,
    4.5,
    5,
    6,
    7,
    8,
    9,
    10,
    12,
    15,
    20,
    30,
    45,
    60,
    90,
    120,
)

agent_requests_total = Counter("agent_requests_total", "Requests", ["model", "status", "feature"])
agent_latency_seconds = Histogram(
    "agent_latency_seconds", "Latency tổng (P50/P95/P99)", ["model", "feature"], buckets=_LATENCY_BUCKETS
)
agent_ttft_seconds = Histogram(
    "agent_ttft_seconds", "Time To First Token", ["model", "feature"], buckets=_LATENCY_BUCKETS
)
agent_tokens_total = Counter("agent_tokens_total", "Tokens", ["model", "direction"])
tool_calls_total = Counter("tool_calls_total", "Tool Calls", ["tool_name", "agent_name", "status"])
tool_latency_seconds = Histogram("tool_latency_seconds", "Tool Latency", ["tool_name", "agent_name"])
cost_per_task = Counter("cost_per_task_total", "Chi phí LLM theo task (USD)", ["feature"])
eval_score_gauge = Gauge("eval_score", "Điểm Eval gần nhất (Ragas)", ["metric_name"])

# Multi-agent routing/step metrics — cho phép soi từng sub-agent thay vì chỉ tổng request/latency.
agent_routes_total = Counter("agent_routes_total", "Số lần Supervisor định tuyến tới mỗi sub-agent", ["target_agent"])
agent_step_seconds = Histogram(
    "agent_step_seconds",
    "Thời gian xử lý mỗi node (supervisor/sub-agent) trong 1 lượt chat",
    ["agent_name"],
    buckets=_LATENCY_BUCKETS,
)
sql_guardrail_rejections_total = Counter(
    "sql_guardrail_rejections_total", "Số lần SQL do sql_agent sinh ra bị guardrail từ chối", ["reason"]
)

# Map tool_name -> agent_name sở hữu tool đó, dùng để gắn nhãn agent_name cho tool_calls_total/
# tool_latency_seconds (LangGraph event không kèm sẵn tên node sở hữu tool trong on_tool_* event).
TOOL_AGENT_MAP = {
    "get_student_info": "data_service_agent",
    "get_student_grades": "data_service_agent",
    "get_class_grades": "data_service_agent",
    "calculate_grade_statistics": "stat_agent",
    "find_top_students": "stat_agent",
    "find_struggling_students": "stat_agent",
    "compare_classes": "stat_agent",
    "get_student_academic_trend": "stat_agent",
    "get_academic_divergence_metrics": "stat_agent",
    "get_grade_inflation_report": "stat_agent",
    "get_evaluation_momentum": "stat_agent",
    "get_exam_validity_report": "stat_agent",
    "execute_read_only_query": "data_service_agent",
    "validate_and_secure_sql": "data_service_agent",
    "search_textbook": "knowledge_agent",
    "get_report_data_summary": "report_agent",
    "generate_custom_report_docx": "report_agent",
}

# 2. PII Redaction (regex — nhẹ, khớp định dạng VN: SĐT, email, CCCD/CMND 9-12 số)
_PII_PATTERNS = [
    (re.compile(r"\b(0|\+84)(\d{9,10})\b"), "[PHONE_REDACTED]"),
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"), "[EMAIL_REDACTED]"),
    (re.compile(r"\b\d{9}(\d{3})?\b"), "[ID_REDACTED]"),
]


def redact_pii(text: str) -> str:
    """Che SĐT/email/CCCD trong log theo PDPL 91/2025 bằng regex (không qua NLP)."""
    if not isinstance(text, str):
        return text
    for pattern, replacement in _PII_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def classify_response_guardrail(text: str):
    """Gắn nhãn giám sát (ADVISORY — chỉ để theo dõi/thống kê, KHÔNG chặn phản hồi) cho câu trả
    lời cuối cùng của AI: có chứa PII thô (SĐT/email/CCCD chưa redact) không.

    Lấp cột `ai_messages.guardrail_status`/enum `GuardrailStatus` — tồn tại sẵn trong schema
    nhưng trước đây không nơi nào ghi giá trị (audit 2026-07-02). Chỉ phát hiện PII bằng regex
    dùng chung với `redact_pii`; KHÔNG phát hiện prompt-injection/nội dung nhạy cảm (cần cơ chế
    riêng đáng tin cậy hơn — regex đoán injection dễ gây cảm giác an toàn giả).
    """
    from src.models.enums import GuardrailStatus

    if not isinstance(text, str) or not text:
        return GuardrailStatus.PASSED
    for pattern, _replacement in _PII_PATTERNS:
        if pattern.search(text):
            return GuardrailStatus.BLOCKED_PII
    return GuardrailStatus.PASSED


# 3. Structlog Config
def add_redaction(logger, log_method, event_dict):
    """Redact PII from log arguments before logging."""
    for key, value in event_dict.items():
        if isinstance(value, str):
            event_dict[key] = redact_pii(value)
    return event_dict


structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        add_redaction,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(20),  # logging.INFO
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger()


def get_langfuse_handler():
    """Tạo Langfuse CallbackHandler (SDK v4, OTel-native) nếu đã cấu hình LANGFUSE_PUBLIC_KEY/SECRET_KEY.

    Trả None nếu chưa cấu hình hoặc lỗi (fail-soft). Lưu ý: session_id/user_id/tags KHÔNG
    truyền vào constructor (API v4 chỉ nhận `public_key`/`trace_context`) — phải gắn qua
    `config={"metadata": {"langfuse_session_id": ..., "langfuse_user_id": ..., "langfuse_tags": [...]}}`
    khi gọi `agent.astream_events(...)`, xem src/api/v1/chat.py.
    """
    if not os.getenv("LANGFUSE_PUBLIC_KEY") or not os.getenv("LANGFUSE_SECRET_KEY"):
        return None
    try:
        from langfuse.langchain import CallbackHandler

        return CallbackHandler()
    except Exception as exc:
        logger.warning("langfuse_handler_init_failed", error=str(exc))
        return None


def histogram_quantile(
    histogram: Histogram, quantile: float, label_match: dict[str, str] | None = None
) -> float | None:
    """Tính percentile xấp xỉ (nội suy tuyến tính) từ Histogram Prometheus đang chạy trong process.

    Tương đương `histogram_quantile()` của PromQL nhưng tính trực tiếp trên REGISTRY in-process,
    không cần Prometheus server riêng (phù hợp backend chạy 1 instance). `label_match` lọc theo
    nhãn (vd {"feature": "chat"}); các series khớp được cộng dồn theo từng `le` (hợp lệ vì tất cả
    series của 1 Histogram dùng chung danh sách bucket boundaries).
    """
    bucket_totals: dict[float, float] = {}
    for metric in histogram.collect():
        for sample in metric.samples:
            if not sample.name.endswith("_bucket"):
                continue
            if label_match and any(sample.labels.get(k) != v for k, v in label_match.items()):
                continue
            le = float(sample.labels["le"])
            bucket_totals[le] = bucket_totals.get(le, 0.0) + sample.value

    if not bucket_totals:
        return None
    sorted_les = sorted(bucket_totals)
    total_count = bucket_totals[sorted_les[-1]]  # bucket +Inf = tổng số quan sát
    if total_count == 0:
        return None

    target = quantile * total_count
    prev_le, prev_count = 0.0, 0.0
    for le in sorted_les:
        count = bucket_totals[le]
        if count >= target:
            if le == float("inf"):
                return prev_le  # không nội suy được qua +Inf, trả bucket hữu hạn cuối
            if count == prev_count:
                return le
            fraction = (target - prev_count) / (count - prev_count)
            return prev_le + fraction * (le - prev_le)
        prev_le, prev_count = le, count
    return sorted_les[-1]


def sum_counter(counter, label_match: dict[str, str] | None = None) -> float:
    """Cộng dồn giá trị 1 Counter Prometheus qua các label series, lọc theo `label_match`."""
    total = 0.0
    for metric in counter.collect():
        for sample in metric.samples:
            if not sample.name.endswith("_total"):
                continue
            if label_match and any(sample.labels.get(k) != v for k, v in label_match.items()):
                continue
            total += sample.value
    return total


def breakdown_counter(counter, group_by: str, label_match: dict[str, str] | None = None) -> dict[str, float]:
    """Cộng dồn giá trị 1 Counter, gom nhóm theo nhãn `group_by` (vd agent_name) thay vì ra 1 tổng duy nhất.

    Dùng để trả về cho UI breakdown như "số request mỗi sub-agent" mà không cần Prometheus server.
    """
    totals: dict[str, float] = {}
    for metric in counter.collect():
        for sample in metric.samples:
            if not sample.name.endswith("_total"):
                continue
            if label_match and any(sample.labels.get(k) != v for k, v in label_match.items()):
                continue
            key = sample.labels.get(group_by, "unknown")
            totals[key] = totals.get(key, 0.0) + sample.value
    return totals


def merge_counts_with_snapshot_fallback(live: dict[str, int], snapshot: dict[str, int] | None) -> dict[str, int]:
    """Merge breakdown đếm (vd `agent_routes`) live với snapshot cũ THEO TỪNG KEY — không phải
    toàn-bộ-hoặc-không: key nào `live` đã có (accumulate được kể từ lần restart gần nhất) thì giữ
    nguyên; key nào `live` CHƯA có (agent tương ứng chưa được gọi lại) thì lấy tạm từ snapshot.

    Trước đây dùng điều kiện `if not live: live = snapshot` — chỉ cần 1 agent có hoạt động mới là
    dict `live` không còn rỗng, khiến TOÀN BỘ agent khác (dù có lịch sử) hiện sai thành 0.
    """
    merged = dict(live)
    if snapshot:
        for key, value in snapshot.items():
            merged.setdefault(key, int(value))
    return merged


def merge_p95_with_snapshot_fallback(
    live: dict[str, float | None], snapshot: dict[str, float | None] | None
) -> dict[str, float | None]:
    """Tương tự `merge_counts_with_snapshot_fallback` nhưng cho breakdown latency P95 (giá trị có
    thể là None khi agent đó chưa có mẫu nào trong cửa sổ hiện tại)."""
    merged = dict(live)
    if snapshot:
        for key, value in snapshot.items():
            if merged.get(key) is None and value is not None:
                merged[key] = value
    return merged


def setup_observability(app):
    # Prometheus metrics endpoint — bảo vệ bằng METRICS_TOKEN (nếu đã cấu hình) vì đây
    # là endpoint public khi deploy thật, lộ token/cost/latency theo model.
    import time

    from fastapi import HTTPException, Request, Response
    from starlette.middleware.base import BaseHTTPMiddleware

    @app.get("/metrics", include_in_schema=False)
    def metrics_endpoint(request: Request):
        from src.config import get_settings

        token = get_settings().metrics_token
        if token and request.headers.get("X-Metrics-Token") != token:
            raise HTTPException(status_code=403, detail="Thiếu hoặc sai METRICS_TOKEN")
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    class ObservabilityMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            clear_contextvars()
            req_id = str(uuid.uuid4())[:8]
            bind_contextvars(correlation_id=req_id, method=request.method, path=request.url.path)

            start_time = time.time()
            try:
                response = await call_next(request)
            except Exception as e:
                logger.error("request_failed", error=str(e), exc_info=True)
                raise e
            finally:
                duration = time.time() - start_time
                logger.info(
                    "request_completed",
                    status_code=response.status_code if "response" in locals() else 500,
                    duration_ms=round(duration * 1000, 2),
                )

            # Attach trace id to response if needed
            if "response" in locals() and response:
                response.headers["X-Correlation-ID"] = req_id

            return response

    app.add_middleware(ObservabilityMiddleware)

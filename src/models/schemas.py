from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from src.schemas.common import ORMBase


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000, description="Tin nhắn từ user")
    session_id: UUID | None = Field(default=None, description="ID của phiên chat")


class ChatResponse(BaseModel):
    response: str = Field(..., description="Phản hồi từ agent")
    analysis: str = Field(default="", description="Phân tích nội bộ")
    session_id: UUID = Field(..., description="ID của phiên chat")


class AiSessionResponse(ORMBase):
    id: UUID
    title: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AiSessionUpdate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500, description="Tiêu đề mới")


class AiMessageResponse(ORMBase):
    id: int | str | UUID
    role: str
    content: str
    generated_sql: str | None = None
    sources: dict | list | None = None
    created_at: datetime

    # New feedback/telemetry columns for rendering chat history
    rating: int | None = None
    feedback_tag: str | None = None
    feedback_text: str | None = None
    feedback_at: datetime | None = None
    thought_trace: list | dict | None = None
    input_token_count: int | None = None
    output_token_count: int | None = None
    cost: float | None = None
    llm_provider: str | None = None
    model_used: str | None = None
    latency_ms: int | None = None


class MessageFeedbackRequest(BaseModel):
    rating: int = Field(..., description="1: Thích/Hữu ích, -1: Không thích/Không đúng")
    feedback_tag: str | None = Field(default=None, description="Nhãn phân loại lỗi")
    feedback_text: str | None = Field(default=None, description="Ý kiến đóng góp chi tiết")


class TelemetryMessageDetail(BaseModel):
    id: int | str | UUID
    session_id: UUID
    role: str
    content: str
    created_at: datetime
    rating: int | None = None
    feedback_tag: str | None = None
    feedback_text: str | None = None
    feedback_at: datetime | None = None
    thought_trace: list | dict | None = None
    latency_ms: int | None = None
    input_token_count: int | None = None
    output_token_count: int | None = None
    cost: float | None = None
    llm_provider: str | None = None
    model_used: str | None = None


class AiTelemetryStatsResponse(BaseModel):
    total_cost: float
    avg_latency_ms: float
    total_tokens: int
    total_input_tokens: int
    total_output_tokens: int
    helpful_count: int
    unhelpful_count: int
    total_feedbacks: int
    # "Không bị chê" = 1 - (unhelpful/total_requests) — GẦN NHƯ LUÔN CAO vì đa số tin nhắn
    # không ai đánh giá gì (mặc định coi là "không tệ"), KHÔNG phải "% người dùng hài lòng".
    # Đọc cùng `feedback_rate` để biết con số này có đáng tin không (feedback_rate thấp nghĩa
    # là helpful_ratio dựa trên rất ít phản hồi thật).
    helpful_ratio: float
    # % tin nhắn THẬT SỰ có người bấm đánh giá (helpful_count + unhelpful_count) / total_requests.
    feedback_rate: float
    # % tích cực TRONG SỐ những tin nhắn có phản hồi — phản ánh đúng "hài lòng" hơn helpful_ratio.
    # None nếu chưa có phản hồi nào.
    positive_feedback_ratio: float | None = None
    total_sessions: int
    total_requests: int
    total_errors: int
    error_rate: float
    avg_cost_per_request: float
    # Số tin nhắn AI bị gắn nhãn advisory BLOCKED_PII (chứa PII thô chưa redact) — xem
    # observability.classify_response_guardrail. Chỉ để giám sát, KHÔNG chặn phản hồi.
    pii_flagged_count: int = 0
    messages: list[TelemetryMessageDetail]


class SchoolTelemetryItem(BaseModel):
    school_id: UUID
    school_name: str
    total_requests: int
    total_errors: int
    error_rate: float
    total_cost: float
    avg_latency_ms: float


class SchoolTelemetryResponse(BaseModel):
    schools: list[SchoolTelemetryItem]


class ObservabilityAlertItem(BaseModel):
    type: str
    message: str
    sent_at: str


class ObservabilitySummaryResponse(BaseModel):
    daily_cost_usd: float
    daily_budget_usd: float
    latency_p95_ms: float | None = None
    ttft_p95_ms: float | None = None
    faithfulness_avg: float | None = None
    groundedness_avg: float | None = None
    tool_success_rate: float | None = None
    recent_alerts: list[ObservabilityAlertItem]
    agent_routes: dict[str, int] = {}
    agent_step_p95_ms: dict[str, float | None] = {}
    sql_guardrail_rejections_total: int = 0


class ObservabilitySnapshotItem(ORMBase):
    captured_at: datetime
    daily_cost_usd: float
    daily_budget_usd: float
    latency_p95_ms: int | None = None
    ttft_p95_ms: int | None = None
    faithfulness_avg: float | None = None
    groundedness_avg: float | None = None
    tool_success_rate: float | None = None
    total_requests: int
    total_tokens_in: int
    total_tokens_out: int


class ObservabilityHistoryResponse(BaseModel):
    snapshots: list[ObservabilitySnapshotItem]


class AiSessionAttachmentResponse(ORMBase):
    id: int
    session_id: UUID
    file_name: str
    file_type: str
    char_count: int
    truncated: bool
    created_at: datetime



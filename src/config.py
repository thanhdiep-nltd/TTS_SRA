from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_name: str = "AI20K Agent"
    app_env: Literal["development", "production", "test"] = "development"
    app_port: int = Field(default=8000, ge=1, le=65535)
    app_host: str = "0.0.0.0"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    cors_origins: str = "http://localhost:3000"
    backend_url: str = Field(default="http://localhost:8000", validation_alias="BACKEND_URL")

    # LLM
    llm_provider: Literal["openai", "deepseek"] = "openai"
    openai_api_key: str = ""
    openai_api_base: str = "https://api.openai.com/v1"
    model_name: str = "gpt-4o-mini"
    deepseek_api_key: str = ""
    deepseek_model_name: str = "deepseek-v4-flash"
    deepseek_api_base: str = "https://api.deepseek.com"
    llm_temperature: float = Field(default=0.4, ge=0.0, le=2.0)
    # SDK OpenAI mặc định timeout ~600s nếu không đặt -> 1 lần API chậm/treo sẽ "ngốn" cả task nền
    # (chat, item_generation, content_difficulty đều dùng chung get_llm()). 60s đủ rộng cho prompt
    # lớn (RAG/self-consistency) nhưng vẫn giảm 10x so với mặc định SDK.
    llm_timeout_s: float = Field(default=60.0, gt=0.0)

    # LLM-based Forecasting (EWS) — giới hạn concurrency & retry để tránh HTTP 429.
    # run_llm_forecasting_batch() dùng ThreadPoolExecutor(max_workers=llm_max_concurrency).
    # _call_llm_with_retry() retry exponential backoff (2s→4s→8s) tối đa llm_max_retries lần.
    llm_max_concurrency: int = Field(default=20, ge=1, le=50)
    llm_max_retries: int = Field(default=3, ge=0, le=10)

    # Judge LLM (Eval-as-a-Metric, xem services/eval.py) — TÙY CHỌN, mặc định "same" nghĩa là
    # judge dùng chung get_llm() với agent đang được chấm (rẻ, không cần cấu hình thêm, nhưng
    # có rủi ro thiên vị tự đánh giá — model có xu hướng chấm điểm rộng lượng cho chính phong
    # cách trả lời của nó). Đặt "openai"/"deepseek" khác với llm_provider để có judge độc lập
    # thật sự (cần cấu hình API key tương ứng).
    judge_llm_provider: Literal["same", "openai", "deepseek"] = "same"

    # VLM đọc đề thi (M1 — plan_cdi_kg_anchored): Qwen3-VL-Flash qua API OpenAI-compatible.
    # User sẽ cấu hình API key sau; khi thiếu key, pipeline fallback OCR (không chặn code).
    vlm_model: str = "qwen3-vl-flash"
    vlm_api_base: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    vlm_api_key: str = ""
    vlm_timeout_s: float = Field(default=60.0, gt=0.0)
    # Số trang gọi VLM song song khi đọc nhiều trang (nạp SGK mục lục, đọc đề nhiều trang).
    # Giữ vừa phải (3-5) để không dính rate-limit 429/503 của provider.
    vlm_max_concurrency: int = Field(default=4, ge=1, le=8)

    # Database
    database_url: str = "sqlite:///./data/app.db"

    # Vector Store (chroma deprecated cho luồng RAG mới — xem docs/RAG_design.md, dùng Qdrant)
    chroma_persist_dir: str = "./data/chroma"

    # RAG Retrieval (knowledge_agent). Vector DB = Qdrant;
    # embedding_provider có thể là 'local', 'openai', 'gemini'.
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    qdrant_collection: str = "edu_knowledge"
    embedding_provider: str = "openai"
    embedding_service_url: str = "http://localhost:8001"
    gemini_api_key: str = ""
    gemini_embed_model: str = "text-embedding-004"
    openai_embed_model: str = "text-embedding-3-large"
    embedding_dim: int = Field(default=1536, ge=1)  # Default = 1536
    embedding_url: str = Field(default="https://api.shopaikey.com/v1", validation_alias="EMBEDDING_URL")
    embedding_openai_api_key: str = Field(default="", validation_alias="EMBEDDING_OPENAI_API_KEY")
    retrieval_top_k: int = Field(default=5, ge=1, le=50)
    retrieval_score_floor: float = Field(default=0.35, ge=0.0, le=1.0)  # chặn kết quả off-topic
    retrieval_timeout_s: float = Field(default=20.0, gt=0.0)

    # RAG ingestion: MinIO/S3 (lưu PDF) + Airflow REST API (trigger pipeline). Xem pipelines/airflow.
    minio_endpoint: str = "http://localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "edu-knowledge"
    airflow_base_url: str = "http://localhost:8080"
    airflow_user: str = "airflow"
    airflow_password: str = "airflow"

    # Auth / JWT — PRODUCTION phải đặt JWT_SECRET_KEY (>=32 byte ngẫu nhiên) qua env
    jwt_secret_key: str = Field(
        default="dev-only-secret-change-me-in-production-please", validation_alias="JWT_SECRET_KEY"
    )
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=30, ge=1)
    refresh_token_expire_days: int = Field(default=7, ge=1)

    # File upload (đề thi). Lưu local; production nên chuyển sang object storage.
    upload_dir: str = "./uploads"
    max_upload_mb: int = Field(default=20, ge=1)

    # Observability — bảo vệ /metrics khi public (rỗng = không yêu cầu, chỉ nên dùng ở dev)
    metrics_token: str = ""
    daily_llm_budget_usd: float = Field(default=5.0, gt=0.0)

    # Discord Webhook Alerting (Giai đoạn 4) — Telegram bị chặn ở VN, Zalo OAuth quá phức tạp
    # cho MVP (access_token ngắn hạn + refresh_token rotate). Discord webhook là 1 URL tĩnh,
    # không cần OAuth: Server Settings → Integrations → Webhooks → New Webhook.
    discord_webhook_url: str = ""

    # Eval-as-a-Metric (Giai đoạn 3): tỉ lệ sample câu trả lời knowledge_agent để chấm Faithfulness
    eval_sample_rate: float = Field(default=0.05, ge=0.0, le=1.0)

    # Đính kèm file trong chat (AI đọc nội dung) — cap số ký tự/file để tránh 1 file lớn
    # chiếm hết ngân sách token mỗi lượt hỏi (nội dung được chèn lại MỌI lượt trong session).
    chat_attachment_max_chars: int = Field(default=8000, ge=500)
    chat_attachment_max_files_per_session: int = Field(default=5, ge=1)

    # Replicate & Supabase for Classroom Recordings
    replicate_api_token: str = ""
    supabase_url: str = ""
    supabase_key: str = ""
    supabase_recordings_bucket: str = "lectures"
    vms_server_url: str = "http://localhost:5000"


@lru_cache
def get_settings() -> Settings:
    return Settings()

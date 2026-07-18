"""Đọc cấu hình pipeline từ Airflow Variables (đã nạp qua env AIRFLOW_VAR_*).

Tách riêng để DAG/helper không gọi trực tiếp `Variable.get` rải rác, dễ test.
Import `airflow` được đặt trong hàm để unit test offline không cần Airflow.
"""

from dataclasses import dataclass


def _var(key: str, default: str | None = None) -> str:
    """Lấy một Airflow Variable; raise nếu thiếu mà không có default."""
    from airflow.models import Variable

    return Variable.get(key, default_var=default)


@dataclass(frozen=True)
class DeepSeekConfig:
    api_key: str
    api_base: str
    model: str


@dataclass(frozen=True)
class QdrantConfig:
    url: str
    api_key: str
    collection: str


def deepseek_config() -> DeepSeekConfig:
    """Cấu hình gọi DeepSeek-V3 (formatting)."""
    return DeepSeekConfig(
        api_key=_var("DEEPSEEK_API_KEY"),
        api_base=_var("DEEPSEEK_API_BASE", "https://api.deepseek.com"),
        model=_var("DEEPSEEK_MODEL", "deepseek-chat"),
    )


def qdrant_config() -> QdrantConfig:
    """Cấu hình kết nối Qdrant."""
    return QdrantConfig(
        url=_var("QDRANT_URL", "http://qdrant:6333"),
        api_key=_var("QDRANT_API_KEY", ""),
        collection=_var("QDRANT_COLLECTION", "edu_knowledge"),
    )


def openai_api_key() -> str:
    return _var("OPENAI_API_KEY")


def embedding_provider() -> str:
    """Nhà cung cấp embedding: 'local' (BGE-m3, $0 offline), 'openai' (text-embedding-3-small)
    hoặc 'gemini' (gemini-embedding-001)."""
    return _var("EMBEDDING_PROVIDER", "openai")


def embedding_model() -> str:
    return _var("EMBEDDING_MODEL", "text-embedding-3-small")


def gemini_embed_model() -> str:
    return _var("GEMINI_EMBED_MODEL", "gemini-embedding-001")


def local_embed_model() -> str:
    """Model embedding local (sentence-transformers) — BGE-m3 đa ngữ, hợp tiếng Việt, 1024 chiều."""
    return _var("LOCAL_EMBED_MODEL", "BAAI/bge-m3")


_DEFAULT_DIM = {"gemini": "768", "local": "1024"}


def embedding_dim() -> int:
    """Số chiều vector của collection — phải khớp model embedding đang dùng."""
    default = _DEFAULT_DIM.get(embedding_provider(), "1536")
    val = _var("EMBEDDING_DIM", default)
    return int(val) if str(val).strip() else int(default)


def vision_provider() -> str:
    """Nhà cung cấp Vision OCR: 'openai' (gpt-4o), 'gemini' (Gemini Flash), hoặc 'qwen' (qwen3-vl-flash)."""
    return _var("VISION_PROVIDER", "openai")


def vision_model() -> str:
    """Model Vision LLM (OpenAI) cho OCR môn nhiều công thức (Toán/KHTN)."""
    return _var("VISION_MODEL", "gpt-4o")


def gemini_api_key() -> str:
    return _var("GEMINI_API_KEY")


def gemini_model() -> str:
    """Model Gemini cho Vision OCR (rẻ hơn gpt-4o)."""
    return _var("GEMINI_MODEL", "gemini-2.0-flash")


def qwen_api_key() -> str:
    return _var("QWEN_API_KEY")


def qwen_model() -> str:
    """Model Qwen-VL (DashScope) cho Vision OCR — tối ưu chi phí."""
    return _var("QWEN_MODEL", "qwen3-vl-flash")


def qwen_api_base() -> str:
    """Endpoint OpenAI-compatible của DashScope (mặc định bản quốc tế)."""
    return _var("QWEN_API_BASE", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1")


def ocr_lang() -> str:
    """Ngôn ngữ Tesseract OCR."""
    return _var("OCR_LANG", "vie")


def minio_bucket() -> str:
    return _var("MINIO_BUCKET", "edu-knowledge")


def chunk_token_size() -> int:
    return int(_var("CHUNK_TOKEN_SIZE", "3000"))

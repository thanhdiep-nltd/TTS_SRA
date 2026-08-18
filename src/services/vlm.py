"""Đọc đề thi bằng VLM (Qwen3-VL-Flash) — M1 trong docs_vsf/plan_cdi_kg_anchored.md.

Gọi API chat/completions OpenAI-compatible (base64 ảnh → text + LaTeX sạch), thay thế
OCR thô cho phần công thức. User sẽ cấu hình VLM_API_KEY sau; khi chưa có key hoặc gọi
lỗi → nâng `VlmUnavailableError` để pipeline fallback OCR (không chặn code).
"""

from __future__ import annotations

import base64
from pathlib import Path

import httpx

from src.config import Settings, get_settings
from src.observability import logger

_READ_PROMPT = (
    "Đọc đề kiểm tra trong ảnh. Trả về NGUYÊN VĂN nội dung các câu hỏi dạng text; "
    "giữ nguyên công thức toán bằng LaTeX ($...$). Không bình luận, không diễn đạt lại."
)

_TOC_PROMPT = (
    "Đây là (một phần) trang mục lục của sách giáo khoa. Trả về NGUYÊN VĂN các dòng mục lục "
    "dạng: 'Chương I: Tên chương' hoặc 'Bài 1: Tên bài'. Không bình luận, không diễn đạt lại."
)


class VlmUnavailableError(Exception):
    """VLM chưa được cấu hình (thiếu key) hoặc không gọi được — caller fallback OCR."""


def is_configured(settings: Settings | None = None) -> bool:
    """VLM có sẵn API base + key chưa (chưa set key → không cấu hình)."""
    s = settings or get_settings()
    return bool(s.vlm_api_base and s.vlm_api_key)


def _chat_completions(image_b64: str, settings: Settings, prompt: str | None = None) -> str:
    """Gọi chat/completions với 1 ảnh; trả text. Lỗi mạng/HTTP → VlmUnavailableError.

    5xx (vd 503 nhà cung cấp tạm quá tải) → retry 1 lần trước khi nâng lỗi.
    """
    payload = {
        "model": settings.vlm_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt or _READ_PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                ],
            }
        ],
    }
    url = f"{settings.vlm_api_base.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {settings.vlm_api_key}"}
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            resp = httpx.post(url, json=payload, headers=headers, timeout=settings.vlm_timeout_s)
            if isinstance(resp.status_code, int) and resp.status_code >= 500 and attempt == 0:
                last_error = httpx.HTTPStatusError(
                    f"Server error {resp.status_code}", request=resp.request, response=resp
                )
                continue
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            return content if isinstance(content, str) else str(content)
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            last_error = exc
    logger.warning("vlm_call_failed", error=str(last_error)[:200])
    raise VlmUnavailableError(f"Lỗi gọi VLM: {last_error}") from last_error


def read_image_bytes(image_bytes: bytes, settings: Settings | None = None) -> str:
    """Đọc 1 ảnh đề (PNG/JPEG...) bằng VLM → text + LaTeX."""
    s = settings or get_settings()
    if not is_configured(s):
        raise VlmUnavailableError("Thiếu VLM_API_KEY — user sẽ cấu hình sau.")
    return _chat_completions(base64.b64encode(image_bytes).decode("ascii"), s)


def read_pdf_pages(path: Path, settings: Settings | None = None, dpi: int = 150) -> str:
    """Render toàn bộ trang PDF → VLM đọc từng trang, ghép kết quả."""
    s = settings or get_settings()
    if not is_configured(s):
        raise VlmUnavailableError("Thiếu VLM_API_KEY — user sẽ cấu hình sau.")
    import fitz  # PyMuPDF — đã có trong deps (test_content_difficulty dùng)

    parts: list[str] = []
    with fitz.open(path) as doc:
        for page in doc:
            pix = page.get_pixmap(dpi=dpi)
            parts.append(_chat_completions(base64.b64encode(pix.tobytes("png")).decode("ascii"), s))
    return "\n\n".join(parts)


def read_pdf_pages_range(
    path: Path,
    start_page: int = 1,
    end_page: int | None = None,
    settings: Settings | None = None,
    dpi: int = 150,
    prompt: str | None = None,
) -> str:
    """Render các trang PDF từ start_page..end_page (1-based) → VLM đọc từng trang, ghép kết quả."""
    s = settings or get_settings()
    if not is_configured(s):
        raise VlmUnavailableError("Thiếu VLM_API_KEY — user sẽ cấu hình sau.")
    import fitz  # PyMuPDF — đã có trong deps (test_content_difficulty dùng)

    parts: list[str] = []
    with fitz.open(path) as doc:
        end = min(end_page or doc.page_count, doc.page_count)
        for idx in range(max(1, start_page), end + 1):
            pix = doc.load_page(idx - 1).get_pixmap(dpi=dpi)
            parts.append(_chat_completions(base64.b64encode(pix.tobytes("png")).decode("ascii"), s, prompt))
    return "\n\n".join(parts)


def read_pdf_toc(path: Path, settings: Settings | None = None, max_pages: int = 8, dpi: int = 120) -> str:
    """Đọc mục lục SGK từ max_pages trang đầu (thường trang 2-6) → text dòng mục lục."""
    return read_pdf_pages_range(path, 1, max_pages, settings, dpi, _TOC_PROMPT)

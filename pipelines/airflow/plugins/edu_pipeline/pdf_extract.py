"""Bóc tách nội dung PDF theo 3 chế độ (Hybrid):

- ``text``      : PDF có sẵn lớp text — PyMuPDF đọc trực tiếp ($0).
- ``tesseract`` : PDF scan, môn ít công thức — OCR cục bộ bằng Tesseract 'vie' ($0).
- ``vision``    : PDF scan, môn nhiều công thức (Toán/KHTN) — render trang -> ảnh ->
                  Vision LLM trả thẳng Markdown + LaTeX (chất lượng cao, tốn phí/trang).

Đầu ra luôn là *text/markdown thô* để đưa tiếp vào bước chunk -> DeepSeek format.
"""

import base64

_PAGE_SEP = "\n\f\n"
_VISION_PROMPT = (
    "Đây là ảnh một trang sách giáo khoa tiếng Việt. Trích xuất TOÀN BỘ nội dung "
    "thành Markdown: giữ tiêu đề, đoạn văn, bảng; chuyển mọi công thức/biểu thức toán "
    "sang LaTeX ($...$ hoặc $$...$$). Giữ nguyên 100% nội dung, không bịa. Chỉ trả Markdown."
)


def _open(pdf_bytes: bytes):
    import fitz

    return fitz.open(stream=pdf_bytes, filetype="pdf")


def _page_indices(page_count: int, max_pages: int) -> range:
    """Giới hạn số trang xử lý (max_pages<=0 nghĩa là toàn bộ) — phục vụ chạy thử rẻ."""
    return range(page_count if max_pages <= 0 else min(max_pages, page_count))


def extract_text_layer(pdf_bytes: bytes, max_pages: int = 0) -> str:
    """Đọc lớp text có sẵn (PDF không scan)."""
    with _open(pdf_bytes) as doc:
        return _PAGE_SEP.join(doc[i].get_text("text") for i in _page_indices(doc.page_count, max_pages))


def extract_with_tesseract(pdf_bytes: bytes, lang: str = "vie", max_pages: int = 0, dpi: int = 200) -> str:
    """OCR cục bộ bằng Tesseract: render từng trang thành ảnh rồi nhận dạng chữ."""
    import io

    import fitz
    import pytesseract
    from PIL import Image

    out: list[str] = []
    with _open(pdf_bytes) as doc:
        for i in _page_indices(doc.page_count, max_pages):
            pix = doc[i].get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72))
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            out.append(pytesseract.image_to_string(img, lang=lang))
    return _PAGE_SEP.join(out)


def _render_png_b64(page, dpi: int) -> str:
    import fitz

    pix = page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72))
    return base64.b64encode(pix.tobytes("png")).decode("ascii")


def _vision_page(client, model: str, b64: str, retries: int = 6) -> str:
    """Gọi Vision LLM cho 1 trang; backoff khi 429 và các lỗi tạm thời (timeout, JSON lỗi)."""
    import json
    import time

    from openai import APIError

    for attempt in range(retries + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                temperature=0.0,
                messages=[{"role": "user", "content": [
                    {"type": "text", "text": _VISION_PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                ]}],
            )
            if not resp.choices:
                raise APIError("empty choices", request=None, body=None)
            return resp.choices[0].message.content or ""
        except (APIError, json.JSONDecodeError):
            if attempt == retries:
                raise
            time.sleep(min(60, 5 * 2**attempt))
    return ""


def extract_with_vision(
    pdf_bytes: bytes, api_key: str, model: str, max_pages: int = 0, dpi: int = 180, base_url: str | None = None
) -> str:
    """OCR bằng Vision LLM tương thích OpenAI: mỗi trang -> ảnh -> Markdown+LaTeX.

    Dùng cho cả OpenAI (gpt-4o) và các API OpenAI-compatible như Qwen/DashScope
    (qwen3-vl-flash) qua `base_url`. Xử lý tuần tự + backoff trong _vision_page.
    """
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=base_url, max_retries=8)
    out: list[str] = []
    with _open(pdf_bytes) as doc:
        for i in _page_indices(doc.page_count, max_pages):
            out.append(_vision_page(client, model, _render_png_b64(doc[i], dpi)))
    return _PAGE_SEP.join(out)


_GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"


def _gemini_page(api_key: str, model: str, b64: str, retries: int = 6) -> str:
    """OCR 1 trang qua Gemini REST (generateContent); backoff khi 429/503."""
    import time

    import httpx

    url = f"{_GEMINI_BASE}/models/{model}:generateContent"
    payload = {
        "contents": [{"parts": [
            {"text": _VISION_PROMPT},
            {"inline_data": {"mime_type": "image/png", "data": b64}},
        ]}],
        "generationConfig": {"temperature": 0.0},
    }
    for attempt in range(retries + 1):
        resp = httpx.post(url, params={"key": api_key}, json=payload, timeout=httpx.Timeout(180.0))
        if resp.status_code in (429, 503) and attempt < retries:
            time.sleep(min(60, 5 * 2**attempt))
            continue
        resp.raise_for_status()
        candidates = resp.json().get("candidates", [])
        if not candidates:
            return ""
        parts = candidates[0].get("content", {}).get("parts", [])
        return "".join(p.get("text", "") for p in parts)
    return ""


def extract_with_gemini(pdf_bytes: bytes, api_key: str, model: str, max_pages: int = 0, dpi: int = 180) -> str:
    """OCR bằng Gemini Flash (rẻ hơn gpt-4o): mỗi trang -> ảnh -> Markdown+LaTeX."""
    out: list[str] = []
    with _open(pdf_bytes) as doc:
        for i in _page_indices(doc.page_count, max_pages):
            out.append(_gemini_page(api_key, model, _render_png_b64(doc[i], dpi)))
    return _PAGE_SEP.join(out)

"""Gọi DeepSeek-V3 để tái cấu trúc text thô thành Markdown sạch + LaTeX.

Dùng endpoint chat completions (tương thích OpenAI) qua httpx. Lỗi 429/timeout
được Airflow xử lý bằng retry + exponential backoff ở tầng task.
"""

import httpx

FORMAT_PROMPT = (
    "Bạn là biên tập viên sách giáo khoa. Dọn dẹp văn bản thô OCR dưới đây:\n"
    "- Tái tạo cấu trúc tiêu đề bằng Markdown (#, ##, ###) theo bài học/mục.\n"
    "- Chuyển MỌI biểu thức toán/công thức sang LaTeX ($...$ inline, $$...$$ block).\n"
    "- Giữ nguyên 100% nội dung kiến thức, TUYỆT ĐỐI không thêm/bịa thông tin.\n"
    "- Chỉ trả về Markdown, không kèm lời dẫn."
)

_TIMEOUT = httpx.Timeout(120.0)


def format_chunk(raw_text: str, api_key: str, api_base: str, model: str) -> str:
    """Gửi một chunk text thô tới DeepSeek, trả về Markdown đã định dạng.

    Raise httpx.HTTPStatusError nếu API trả lỗi (để Airflow retry).
    """
    resp = httpx.post(
        f"{api_base.rstrip('/')}/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "temperature": 0.0,
            "messages": [
                {"role": "system", "content": FORMAT_PROMPT},
                {"role": "user", "content": raw_text},
            ],
        },
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]

"""Đọc đề thi bằng VLM (Qwen3-VL-Flash) — M1 trong docs_vsf/plan_cdi_kg_anchored.md.

Gọi API chat/completions OpenAI-compatible (base64 ảnh → text + LaTeX sạch), thay thế
OCR thô cho phần công thức. User sẽ cấu hình VLM_API_KEY sau; khi chưa có key hoặc gọi
lỗi → nâng `VlmUnavailableError` để pipeline fallback OCR (không chặn code).
"""

from __future__ import annotations

import base64
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

from src.config import Settings, get_settings
from src.observability import logger

_READ_PROMPT = (
    "Đọc đề kiểm tra trong ảnh. Trả về NGUYÊN VĂN nội dung các câu hỏi dạng text; "
    "giữ nguyên công thức toán bằng LaTeX ($...$). Không bình luận, không diễn đạt lại."
)

_TOC_PROMPT = (
    "Đây là một trang của sách giáo khoa. Xác định trang này có phải trang MỤC LỤC (danh sách "
    "chương/bài ở đầu sách) hay không. Trả về CHỈ 1 JSON object (không markdown, không giải thích):\n"
    '{"toc_page": false}\n'
    "Nếu KHÔNG phải trang mục lục.\n"
    '{"toc_page": true, "chapters": [{"name": "Tên chương", "lessons": [{"name": "Tên bài", "kind": "lesson"}]}]}\n'
    "Nếu CÓ. Quy tắc:\n"
    "- Chỉ lấy mục nằm trong MỤC LỤC thật, bỏ số trang, dấu chấm chấm, header/footer.\n"
    "- name giữ NGUYÊN cách viết hoa như trong sách (vd 'Số tự nhiên', 'SỐ NGUYÊN').\n"
    "- Bỏ các mục không phải nội dung học: 'Tên chương', 'Tên bài', 'Lời nói đầu', 'Phụ lục', 'Bảng giải thích thuật ngữ'.\n"
    "- kind = 'phu' cho mục ôn tập/kiểm tra/hoạt động (vd 'Ôn tập chương II', 'Kiểm tra chương II', "
    "'Hoạt động thực hành và trải nghiệm', 'Luyện tập chung', 'Bài tập cuối chương'); kind = 'lesson' cho bài kiến thức.\n"
    "- Nếu trang có nhiều chương, gom tất cả vào chapters; nếu trang chỉ có tiếp bài của chương trước "
    "thì đặt lessons vào chapter cuối cùng hiện có."
)

# Backoff giữa các lần retry khi gặp 5xx/429 thoáng qua từ nhà cung cấp VLM (giây).
_VLM_BACKOFF = (1, 2, 4)


class VlmUnavailableError(Exception):
    """VLM chưa được cấu hình (thiếu key) hoặc không gọi được — caller fallback OCR."""


def is_configured(settings: Settings | None = None) -> bool:
    """VLM có sẵn API base + key chưa (chưa set key → không cấu hình)."""
    s = settings or get_settings()
    return bool(s.vlm_api_base and s.vlm_api_key)


def _format_friendly_vlm_error(exc: Exception, model_name: str) -> str:
    """Chuyển đổi lỗi kỹ thuật từ API VLM (503, 429, timeout, network...) thành thông báo tiếng Việt dễ hiểu."""
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code if exc.response is not None else 0
        if status in (502, 503, 504):
            return f"Máy chủ AI ({model_name}) hiện đang quá tải hoặc tạm thời bảo trì (HTTP {status}). Hệ thống đã tự động thử lại 3 lần nhưng chưa thành công. Vui lòng thử lại sau ít phút."
        if status == 429:
            return f"Đã vượt quá giới hạn tần suất gọi API AI (HTTP 429 - Rate Limit). Vui lòng đợi 1–2 phút rồi thử nạp lại."
        if status in (401, 403):
            return f"Khóa API AI (VLM_API_KEY) không hợp lệ hoặc đã hết hạn (HTTP {status}). Vui lòng kiểm tra lại cấu hình API key."
        return f"Máy chủ AI ({model_name}) phản hồi mã lỗi HTTP {status}. Vui lòng thử lại sau."
    if isinstance(exc, httpx.TimeoutException):
        return f"Thời gian chờ phản hồi từ máy chủ AI ({model_name}) quá lâu (Timeout). File sách có thể quá nặng hoặc đường truyền mạng chập chờn."
    if isinstance(exc, httpx.ConnectError):
        return f"Không thể kết nối đến máy chủ AI ({model_name}). Vui lòng kiểm tra kết nối mạng hoặc đường dẫn API."
    raw = str(exc)
    clean_msg = raw.split("For more information check:")[0].strip()
    return f"Lỗi xử lý AI ({model_name}): {clean_msg}"


def _chat_completions(image_b64: str, settings: Settings, prompt: str | None = None) -> str:
    """Gọi chat/completions với 1 ảnh; trả text. Lỗi mạng/HTTP → VlmUnavailableError.

    5xx (vd 503 nhà cung cấp tạm quá tải) / 429 (rate limit) → retry tối đa 3 lần với
    backoff tăng dần (1s → 2s → 4s) trước khi nâng lỗi — tránh worker fail ngay vì 503 thoáng qua.
    """
    model_name = settings.vlm_model
    url = f"{settings.vlm_api_base.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {settings.vlm_api_key}"}
    payload = {
        "model": model_name,
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

    last_error: Exception | None = None
    for attempt in range(3):
        t0 = time.time()
        print(f"[VLM/Qwen] 🚀 Đang gửi request tới '{model_name}' (lần {attempt + 1}/3)...")
        logger.info("vlm_request_start", model=model_name, url=url, attempt=attempt + 1)
        try:
            resp = httpx.post(url, json=payload, headers=headers, timeout=settings.vlm_timeout_s)
            status = resp.status_code if isinstance(resp.status_code, int) else 0
            duration = time.time() - t0
            transient = status >= 500 or status == 429
            if transient and attempt < 2:
                last_error = httpx.HTTPStatusError(
                    f"Server error {status}", request=resp.request, response=resp
                )
                print(f"[VLM/Qwen] ⚠️ Gặp lỗi tạm thời (HTTP {status}) sau {duration:.2f}s — chuẩn bị retry lần {attempt + 2} sau {_VLM_BACKOFF[attempt]}s...")
                logger.warning(
                    "vlm_transient_retry", model=model_name, status=status, attempt=attempt + 1, duration_s=round(duration, 2), sleep=_VLM_BACKOFF[attempt]
                )
                time.sleep(_VLM_BACKOFF[attempt])
                continue

            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            result_str = content if isinstance(content, str) else str(content)
            print(f"[VLM/Qwen] ✅ Nhận phản hồi thành công từ '{model_name}' (HTTP {status}, {duration:.2f}s, {len(result_str)} ký tự)")
            logger.info("vlm_call_success", model=model_name, status_code=status, duration_s=round(duration, 2), result_len=len(result_str))
            return result_str
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            duration = time.time() - t0
            last_error = exc
            print(f"[VLM/Qwen] ❌ Lỗi gọi '{model_name}' lần {attempt + 1} ({duration:.2f}s): {exc}")
            logger.warning("vlm_call_attempt_error", model=model_name, attempt=attempt + 1, duration_s=round(duration, 2), error=str(exc)[:200])

    friendly_msg = _format_friendly_vlm_error(last_error or Exception("Không nhận được phản hồi"), model_name)
    print(f"[VLM/Qwen] 🛑 Đã thử 3 lần nhưng gọi '{model_name}' thất bại: {friendly_msg}")
    logger.error("vlm_call_failed", model=model_name, error=friendly_msg)
    raise VlmUnavailableError(friendly_msg) from last_error



def read_image_bytes(image_bytes: bytes, settings: Settings | None = None) -> str:
    """Đọc 1 ảnh đề (PNG/JPEG...) bằng VLM → text + LaTeX."""
    s = settings or get_settings()
    if not is_configured(s):
        raise VlmUnavailableError("Thiếu VLM_API_KEY — user sẽ cấu hình sau.")
    return _chat_completions(base64.b64encode(image_bytes).decode("ascii"), s)


def read_pdf_pages(path: Path, settings: Settings | None = None, dpi: int = 150) -> str:
    """Render toàn bộ trang PDF → VLM đọc từng trang SONG SONG (có giới hạn), ghép kết quả."""
    s = settings or get_settings()
    if not is_configured(s):
        raise VlmUnavailableError("Thiếu VLM_API_KEY — user sẽ cấu hình sau.")
    import fitz  # PyMuPDF — đã có trong deps (test_content_difficulty dùng)

    with fitz.open(path) as doc:
        images = [
            base64.b64encode(doc.load_page(i).get_pixmap(dpi=dpi).tobytes("png")).decode("ascii")
            for i in range(doc.page_count)
        ]
    return "\n\n".join(_call_in_parallel(images, s))


def read_pdf_pages_range(
    path: Path,
    start_page: int = 1,
    end_page: int | None = None,
    settings: Settings | None = None,
    dpi: int = 150,
    prompt: str | None = None,
) -> str:
    """Render các trang PDF từ start_page..end_page (1-based) → VLM đọc từng trang SONG SONG, ghép kết quả."""
    s = settings or get_settings()
    if not is_configured(s):
        raise VlmUnavailableError("Thiếu VLM_API_KEY — user sẽ cấu hình sau.")
    import fitz  # PyMuPDF — đã có trong deps (test_content_difficulty dùng)

    with fitz.open(path) as doc:
        end = min(end_page or doc.page_count, doc.page_count)
        images = [
            base64.b64encode(doc.load_page(idx - 1).get_pixmap(dpi=dpi).tobytes("png")).decode("ascii")
            for idx in range(max(1, start_page), end + 1)
        ]
    return "\n\n".join(_call_in_parallel(images, s, prompt))


def read_pdf_toc(
    path: Path, settings: Settings | None = None, max_pages: int = 8, dpi: int = 150
) -> list[str]:
    """Đọc mục lục SGK từ max_pages trang đầu → list text JSON từng trang (VLM nhận diện TOC).

    Mỗi phần tử là response của 1 trang: {"toc_page": false} hoặc
    {"toc_page": true, "chapters": [...]} — caller gom/parse.
    Các trang được gọi SONG SONG (tối đa settings.vlm_max_concurrency, mặc định 4) để rút ngắn
    thời gian job nạp sách — kết quả giữ đúng thứ tự trang.
    """
    s = settings or get_settings()
    if not is_configured(s):
        raise VlmUnavailableError("Thiếu VLM_API_KEY — user sẽ cấu hình sau.")
    import fitz  # PyMuPDF — đã có trong deps

    with fitz.open(path) as doc:
        total_pages_to_check = min(max_pages, doc.page_count)
        print(f"[VLM/Qwen] 📖 Bắt đầu đọc mục lục PDF ({total_pages_to_check}/{doc.page_count} trang đầu) bằng model '{s.vlm_model}' (concurrency={s.vlm_max_concurrency})...")
        logger.info("vlm_pdf_toc_start", total_pages=total_pages_to_check, model=s.vlm_model)
        images = [
            base64.b64encode(doc.load_page(idx).get_pixmap(dpi=dpi).tobytes("png")).decode("ascii")
            for idx in range(total_pages_to_check)
        ]
    return _call_in_parallel(images, s, _TOC_PROMPT)


def _call_in_parallel(
    images: list[str], settings: Settings, prompt: str | None = None
) -> list[str]:
    """Gọi VLM cho nhiều ảnh SONG SONG với số worker giới hạn; giữ thứ tự đầu vào.

    Mỗi ảnh độc lập (không chia sẻ state) nên an toàn với thread pool. Số worker lấy từ
    settings.vlm_max_concurrency — mặc định 4, giữ 3-5 để không dính rate-limit 429/503.
    """
    max_workers = max(1, min(settings.vlm_max_concurrency, len(images)))
    if max_workers <= 1:
        return [_chat_completions(img, settings, prompt) for img in images]
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        return list(pool.map(lambda img: _chat_completions(img, settings, prompt), images))


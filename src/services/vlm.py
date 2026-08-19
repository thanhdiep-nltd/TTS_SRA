"""Đọc đề thi bằng VLM (Qwen3-VL-Flash) — M1 trong docs_vsf/plan_cdi_kg_anchored.md.

Gọi API chat/completions OpenAI-compatible (base64 ảnh → text + LaTeX sạch), thay thế
OCR thô cho phần công thức. User sẽ cấu hình VLM_API_KEY sau; khi chưa có key hoặc gọi
lỗi → nâng `VlmUnavailableError` để pipeline fallback OCR (không chặn code).
"""

from __future__ import annotations

import base64
import time
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from pathlib import Path

import httpx

from src.config import Settings, get_settings
from src.observability import logger

_READ_PROMPT = (
    "Đọc đề kiểm tra trong ảnh. Trả về NGUYÊN VĂN nội dung các câu hỏi dạng text; "
    "giữ nguyên công thức toán bằng LaTeX ($...$). Không bình luận, không diễn đạt lại."
)

# Quét sách giáo khoa: VLM phân loại từng trang (toc/frontmatter/content) và gán trang nội dung về
# ĐƠN VỊ HỌC TẬP (chương/bài/unit/lesson/chủ đề — tùy sách). Quy tắc phân cấp là CẤU TRÚC tổng quát
# (heading đơn vị có thứ tự riêng của sách; đề mục bên trong KHÔNG phải đơn vị mới), KHÔNG liệt kê
# từ khóa môn nào. Mọi trích xuất do VLM làm — không regex/hardcode.
_SCAN_PROMPT = (
    "Đây là các trang của một cuốn SÁCH GIÁO KHOA (mỗi ảnh = 1 trang, theo đúng thứ tự). "
    "Trả về CHỈ 1 JSON object (không markdown, không giải thích):\n"
    '{"pages": [{"kind": "toc"|"frontmatter"|"content", "printed_page": 0, "chapter": "", "lesson": "", "chapters": []}]}\n'
    "với ĐÚNG 1 phần tử cho MỖI ảnh, theo đúng thứ tự ảnh. Quy tắc:\n"
    "- kind: 'toc' nếu trang là MỤC LỤC (danh sách đơn vị học tập ở đầu sách); 'frontmatter' nếu là bìa, "
    "lời nói đầu, hướng dẫn sử dụng, phụ lục, đáp án, bảng thuật ngữ; 'content' nếu là nội dung bài học.\n"
    "- printed_page: số trang in ở đầu/chân trang (0 nếu không thấy).\n"
    "- ĐƠN VỊ HỌC TẬP (chapter/lesson) là chương/bài/unit/lesson/chủ đề/tiết — tùy sách, KHÔNG phải mục con. "
    "Một trang bắt đầu đơn vị mới CHỈ KHI trang có HEADING ĐƠN VỊ: đề mục cấp cao có thứ tự riêng của sách "
    "(dạng 'Bài 1:', 'Unit 3:', 'Chương II:', 'Lesson 2:', 'Topic A:'...). Các đề mục khác (mục con, phần, "
    "hoạt động, bài tập, ví dụ, câu hỏi, thực hành, ghi nhớ...) là NỘI DUNG BÊN TRONG đơn vị — KHÔNG phải "
    "đơn vị mới, vẫn thuộc đơn vị đang đọc. Trang không có heading đơn vị → thuộc đơn vị của trang trước.\n"
    "- Với kind='content': chapter/lesson = tên đơn vị mà trang thuộc về (theo quy tắc trên); "
    "rỗng nếu không xác định. Bỏ số trang, header/footer, tên sách khỏi tên; giữ NGUYÊN cách viết hoa.\n"
    "- Với kind='toc': điền 'chapters': [{\"name\": \"Tên đơn vị học tập cấp lớn (chương/unit/chủ đề)\", "
    "\"page\": <số trang in>, \"lessons\": [{\"name\": \"Tên bài/lesson/mục con\", \"page\": <số trang in>, "
    "\"kind\": \"lesson\"|\"phu\"}]}]. "
    "kind='phu' cho mục ôn tập/kiểm tra/hoạt động thực hành/luyện tập chung/bài tập cuối chương. "
    "BỎ các mục không phải nội dung học: 'Tên chương', 'Tên bài', 'Lời nói đầu', 'Phụ lục', "
    "'Bảng giải thích thuật ngữ'. Bỏ số trang và dấu chấm chấm khỏi name."
)

# Phần bổ sung khi ĐÃ CÓ MỤC LỤC: danh sách neo là QUYỀN LỰC DUY NHẤT xác định đơn vị — VLM chỉ được
# chọn ID từ danh sách, không tự đặt tên → không bao giờ bịa đơn vị mới từ mục con.
_ANCHOR_RULE = (
    "\nĐÂY LÀ DANH SÁCH CÁC ĐƠN VỊ HỌC TẬP (từ MỤC LỤC) — QUYỀN LỰC DUY NHẤT để gán lesson:\n"
    "{anchors}\n"
    "Với kind='content': lesson PHẢI là ID (số) trong danh sách trên, vd '1', '2', ... (copy đúng số, "
    "không tự đặt tên mới). Heading KHÔNG khớp mục nào trong danh sách = mục con → vẫn thuộc đơn vị "
    "đang đọc (giữ lesson của trang trước). Trang đầu không khớp mục nào → lesson rỗng."
)


def scan_prompt_with_anchors(anchors: str) -> str:
    """Prompt quét nội dung có kèm danh sách neo MỤC LỤC — VLM chỉ chọn ID từ danh sách."""
    return _SCAN_PROMPT + _ANCHOR_RULE.format(anchors=anchors)


# Làm giàu 1 bài học: VLM nhìn TOÀN BỘ trang của bài → tóm tắt + từ khóa + mục con theo thứ tự.
# Prompt tổng quát cho MỌI MÔN — không kind taxonomy, không từ khóa môn cụ thể.
_ENRICH_RULES = (
    "Trả về CHỈ 1 JSON object (không markdown, không giải thích):\n"
    '{"summary": "...", "keywords": ["..."], "sections": [{"name": "..."}]}\n'
    "Quy tắc:\n"
    "- summary: 2-4 câu đúc kết NỘI DUNG KIẾN THỨC CỐT LÕI của bài (khái niệm, quy tắc, sự kiện, "
    "cấu trúc, kỹ năng chính...); viết liền mạch như giáo viên tóm tắt bài; công thức (nếu có) giữ LaTeX.\n"
    "- keywords: 4-8 thuật ngữ/khái niệm cốt lõi của bài.\n"
    "- sections: DANH SÁCH các mục con/đề mục xuất hiện trong bài theo đúng thứ tự (tên ngắn gọn); "
    "bài không có mục con rõ ràng → sections: [].\n"
    "- Bỏ header/footer, số trang, tiêu đề lặp lại trang trước. TUYỆT ĐỐI KHÔNG tự ý mở rộng, KHÔNG đưa kiến thức bách khoa toàn thư hay kiến thức ngoài sách vào."
)

_ENRICH_PROMPT = (
    "Đây là các trang của MỘT BÀI HỌC trong sách giáo khoa (mỗi ảnh = 1 trang, theo đúng thứ tự).\n"
    + _ENRICH_RULES
)


def enrich_prompt(lesson_name: str | None = None, chapter_name: str | None = None) -> str:
    """Prompt làm giàu 1 bài — có câu neo tên bài/chương để VLM giữ ngữ cảnh nhất quán.

    Khi biết tên bài (từ MỤC LỤC), đính kèm làm neo: VLM không phải tự đoán bài đang đọc là gì,
    tránh bất nhất giữa các lần gọi (vd mục con 'Thực hành 1' lúc có lúc không).
    """
    if not lesson_name:
        return _ENRICH_PROMPT
    prefix = f"Đây là các trang của bài học '{lesson_name}'"
    if chapter_name:
        prefix += f" thuộc chương '{chapter_name}'"
    return prefix + " (mỗi ảnh = 1 trang, theo đúng thứ tự).\n" + _ENRICH_RULES

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
            return "Đã vượt quá giới hạn tần suất gọi API AI (HTTP 429 - Rate Limit). Vui lòng đợi 1–2 phút rồi thử nạp lại."
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


def _chat_completions(image_b64s: str | list[str], settings: Settings, prompt: str | None = None) -> str:
    """Gọi chat/completions với 1 hoặc NHIỀU ảnh (content array); trả text.

    Lỗi mạng/HTTP → VlmUnavailableError. 5xx (vd 503 nhà cung cấp tạm quá tải) / 429
    (rate limit) → retry tối đa 3 lần với backoff tăng dần (1s → 2s → 4s) trước khi nâng
    lỗi — tránh worker fail ngay vì 503 thoáng qua.
    """
    model_name = settings.vlm_model
    url = f"{settings.vlm_api_base.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {settings.vlm_api_key}"}
    if isinstance(image_b64s, str):
        image_b64s = [image_b64s]
    content: list[dict[str, object]] = [{"type": "text", "text": prompt or _READ_PROMPT}]
    content.extend(
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}} for b64 in image_b64s
    )
    payload = {
        "model": model_name,
        "temperature": 0.1,
        "messages": [
            {
                "role": "user",
                "content": content,
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


def read_book_pages(
    path: Path,
    settings: Settings | None = None,
    dpi: int = 100,
    pages_per_call: int | None = None,
    progress_cb: Callable[[int, int], None] | None = None,
    prompt: str | None = None,
    start_page: int = 0,
    max_pages: int | None = None,
) -> list[str | None]:
    """Quét PDF theo lô (mỗi lô = 1 gọi VLM NHIỀU ảnh) → list JSON thô từng lô.

    Phần tử thứ i = response của lô i (JSON array cho từng trang trong lô); None = lô gọi
    thất bại sau retry (không sập cả lượt quét — caller bỏ qua lô đó). Các lô chạy song
    song với giới hạn settings.vlm_max_concurrency; progress_cb(done_batches, total_batches).

    start_page: bắt đầu từ chỉ số trang này (0-based) — dùng để quét phần NỘI DUNG sau MỤC LỤC.
    max_pages: chỉ quét tối đa N trang (từ start_page) — dùng để tìm MỤC LỤC ở đầu sách.
    prompt: prompt tùy biến (vd có kèm danh sách neo MỤC LỤC qua scan_prompt_with_anchors).
    """
    s = settings or get_settings()
    if not is_configured(s):
        raise VlmUnavailableError("Thiếu VLM_API_KEY — user sẽ cấu hình sau.")
    import fitz  # PyMuPDF — đã có trong deps

    with fitz.open(path) as doc:
        page_count = doc.page_count
        end = min(page_count, start_page + max_pages) if max_pages else page_count
        total_to_scan = max(0, end - start_page)
        print(
            f"[VLM/Qwen] 📖 Quét trang {start_page + 1}–{end} ({total_to_scan} trang) bằng '{s.vlm_model}' "
            f"(lô {s.vlm_sweep_pages_per_call} trang, concurrency={s.vlm_max_concurrency})..."
        )
        logger.info("vlm_book_sweep_start", start=start_page, end=end, model=s.vlm_model)
        images = [
            base64.b64encode(doc.load_page(i).get_pixmap(dpi=dpi).tobytes("png")).decode("ascii")
            for i in range(start_page, end)
        ]

    batch_size = max(1, min(pages_per_call or s.vlm_sweep_pages_per_call, len(images)))
    batches = [images[i : i + batch_size] for i in range(0, len(images), batch_size)]
    total = len(batches)
    results: list[str | None] = [None] * total
    if not batches:
        return results

    scan_prompt = prompt or _SCAN_PROMPT
    max_workers = max(1, min(s.vlm_max_concurrency, total))
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        pending: dict[Future, int] = {}
        next_idx = 0

        def submit(batch_idx: int) -> None:
            pending[pool.submit(_chat_completions, batches[batch_idx], s, scan_prompt)] = batch_idx

        for _ in range(min(max_workers, total)):
            submit(next_idx)
            next_idx += 1

        done_count = 0
        while pending:
            finished, _ = wait(pending, return_when=FIRST_COMPLETED)
            for fut in finished:
                batch_idx = pending.pop(fut)
                try:
                    results[batch_idx] = fut.result()
                except Exception as exc:  # noqa: BLE001 — 1 lô hỏng không hủy cả lượt quét
                    logger.warning("vlm_sweep_batch_failed", batch=batch_idx, error=str(exc)[:200])
                    results[batch_idx] = None
                done_count += 1
                if progress_cb:
                    progress_cb(done_count, total)
            for _ in range(len(finished)):
                if next_idx < total:
                    submit(next_idx)
                    next_idx += 1
    return results


def read_lesson_pages(
    path: Path,
    page_indices: list[int],
    lesson_name: str | None = None,
    chapter_name: str | None = None,
    settings: Settings | None = None,
    dpi: int = 100,
) -> str:
    """Đọc các trang của 1 bài (NHIỀU ảnh/1 request) → JSON {summary, keywords, sections}.

    lesson_name/chapter_name (từ MỤC LỤC) đính vào prompt làm NEO ngữ cảnh — VLM biết bài đang
    đọc là gì → mục con (sections) nhất quán giữa các lần gọi.
    Nâng VlmUnavailableError nếu gọi thất bại sau retry — caller bỏ bài đó + warning.
    """
    s = settings or get_settings()
    if not is_configured(s):
        raise VlmUnavailableError("Thiếu VLM_API_KEY — user sẽ cấu hình sau.")
    import fitz  # PyMuPDF — đã có trong deps

    with fitz.open(path) as doc:
        images = [
            base64.b64encode(doc.load_page(i).get_pixmap(dpi=dpi).tobytes("png")).decode("ascii")
            for i in page_indices
        ]
    return _chat_completions(images, s, enrich_prompt(lesson_name, chapter_name))


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


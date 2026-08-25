"""Đọc đề thi bằng VLM (Qwen3-VL-Flash) — M1 trong docs_vsf/plan_cdi_kg_anchored.md.

Gọi API chat/completions OpenAI-compatible (base64 ảnh → text + LaTeX sạch), thay thế
OCR thô cho phần công thức. User sẽ cấu hình VLM_API_KEY sau; khi chưa có key hoặc gọi
lỗi → nâng `VlmUnavailableError` để pipeline fallback OCR (không chặn code).
"""

from __future__ import annotations

import base64
import io
import json
import re
import time
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, Field

from src.config import Settings, get_settings
from src.observability import logger

_READ_PROMPT = (
    "Đọc đề kiểm tra trong ảnh. Trả về NGUYÊN VĂN nội dung các câu hỏi dạng text; "
    "giữ nguyên công thức toán bằng LaTeX ($...$). Không bình luận, không diễn đạt lại."
)

_EXAM_SEGMENTATION_PROMPT = (
    "Bạn là chuyên gia thị giác máy tính và khảo thí. Nhiệm vụ của bạn là bóc tách toàn bộ đề thi trong ảnh/PDF thành DANH SÁCH TỪNG CÂU HỎI RIÊNG BIỆT.\n\n"
    "QUY TẮC BẮT BUỘC:\n"
    "1. MỖI CÂU HỎI (Câu 1, Câu 2, Câu 3... hoặc Bài 1, Bài 2...) BẮT BUỘC LÀ 1 PHẦN TỬ RIÊNG BIỆT TRONG JSON ARRAY. TUYỆT ĐỐI KHÔNG ĐƯỢC GỘP NHIỀU CÂU VÀO CÙNG 1 PHẦN TỬ.\n"
    "2. has_figure: true NẾU đề bài CÓ IN SẴN hình vẽ hình học (tam giác, tứ giác, hình tròn...), đồ thị, sơ đồ, biểu đồ hoặc tranh ảnh minh họa; false nếu câu hỏi chỉ mô tả bằng chữ (kể cả câu yêu cầu học sinh tự vẽ hình) hoặc chỉ toàn công thức toán thuần túy.\n"
    "3. text: Đọc ĐÚNG NGUYÊN VĂN tiêu đề và nội dung của từng câu trong đề kèm các đáp án A, B, C, D; giữ nguyên công thức toán LaTeX ($...$).\n"
    "4. page_index: chỉ số trang (0 cho trang 1, 1 cho trang 2...).\n\n"
    "ĐỊNH DẠNG ĐẦU RA (CHỈ TRẢ VỀ JSON ARRAY, KHÔNG KÈM TEXT GIẢI THÍCH):\n"
    "[\n"
    "  {\n"
    '    "question_number": 1,\n'
    '    "page_index": 0,\n'
    '    "text": "Câu 1. Để viết tập hợp M... A. ... B. ... C. ... D. ...",\n'
    '    "has_figure": false,\n'
    '    "score_text": null\n'
    "  },\n"
    "  {\n"
    '    "question_number": 6,\n'
    '    "page_index": 0,\n'
    '    "text": "Câu 6. Hãy liệt kê tên của các hình sau... A. ... B. ... C. ... D. ...",\n'
    '    "has_figure": true,\n'
    '    "score_text": null\n'
    "  }\n"
    "]"
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


_TOC_DYNAMIC_TREE_PROMPT = (
    "Bạn là chuyên gia bóc tách cấu trúc Sách Giáo Khoa (SGK). Nhiệm vụ của bạn là đọc các ảnh chụp các trang MỤC LỤC (Table of Contents) "
    "được cung cấp và trích xuất TOÀN BỘ cây danh mục Chương và Bài học xuất hiện trên các trang đó thành 1 JSON object duy nhất.\n\n"
    "QUY TẮC BẮT BUỘC:\n"
    "1. GIỮ NGUYÊN 100% TIÊU ĐỀ ĐẦY ĐỦ: Giữ nguyên số thứ tự (ví dụ 'Bài 1.', 'Bài 11.', 'Unit 3:'), "
    "tên bài và toàn bộ nội dung phụ/mô tả sau dấu ':' (ví dụ 'Hoạt động thực hành và trải nghiệm: Sử dụng máy tính cầm tay'). "
    "TUYỆT ĐỐI KHÔNG ĐƯỢC CẮT BỎ phụ đề hay gộp các bài trùng tên.\n"
    "2. TRÍCH XUẤT CHÍNH XÁC SỐ TRANG IN (page): Lấy số trang in tương ứng ở cột bên phải của từng chương/bài (ví dụ: '... 42' -> 42).\n"
    "3. PHÂN LOẠI kind: 'chinh' cho các bài học lý thuyết/trọng tâm; 'phu' cho ôn tập chương, bài tập cuối chương, thực hành trải nghiệm, kiểm tra.\n"
    "4. BỎ QUA CÁC TRANG KHÔNG PHẢI MỤC LỤC: Nếu trong các ảnh có trang bìa, lời nói đầu, hoặc trang nội dung bài học, chỉ cần bỏ qua và không trích xuất từ các trang đó.\n"
    "5. BỎ CÁC MỤC NGOÀI CHƯƠNG TRÌNH: 'Lời nói đầu', 'Bảng giải thích thuật ngữ', 'Bảng tra cứu', 'Phụ lục'.\n\n"
    "ĐỊNH DẠNG ĐẦU RA (CHỈ TRẢ VỀ 1 JSON OBJECT, KHÔNG KÈM TEXT HAY MARKDOWN):\n"
    "{\n"
    '  "chapters": [\n'
    "    {\n"
    '      "name": "CHƯƠNG I: SỐ TỰ NHIÊN",\n'
    '      "page": 4,\n'
    '      "lessons": [\n'
    '        {"name": "Bài 1. Tập hợp. Phần tử của tập hợp", "page": 4, "kind": "chinh"},\n'
    '        {"name": "Bài 2. Tập hợp số tự nhiên. Ghi số tự nhiên", "page": 9, "kind": "chinh"},\n'
    '        {"name": "Bài 11. Hoạt động thực hành và trải nghiệm: Sử dụng máy tính cầm tay", "page": 42, "kind": "phu"},\n'
    '        {"name": "Bài tập cuối chương I", "page": 45, "kind": "phu"}\n'
    "      ]\n"
    "    }\n"
    "  ]\n"
    "}"
)


def toc_dynamic_tree_prompt() -> str:
    """Prompt trích xuất cấu trúc mục lục dạng cây đệ quy động."""
    return _TOC_DYNAMIC_TREE_PROMPT


def read_toc_pages(
    path: Path,
    page_indices: list[int],
    settings: Settings | None = None,
    dpi: int = 150,
) -> str:
    """Render các trang Mục Lục (TOC) từ PDF → gọi VLM bóc tách cây Chương/Bài kèm số trang in trong 1 request duy nhất."""
    s = settings or get_settings()
    if not is_configured(s):
        raise VlmUnavailableError("Thiếu VLM_API_KEY — user sẽ cấu hình sau.")
    import fitz

    with fitz.open(path) as doc:
        images = [
            base64.b64encode(doc.load_page(i).get_pixmap(dpi=dpi).tobytes("png")).decode("ascii")
            for i in page_indices
            if i < doc.page_count
        ]
    if not images:
        return json.dumps({"chapters": []})
    return _chat_completions(images, s, _TOC_DYNAMIC_TREE_PROMPT)


def _extract_chapters_from_obj(obj: dict[str, Any]) -> list[dict[str, Any]]:
    """Trích xuất và chuẩn hóa danh sách chapters từ dict JSON."""
    chapters_raw = (obj or {}).get("chapters") or (obj or {}).get("units") or []
    if not isinstance(chapters_raw, list):
        return []

    chapters: list[dict[str, Any]] = []
    for ch in chapters_raw:
        if not isinstance(ch, dict):
            continue
        ch_name = str(ch.get("name") or ch.get("title") or "").strip()
        if not ch_name:
            continue
        lessons_raw = ch.get("lessons") or ch.get("children") or []
        lessons: list[dict[str, Any]] = []
        for ls in lessons_raw:
            if not isinstance(ls, dict):
                continue
            ls_name = str(ls.get("name") or ls.get("title") or "").strip()
            if not ls_name:
                continue
            lessons.append(
                {
                    "name": ls_name,
                    "page": ls.get("page") or ls.get("printed_page"),
                    "kind": ls.get("kind", "chinh"),
                }
            )
        chapters.append(
            {
                "name": ch_name,
                "page": ch.get("page") or ch.get("printed_page"),
                "lessons": lessons,
            }
        )
    return chapters



def parse_dynamic_toc_json(raw_text: str) -> list[dict[str, Any]]:
    """Parse JSON cây TOC từ kết quả VLM, tự sửa escape LaTeX và chuẩn hóa cấu trúc."""
    if not raw_text:
        return []
    cleaned = re.sub(r"^`{3}(?:json)?|`{3}$", "", raw_text.strip(), flags=re.MULTILINE).strip()
    start = cleaned.find("{")
    if start < 0:
        return []
    sub_text = cleaned[start:]
    obj: dict[str, Any] | None = None
    try:
        parsed, _ = json.JSONDecoder().raw_decode(sub_text)
        if isinstance(parsed, dict):
            obj = parsed
    except json.JSONDecodeError:
        pass

    if obj is None:
        try:
            fixed = re.sub(r'\\(?![/\\\"bfnrt]|u[0-9a-fA-F]{4})', r'\\\\', sub_text)
            parsed, _ = json.JSONDecoder().raw_decode(fixed)
            if isinstance(parsed, dict):
                obj = parsed
        except json.JSONDecodeError:
            return []

    return _extract_chapters_from_obj(obj or {})


# Làm giàu 1 bài học: VLM nhìn TOÀN BỘ trang của bài → tóm tắt + từ khóa + mục con theo thứ tự.
# Prompt tổng quát cho MỌI MÔN — không kind taxonomy, không từ khóa môn cụ thể.
_ENRICH_RULES = (
    "Trả về CHỈ 1 JSON object (không markdown, không giải thích):\n"
    '{"summary": "...", "keywords": ["..."], "sections": [{"name": "..."}]}\n'
    "Quy tắc bắt buộc:\n"
    "- summary: 2-4 câu đúc kết NỘI DUNG KIẾN THỨC CỐT LÕI của bài (khái niệm, quy tắc, sự kiện, "
    "cấu trúc, kỹ năng chính...); viết liền mạch như giáo viên tóm tắt bài; công thức (nếu có) giữ LaTeX.\n"
    "- keywords: 4-8 thuật ngữ/khái niệm cốt lõi của bài.\n"
    "- sections: DANH SÁCH các mục con/đề mục xuất hiện trong bài theo đúng thứ tự (tên ngắn gọn); "
    "bài không có mục con rõ ràng → sections: [].\n"
    "- PHẠM VI TIÊU ĐỀ: Bắt đầu tóm tắt từ tiêu đề chính to đậm của bài học. Nếu trang đầu có chứa phần bài tập hoặc đề mục của bài học trước, HÃY BỎ QUA hoàn toàn phần đó.\n"
    "- TRUNG THỰC HỌC THUẬT: Chỉ tóm tắt những gì thực sự xuất hiện trên các trang ảnh. TUYỆT ĐỐI KHÔNG tự ý suy diễn, phóng đại hoặc bịa đặt số liệu thống kê/sự kiện đời sống ngoài sách."
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

def _retry_batch_single_pages(
    path: Path,
    page_indices: list[int],
    settings: Settings,
    prompt: str | None = None,
    dpi: int = 100,
) -> str | None:
    """Fallback khi cả 1 lô VLM fail: thử lại TỪNG TRANG riêng lẻ.

    Render lại PDF, gửi mỗi lần 1 ảnh → VLM trả page JSON.
    Trang nào vẫn lỗi → dict rỗng {} — không làm mất các trang khỏe.
    Trả về JSON string giống batch gốc {"pages": [...]} để parse_into xử lý đồng nhất.
    """
    import fitz  # PyMuPDF — đã có trong deps

    results: list[dict[str, Any]] = []
    with fitz.open(path) as doc:
        for idx in page_indices:
            if idx >= doc.page_count:
                results.append({})
                continue
            try:
                img_b64 = base64.b64encode(
                    doc.load_page(idx).get_pixmap(dpi=dpi).tobytes("png")
                ).decode("ascii")
                raw = _chat_completions(img_b64, settings, prompt)
            except VlmUnavailableError:
                # Single page vẫn fail — ghi {} thay vì mất trang khỏe
                results.append({})
                logger.warning("vlm_single_page_retry_failed", page=idx)
                continue
            # Parse single-page response: {"pages": [{...}]} hoặc trực tiếp {"kind": "...", ...}
            obj = _parse_single_page_json(raw) if raw else None
            if obj and isinstance(obj.get("pages"), list) and obj["pages"]:
                page = obj["pages"][0] if isinstance(obj["pages"][0], dict) else {}
            elif obj and isinstance(obj, dict) and ("kind" in obj or "chapter" in obj or "chapters" in obj or "printed_page" in obj):
                page = obj
            else:
                page = {}
            results.append(page)
    if not results:
        return None
    return json.dumps({"pages": results}, ensure_ascii=False)


def _parse_single_page_json(text: str) -> dict[str, Any] | None:
    """Parse JSON từ VLM response 1 trang (handle code fences, LaTeX escapes)."""
    cleaned = re.sub(r"^`{3}(?:json)?|`{3}$", "", text.strip(), flags=re.MULTILINE).strip()
    start = cleaned.find("{")
    if start < 0:
        return None
    sub_text = cleaned[start:]
    try:
        obj, _ = json.JSONDecoder().raw_decode(sub_text)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass

    try:
        fixed_text = re.sub(r'\\(?![/\\\"bfnrt]|u[0-9a-fA-F]{4})', r'\\\\', sub_text)
        obj, _ = json.JSONDecoder().raw_decode(fixed_text)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        return None


# Backoff giữa các lần retry khi gặp 5xx/429 thoáng qua từ nhà cung cấp VLM (giây).
_VLM_BACKOFF = (1, 2, 4)


class VlmUnavailableError(Exception):
    """VLM chưa được cấu hình (thiếu key) hoặc không gọi được — caller fallback OCR."""


def resolve_vlm_config(settings: Settings | None = None) -> tuple[str, str, str, str]:
    """Phân giải cấu hình VLM theo provider đã chọn trong settings (mặc định VLM_PROVIDER='qwen').

    Trả về: (provider_name, model_name, api_base, api_key).
    """
    s = settings or get_settings()
    provider = (getattr(s, "vlm_provider", "qwen") or "qwen").lower()

    if provider == "openrouter":
        api_base = getattr(s, "openrouter_api_base", "https://openrouter.ai/api/v1") or "https://openrouter.ai/api/v1"
        api_key = getattr(s, "openrouter_api_key", "") or s.vlm_api_key
        model = getattr(s, "openrouter_vlm_model", "google/gemini-3.7-flash") or "google/gemini-3.7-flash"
        return "OpenRouter", model, api_base, api_key

    if provider in ("qwen", "dashscope", "shopaikey"):
        api_base = getattr(s, "qwen_vlm_api_base", "https://direct.shopaikey.com/v1") or s.vlm_api_base or "https://direct.shopaikey.com/v1"
        api_key = getattr(s, "qwen_vlm_api_key", "") or s.vlm_api_key
        model = getattr(s, "qwen_vlm_model", "qwen3-vl-flash") or s.vlm_model or "qwen3-vl-flash"
        return "Qwen", model, api_base, api_key

    if provider == "openai":
        api_base = getattr(s, "openai_api_base", "https://api.openai.com/v1") or "https://api.openai.com/v1"
        api_key = getattr(s, "openai_api_key", "") or s.vlm_api_key
        model = getattr(s, "openai_vlm_model", "gpt-4o-mini") or "gpt-4o-mini"
        return "OpenAI", model, api_base, api_key

    # Custom / fallback trực tiếp theo vlm_model & vlm_api_base & vlm_api_key
    return "Custom", s.vlm_model, s.vlm_api_base, s.vlm_api_key


def is_configured(settings: Settings | None = None) -> bool:
    """VLM có sẵn API base + key chưa (chưa set key → không cấu hình)."""
    s = settings or get_settings()
    _, _, api_base, api_key = resolve_vlm_config(s)
    return bool(api_base and api_key)


def _format_friendly_vlm_error(exc: Exception, model_name: str) -> str:
    """Chuyển đổi lỗi kỹ thuật từ API VLM (503, 429, timeout, network...) thành thông báo tiếng Việt dễ hiểu."""
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code if exc.response is not None else 0
        if status in (502, 503, 504):
            return f"Máy chủ AI ({model_name}) hiện đang quá tải hoặc tạm thời bảo trì (HTTP {status}). Hệ thống đã tự động thử lại 3 lần nhưng chưa thành công. Vui lòng thử lại sau ít phút."
        if status == 429:
            return "Đã vượt quá giới hạn tần suất gọi API AI (HTTP 429 - Rate Limit). Vui lòng đợi 1–2 phút rồi thử nạp lại."
        if status in (401, 403):
            return f"Khóa API AI ({model_name}) không hợp lệ hoặc đã hết hạn (HTTP {status}). Vui lòng kiểm tra lại cấu hình API key."
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
    provider_name, model_name, api_base, api_key = resolve_vlm_config(settings)
    url = f"{api_base.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"}
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
        print(f"[VLM/{provider_name}] -> Dang gui request toi '{model_name}' (lan {attempt + 1}/3)...")
        logger.info("vlm_request_start", provider=provider_name, model=model_name, url=url, attempt=attempt + 1)
        try:
            resp = httpx.post(url, json=payload, headers=headers, timeout=settings.vlm_timeout_s)
            status = resp.status_code if isinstance(resp.status_code, int) else 0
            duration = time.time() - t0
            transient = status >= 500 or status == 429
            if transient and attempt < 2:
                last_error = httpx.HTTPStatusError(
                    f"Server error {status}", request=resp.request, response=resp
                )
                print(f"[VLM/{provider_name}] [RETRY] Gap loi tam thoi (HTTP {status}) sau {duration:.2f}s -- chuan bi retry lan {attempt + 2} sau {_VLM_BACKOFF[attempt]}s...")
                logger.warning(
                    "vlm_transient_retry", provider=provider_name, model=model_name, status=status, attempt=attempt + 1, duration_s=round(duration, 2), sleep=_VLM_BACKOFF[attempt]
                )
                time.sleep(_VLM_BACKOFF[attempt])
                continue

            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            result_str = content if isinstance(content, str) else str(content)
            print(f"[VLM/{provider_name}] [OK] Nhan phan hoi thanh cong tu '{model_name}' (HTTP {status}, {duration:.2f}s, {len(result_str)} ky tu)")
            logger.info("vlm_call_success", provider=provider_name, model=model_name, status_code=status, duration_s=round(duration, 2), result_len=len(result_str))
            return result_str
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            duration = time.time() - t0
            last_error = exc
            print(f"[VLM/{provider_name}] [ERROR] Loi goi '{model_name}' lan {attempt + 1} ({duration:.2f}s): {exc}")
            logger.warning("vlm_call_attempt_error", provider=provider_name, model=model_name, attempt=attempt + 1, duration_s=round(duration, 2), error=str(exc)[:200])

    friendly_msg = _format_friendly_vlm_error(last_error or Exception("Không nhận được phản hồi"), model_name)
    print(f"[VLM/{provider_name}] [FAILED] Da thu 3 lan nhung goi '{model_name}' that bai: {friendly_msg}")
    logger.error("vlm_call_failed", provider=provider_name, model=model_name, error=friendly_msg)
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
        if hasattr(doc, "page_count") and hasattr(doc, "load_page"):
            images = [
                base64.b64encode(doc.load_page(i).get_pixmap(dpi=dpi).tobytes("png")).decode("ascii")
                for i in range(doc.page_count)
            ]
        else:
            images = [
                base64.b64encode(page.get_pixmap(dpi=dpi).tobytes("png")).decode("ascii")
                for page in doc
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
            f"[VLM/Qwen] Quet trang {start_page + 1}-{end} ({total_to_scan} trang) bang '{s.vlm_model}' "
            f"(lo {s.vlm_sweep_pages_per_call} trang, concurrency={s.vlm_max_concurrency})..."
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
                except Exception as exc:  # noqa: BLE001 — 1 lô hỏng → retry từng trang thay vì vứt cả lô
                    logger.warning("vlm_sweep_batch_failed", batch=batch_idx, error=str(exc)[:200])
                    # Retry từng trang riêng lẻ — chỉ mất trang nào thực sự lỗi, không cả 5
                    try:
                        page_offset = batch_idx * batch_size
                        page_indices = list(range(
                            start_page + page_offset,
                            min(start_page + page_offset + batch_size, end)
                        ))
                        fallback = _retry_batch_single_pages(path, page_indices, s, scan_prompt, dpi)
                        results[batch_idx] = fallback if fallback else None
                    except Exception:  # noqa: BLE001
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

    def _invoke(img: str) -> str:
        if prompt is not None:
            return _chat_completions(img, settings, prompt)
        return _chat_completions(img, settings)

    if max_workers <= 1:
        return [_invoke(img) for img in images]
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        return list(pool.map(_invoke, images))


class SegmentedQuestion(BaseModel):
    """1 câu hỏi độc lập được bóc tách từ đề thi kèm tọa độ vùng ảnh và cờ hình học."""

    question_number: int
    page_index: int = 0
    box_2d: list[int | float] | None = None
    text: str
    score_text: str | None = None
    has_figure: bool = False
    image_data_url: str | None = None
    cropped_bytes: bytes | None = None


def _parse_json_from_response(raw: str) -> Any:
    """Bóc tách JSON array/object an toàn từ kết quả LLM/VLM."""
    text = raw.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        text = match.group(1).strip()
    try:
        return json.loads(text)
    except Exception:
        arr_match = re.search(r"(\[[\s\S]*\])", text)
        if arr_match:
            try:
                return json.loads(arr_match.group(1))
            except Exception:
                pass
        obj_match = re.search(r"(\{[\s\S]*\})", text)
        if obj_match:
            try:
                return json.loads(obj_match.group(1))
            except Exception:
                pass
        raise





def _split_compound_items(raw_items: list[dict]) -> list[dict]:
    """
    Tự động kiểm tra và phân tách các phần tử bị LLM gộp nhiều câu (ví dụ 'Câu 1... Câu 2...').
    Đảm bảo 100% mỗi câu hỏi là 1 item độc lập, kể cả khi VLM trả về gộp chung.
    """
    clean_items: list[dict] = []

    for item in raw_items:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()
        if not text:
            continue

        # Tìm các mốc câu hỏi: "Câu 1.", "Câu 2:", "Bài 1.", "Bài 2:"
        pattern = r"(?:^|[\n\r]|(?:\.\s+)|(?:\;\s+)|(?:\s{2,}))(?:Câu|Bài|Question)\s*(\d+)[\.\:\s]"
        matches = list(re.finditer(pattern, text, flags=re.IGNORECASE))

        if len(matches) <= 1:
            clean_items.append(item)
            continue

        has_figure = bool(item.get("has_figure", False))
        box = item.get("box_2d") or item.get("figure_box_2d")

        if has_figure and isinstance(box, (list, tuple)) and len(box) >= 4:
            b_xmin, b_ymin, b_xmax, b_ymax = float(box[0]), float(box[1]), float(box[2]), float(box[3])
        else:
            b_xmin, b_ymin, b_xmax, b_ymax = 0.0, 0.0, 1000.0, 1000.0

        total_len = max(1, len(text))
        n_matches = len(matches)

        for i, match in enumerate(matches):
            start_idx = match.start()
            if text[start_idx] in "\n\r. ;":
                sub_m = re.search(r"(?:Câu|Bài|Question)", text[start_idx:], flags=re.IGNORECASE)
                if sub_m:
                    start_idx += sub_m.start()

            end_idx = matches[i + 1].start() if i + 1 < n_matches else len(text)
            sub_text = text[start_idx:end_idx].strip()
            if not sub_text:
                continue

            try:
                q_num = int(match.group(1))
            except Exception:
                q_num = i + 1

            if has_figure and box:
                frac_start = start_idx / total_len
                frac_end = end_idx / total_len
                sub_ymin = int(round(b_ymin + (b_ymax - b_ymin) * frac_start))
                sub_ymax = int(round(b_ymin + (b_ymax - b_ymin) * frac_end))
                sub_box = [int(round(b_xmin)), sub_ymin, int(round(b_xmax)), sub_ymax]
            else:
                sub_box = None

            if has_figure and n_matches > 1:
                # Chỉ giữ cờ has_figure cho câu con có chứa từ khóa liên quan đến hình ảnh/đồ thị
                sub_has_figure = bool(
                    re.search(
                        r"hình|đồ thị|sơ đồ|biểu đồ|bảng|vẽ|minh họa|figure|diagram|chart",
                        sub_text,
                        re.IGNORECASE,
                    )
                )
            else:
                sub_has_figure = has_figure

            sub_item = {
                **item,
                "question_number": q_num,
                "text": sub_text,
                "has_figure": sub_has_figure,
                "box_2d": None,
            }
            clean_items.append(sub_item)

    return clean_items


def segment_exam_questions(
    path: Path,
    file_type: Any = None,
    settings: Settings | None = None,
    dpi: int = 150,
) -> list[SegmentedQuestion]:
    """Gửi các trang đề thi vào VLM để bóc tách danh sách câu hỏi & dùng DocLayout-YOLO cắt ảnh chuẩn xác."""
    s = settings or get_settings()
    if not is_configured(s):
        raise VlmUnavailableError("Thiếu VLM_API_KEY — user sẽ cấu hình sau.")

    import fitz
    from PIL import Image
    from src.services import layout_detector

    file_ext = path.suffix.lower()
    is_pdf = file_ext == ".pdf" or (file_type and "pdf" in str(file_type).lower())

    questions: list[SegmentedQuestion] = []

    if is_pdf:
        with fitz.open(path) as doc:
            page_count = doc.page_count
            if page_count == 0:
                return []
            page_pils: list[Image.Image] = []
            images_b64: list[str] = []
            for i in range(page_count):
                pix = doc.load_page(i).get_pixmap(dpi=dpi)
                pix_bytes = pix.tobytes("png")
                images_b64.append(base64.b64encode(pix_bytes).decode("ascii"))
                page_pils.append(Image.open(io.BytesIO(pix_bytes)))

            raw_response = _chat_completions(images_b64, s, prompt=_EXAM_SEGMENTATION_PROMPT)
            try:
                parsed = _parse_json_from_response(raw_response)
            except Exception as exc:
                logger.warning("Không parse được JSON segmentation từ VLM: %s", exc)
                return []

            if not isinstance(parsed, list):
                if isinstance(parsed, dict) and "questions" in parsed and isinstance(parsed["questions"], list):
                    parsed = parsed["questions"]
                else:
                    parsed = [parsed]

            parsed = _split_compound_items(parsed)

            for idx, item in enumerate(parsed):
                if not isinstance(item, dict):
                    continue
                q_num = item.get("question_number", idx + 1)
                try:
                    q_num = int(q_num)
                except Exception:
                    q_num = idx + 1
                try:
                    p_idx = int(item.get("page_index", 0))
                except Exception:
                    p_idx = 0
                p_idx = max(0, min(page_count - 1, p_idx))
                q_text = str(item.get("text", "")).strip()
                if not q_text:
                    continue
                score_text = item.get("score_text")
                has_figure = bool(item.get("has_figure", False))

                questions.append(
                    SegmentedQuestion(
                        question_number=q_num,
                        page_index=p_idx,
                        box_2d=None,
                        text=q_text,
                        score_text=score_text,
                        has_figure=has_figure,
                        image_data_url=None,
                        cropped_bytes=None,
                    )
                )

            # Tự động phát hiện layout bằng DocLayout-YOLO và gán ảnh hình vẽ chuẩn xác 100%
            questions = layout_detector.associate_figures_to_questions(page_pils, questions)

    else:
        # File ảnh đơn lẻ
        data = path.read_bytes()
        img_b64 = base64.b64encode(data).decode("ascii")
        raw_response = _chat_completions(img_b64, s, prompt=_EXAM_SEGMENTATION_PROMPT)
        try:
            parsed = _parse_json_from_response(raw_response)
        except Exception as exc:
            logger.warning("Không parse được JSON segmentation từ VLM cho ảnh: %s", exc)
            return []

        if not isinstance(parsed, list):
            if isinstance(parsed, dict) and "questions" in parsed and isinstance(parsed["questions"], list):
                parsed = parsed["questions"]
            else:
                parsed = [parsed]

        parsed = _split_compound_items(parsed)
        pil_img = Image.open(io.BytesIO(data))

        for idx, item in enumerate(parsed):
            if not isinstance(item, dict):
                continue
            q_num = item.get("question_number", idx + 1)
            try:
                q_num = int(q_num)
            except Exception:
                q_num = idx + 1
            q_text = str(item.get("text", "")).strip()
            if not q_text:
                continue
            score_text = item.get("score_text")
            has_figure = bool(item.get("has_figure", False))

            questions.append(
                SegmentedQuestion(
                    question_number=q_num,
                    page_index=0,
                    box_2d=None,
                    text=q_text,
                    score_text=score_text,
                    has_figure=has_figure,
                    image_data_url=None,
                    cropped_bytes=None,
                )
            )

        # Tự động phát hiện layout bằng DocLayout-YOLO và gán ảnh hình vẽ chuẩn xác 100%
        questions = layout_detector.associate_figures_to_questions([pil_img], questions)

    return questions


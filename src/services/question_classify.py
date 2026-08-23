"""Công cụ test 1 câu hỏi: ảnh/PDF → VLM đọc text → LLM map vào cây chương/bài SGK.

Không trạng thái (không ghi DB, không tạo exam_papers) — tái dùng pipeline map của
content_difficulty (map_items → rejudge_null_items → _expand_mapped) để giữ cùng ngữ
nghĩa với phân tích độ khó đề thi (TEVI/CDI): shortlist = cây curriculum_units active
theo (môn, khối), node lạ bị loại, không khớp → off_curriculum + node gợi ý.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from src.models.enums import FileType
from src.models.tables import CurriculumUnit
from src.schemas.question_classify import ClassifiedItem, QuestionClassifyResult
from src.services import content_difficulty, curriculum_catalog, vlm

logger = logging.getLogger(__name__)

# Giả định 1 câu hỏi đơn nằm trong tối đa 3 trang PDF (tránh cost khi dán nhầm đề dài).
_MAX_PDF_PAGES = 3
_MAX_CANDIDATES = 3


def extract_question_text(path: Path, file_type: FileType) -> str:
    """Đọc nội dung 1 câu hỏi từ file (ảnh hoặc PDF) bằng VLM — giữ LaTeX công thức.

    Nâng VlmUnavailableError nếu VLM chưa cấu hình/lỗi — endpoint chuyển thành 503
    với message thân thiện. Loại file khác → ValueError (endpoint trả 400).
    """
    if file_type == FileType.IMAGE:
        return vlm.read_image_bytes(path.read_bytes())
    if file_type == FileType.PDF:
        import fitz  # PyMuPDF — đã có trong deps

        with fitz.open(path) as doc:
            end = min(doc.page_count, _MAX_PDF_PAGES)
        return vlm.read_pdf_pages_range(path, start_page=1, end_page=end)
    raise ValueError("Chỉ hỗ trợ ảnh hoặc PDF cho câu hỏi đơn.")


def resolve_shortlist(db: Session, subject_code: str, grade: int, semester_number: int | None = None) -> list[CurriculumUnit]:
    """Lọc cây chương/bài active của (môn, khối, học kỳ) → shortlist node cho LLM map.

    ValueError với message tiếng Việt rõ ràng khi môn/khối chưa có trong
    s360.dim_subject hoặc chưa nạp SGK — endpoint chuyển thành 422.
    """
    subject_ids = curriculum_catalog.resolve_subject_ids(db, subject_code, [grade])
    subject_id = subject_ids.get(grade)
    if subject_id is None:
        raise ValueError(f"Môn {subject_code.upper()} khối {grade} chưa có trong danh mục môn học.")
    units = content_difficulty.build_shortlist(db, subject_id, grade, semester_number=semester_number)
    if not units:
        sem_str = f" học kỳ {semester_number}" if semester_number else ""
        raise ValueError(f"Môn {subject_code.upper()} khối {grade}{sem_str} chưa nạp SGK — hãy nạp sách trước.")
    return units


def _merge_resolved(
    resolved: list[content_difficulty.ResolvedCompetency],
    mapped: list[content_difficulty.MappedItem],
) -> list[ClassifiedItem]:
    """Gộp các ý cùng unit (cộng weight), sắp theo weight giảm dần; confidence lấy từ MappedItem."""
    by_topic = {item.topic: item for item in mapped}
    groups: dict[int, dict[str, Any]] = {}
    for r in resolved:
        if r.unit_id is None:
            continue
        g = groups.setdefault(r.unit_id, {"item": r, "weight": 0.0})
        g["weight"] += r.weight
    total_w = sum(g["weight"] for g in groups.values())
    scale = (1.0 / total_w) if total_w > 0.0 else 1.0

    sorted_groups = sorted(groups.values(), key=lambda gv: -gv["weight"])
    items: list[ClassifiedItem] = []
    for idx, g in enumerate(sorted_groups):
        item_w = round(min(1.0, g["weight"] * scale), 4)
        m_item = by_topic.get(g["item"].topic)
        items.append(
            ClassifiedItem(
                topic=g["item"].topic,
                chapter=g["item"].chapter,
                lesson=g["item"].lesson,
                unit_code=g["item"].unit_code,
                unit_name=g["item"].unit_name,
                bloom_level=g["item"].bloom_level,
                weight=item_w,
                question_share=item_w,
                is_primary=(idx == 0 or item_w >= 0.5),
                confidence=m_item.confidence if m_item is not None else None,
                reason=m_item.reason if m_item is not None else g["item"].reason,
                excerpt=g["item"].excerpt,
            )
        )
    return items


def classify_question(
    text: str, shortlist: list[CurriculumUnit], llm: Any | None = None
) -> QuestionClassifyResult:
    """Map 1 câu hỏi (text) vào cây chương/bài — kết quả cấu trúc cho UI.

    Text quá ngắn (< ngưỡng pipeline đề) hoặc LLM không parse được → matched=False;
    rejudge 1 lần cho ý không khớp node; không khớp → off_curriculum + node gợi ý.
    """
    items = content_difficulty.map_items(text, shortlist, llm)
    if not items:
        return QuestionClassifyResult(
            text=text,
            matched=False,
            off_curriculum=True,
            items=[],
            candidates=[u.name for u in shortlist[:_MAX_CANDIDATES]],
        )
    items = content_difficulty.rejudge_null_items(items, shortlist, llm)
    resolved = content_difficulty._expand_mapped(items, shortlist)
    resolved, items = content_difficulty._normalize_resolved(resolved, items)
    classified = _merge_resolved(resolved, items)
    matched = bool(classified)
    return QuestionClassifyResult(
        text=text,
        matched=matched,
        off_curriculum=not matched,
        items=classified,
        candidates=[] if matched else [u.name for u in shortlist[:_MAX_CANDIDATES]],
    )

"""Nạp sách giáo khoa (PDF/DOCX/TXT) → tự tách mục lục → node chương/bài — KHÔNG RAG.

M5 mở rộng: thay vì người dùng tự tổng hợp file JSON/markdown, upload chính cuốn SGK;
pipeline đọc TOC (bookmark PDF → text-layer → VLM fallback) và sinh node curriculum_units.
Hỗ trợ dry_run (xem trước cây dự kiến trước khi ghi DB).
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.tables import CurriculumUnit
from src.services import vlm
from src.services.curriculum_catalog import deactivate_placeholder_units, resolve_subject_ids

_TMP_DIR = Path(__file__).resolve().parents[2] / "temp"

_CHAPTER_RE = re.compile(r"^\s*Chương\s+([IVXLCDM]+|\d+)\s*[.:]?\s*(.+)$", re.IGNORECASE)
_LESSON_RE = re.compile(r"^\s*Bài\s+(\d+)\s*[.:]?\s*(.+)$", re.IGNORECASE)
_SEMESTER_RE = re.compile(r"(?:tập|tap|hk)\s*([12])", re.IGNORECASE)

TocEntry = tuple[int, str, int]  # (level: 1=chương, 2=bài, page)


def detect_semester_from_filename(filename: str) -> int | None:
    """Đoán học kỳ từ tên file ("tap 1"/"tập 2"/"HK1") → 1 hoặc 2; None nếu không rõ."""
    match = _SEMESTER_RE.search(filename)
    if not match:
        return None
    return int(match.group(1))


def extract_toc_from_text(text: str) -> list[TocEntry]:
    """Dò dòng "Chương I: Tên" / "Bài 1: Tên" trong text → TOC entries (không cần page chính xác)."""
    entries: list[TocEntry] = []
    for idx, line in enumerate(text.splitlines()):
        line = line.strip()
        chapter = _CHAPTER_RE.match(line)
        if chapter:
            entries.append((1, chapter.group(2).strip(), idx))
            continue
        lesson = _LESSON_RE.match(line)
        if lesson:
            entries.append((2, lesson.group(2).strip(), idx))
    return entries


def extract_toc_from_pdf(content: bytes) -> tuple[list[TocEntry], str]:
    """Trích TOC từ PDF: bookmark (get_toc) → text-layer regex → VLM. Trả (entries, source)."""
    import fitz  # PyMuPDF

    with fitz.open(stream=content, filetype="pdf") as doc:
        toc = doc.get_toc()
        if toc:
            entries = [(int(level), title.strip(), page) for level, title, page in toc if int(level) <= 2]
            if entries:
                return entries, "pdf-bookmark"
        text_parts: list[str] = []
        for page in doc:
            text_parts.append(page.get_text())
    entries = extract_toc_from_text("\n".join(text_parts))
    if entries:
        return entries, "pdf-text"

    if vlm.is_configured():
        _TMP_DIR.mkdir(parents=True, exist_ok=True)
        tmp = _TMP_DIR / f"toc_{uuid.uuid4().hex}.pdf"
        tmp.write_bytes(content)
        try:
            raw = vlm.read_pdf_toc(tmp)
        except vlm.VlmUnavailableError:
            raw = ""  # VLM lỗi (mạng/key/provider 5xx) → degrade, không làm 500
        finally:
            tmp.unlink(missing_ok=True)
        entries = extract_toc_from_text(raw)
        if entries:
            return entries, "pdf-vlm"
    return [], "pdf"


def extract_toc_from_docx(content: bytes) -> list[TocEntry]:
    """Trích TOC từ DOCX bằng heading styles (Heading 1 = chương, Heading 2 = bài)."""
    import docx

    document = docx.Document(__import__("io").BytesIO(content))
    entries: list[TocEntry] = []
    for idx, para in enumerate(document.paragraphs):
        style = (para.style.name if para.style else "") or ""
        if style.lower().startswith("heading"):
            level = 1 if "1" in style else 2
            if para.text.strip():
                entries.append((level, para.text.strip(), idx))
    return entries


def _dedupe(entries: list[TocEntry]) -> list[TocEntry]:
    """Bỏ trùng tên chương/bài (TOC lặp giữa các trang)."""
    seen: set[tuple[int, str]] = set()
    result: list[TocEntry] = []
    for level, title, page in entries:
        key = (level, title)
        if key in seen:
            continue
        seen.add(key)
        result.append((level, title, page))
    return result


def build_unit_specs_from_toc(
    entries: list[TocEntry],
    subject_code: str,
    grade: int,
    semester: int | None,
    include_lessons: bool,
) -> list[dict[str, Any]]:
    """Chuyển TOC entries → spec curriculum_units: chương C1.., bài con {chương}_B{n} (parent_code)."""
    specs: list[dict[str, Any]] = []
    chapter_index = 0
    lesson_index = 0
    current_chapter_code: str | None = None
    prefix = f"{subject_code.upper()}{grade}"
    for level, title, _page in entries:
        if level == 1:
            chapter_index += 1
            lesson_index = 0
            current_chapter_code = f"{prefix}_C{chapter_index}"
            specs.append(
                {
                    "code": current_chapter_code,
                    "name": title,
                    "semester_number": semester,
                    "parent_code": None,
                }
            )
            continue
        if not include_lessons or current_chapter_code is None:
            continue
        lesson_index += 1
        specs.append(
            {
                "code": f"{current_chapter_code}_B{lesson_index}",
                "name": title,
                "semester_number": semester,
                "parent_code": current_chapter_code,
            }
        )
    return specs


def upsert_unit_tree(
    db: Session, specs: list[dict[str, Any]], subject_id: int, grade: int
) -> tuple[int, int]:
    """Upsert chương trước, rồi bài con gắn parent_id theo parent_code. Trả (inserted, updated)."""
    inserted = updated = 0
    code_to_id: dict[str, int] = {}
    for spec in specs:
        unit = db.execute(
            select(CurriculumUnit).where(
                CurriculumUnit.subject_id == subject_id,
                CurriculumUnit.grade_number == grade,
                CurriculumUnit.code == spec["code"],
            )
        ).scalars().first()
        parent_id = code_to_id.get(spec["parent_code"]) if spec["parent_code"] else None
        if unit is None:
            unit = CurriculumUnit(
                subject_id=subject_id,
                grade_number=grade,
                code=spec["code"],
                name=spec["name"],
                semester_number=spec["semester_number"],
                parent_id=parent_id,
            )
            db.add(unit)
            inserted += 1
        else:
            unit.name = spec["name"]
            unit.semester_number = spec["semester_number"]
            unit.parent_id = parent_id
            unit.is_active = True
            updated += 1
        db.flush()
        code_to_id[spec["code"]] = unit.id
    db.commit()
    return inserted, updated


def save_catalog_from_preview(
    db: Session,
    chapters: list[dict[str, Any]],
    subject_code: str,
    grade: int,
    semester: int | None = None,
) -> dict[str, Any]:
    """Lưu cây chương/bài (đã trích xuất ở bước dry_run) thẳng vào curriculum_units.

    KHÔNG trích lại file, KHÔNG gọi VLM — upsert theo code đã xem trước (idempotent).
    """
    specs: list[dict[str, Any]] = []
    for chapter in chapters:
        code = chapter["code"]
        specs.append(
            {
                "code": code,
                "name": chapter["name"],
                "semester_number": chapter.get("semester_number") or semester,
                "parent_code": None,
            }
        )
        for lesson in chapter.get("lessons", []):
            specs.append(
                {
                    "code": lesson["code"],
                    "name": lesson["name"],
                    "semester_number": chapter.get("semester_number") or semester,
                    "parent_code": code,
                }
            )
    if not specs:
        raise ValueError("Không có chương nào để lưu.")
    subject_ids = resolve_subject_ids(db, subject_code, [grade])
    subject_id = subject_ids.get(grade)
    if subject_id is None:
        raise ValueError(f"Không có s360.dim_subject cho {subject_code.upper()}_{grade} — nạp môn trước.")
    inserted, updated = upsert_unit_tree(db, specs, subject_id, grade)
    hidden = deactivate_placeholder_units(db)
    return {
        "subject_code": subject_code.upper(),
        "grade": grade,
        "semester": semester,
        "source": "preview",
        "chapters": chapters,
        "inserted": inserted,
        "updated": updated,
        "hidden_placeholders": hidden,
        "dry_run": False,
    }


def _extract(content: bytes, filename: str) -> tuple[list[TocEntry], str]:
    """Chọn extractor theo đuôi file → (entries, source). Nâng ValueError khi không trích được."""
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        entries, source = extract_toc_from_pdf(content)
    elif ext == ".docx":
        entries, source = extract_toc_from_docx(content), "docx"
    elif ext in (".txt", ".md"):
        text = content.decode("utf-8", errors="replace")
        entries, source = extract_toc_from_text(text), "text"
    else:
        raise ValueError(f"Định dạng không hỗ trợ: {ext} (chỉ PDF/DOCX/TXT/MD)")
    return _dedupe(entries), source


def ingest_book(
    db: Session,
    filename: str,
    content: bytes,
    subject_code: str,
    grade: int,
    semester: int | None = None,
    include_lessons: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Nạp sách → tách TOC → (dry_run: preview | thật: upsert curriculum_units). KHÔNG RAG."""
    entries, source = _extract(content, filename)
    if not entries:
        raise ValueError(
            "Không trích được mục lục: sách không có bookmark/text-layer và VLM đọc thất bại "
            "(mạng hoặc provider tạm lỗi). Hãy thử lại sau, hoặc dùng file PDF có bookmark "
            "hoặc file mục lục JSON/markdown."
        )
    if semester is None:
        semester = detect_semester_from_filename(filename)
    specs = build_unit_specs_from_toc(entries, subject_code, grade, semester, include_lessons)
    chapters = [
        {
            "code": spec["code"],
            "name": spec["name"],
            "semester_number": spec["semester_number"],
            "lessons": [
                {"code": child["code"], "name": child["name"]}
                for child in specs
                if child["parent_code"] == spec["code"]
            ],
        }
        for spec in specs
        if spec["parent_code"] is None
    ]
    if dry_run:
        return {
            "subject_code": subject_code.upper(),
            "grade": grade,
            "semester": semester,
            "source": source,
            "chapters": chapters,
            "inserted": 0,
            "updated": 0,
            "hidden_placeholders": 0,
            "dry_run": True,
        }

    subject_ids = resolve_subject_ids(db, subject_code, [grade])
    subject_id = subject_ids.get(grade)
    if subject_id is None:
        raise ValueError(f"Không có s360.dim_subject cho {subject_code.upper()}_{grade} — nạp môn trước.")
    inserted, updated = upsert_unit_tree(db, specs, subject_id, grade)
    hidden = deactivate_placeholder_units(db)
    return {
        "subject_code": subject_code.upper(),
        "grade": grade,
        "semester": semester,
        "source": source,
        "chapters": chapters,
        "inserted": inserted,
        "updated": updated,
        "hidden_placeholders": hidden,
        "dry_run": False,
    }

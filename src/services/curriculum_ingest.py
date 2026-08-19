"""Nạp sách giáo khoa (PDF/DOCX/TXT/MD) → tự tách mục lục → node chương/bài — KHÔNG RAG.

M5 mở rộng: thay vì người dùng tự tổng hợp file JSON/markdown, upload chính cuốn SGK.

- PDF: đi thẳng Qwen3-VL-Flash (VLM-thuần) — VLM nhìn ảnh trang mục lục và xuất JSON cấu trúc
  (chương → bài, kind lesson/phu). KHÔNG dùng bookmark/regex (nguồn gây lẫn ruột sách).
- DOCX: heading styles (Heading 1 = chương, Heading 2 = bài).
- TXT/MD: regex dòng "Chương X:" / "Bài n:" (mục lục tay — user kiểm soát nội dung).

Mọi nguồn đều qua chuẩn hóa (_normalize_title), lọc placeholder (_is_placeholder),
gắn cờ phụ (_is_phu_title) và sanity-check (_sanity_check) trước khi preview/lưu.
Hỗ trợ dry_run (xem trước cây dự kiến trước khi ghi DB).
"""

from __future__ import annotations

import json
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
_TRAILING_PAGE_RE = re.compile(r"[\s.…]+\d{1,3}[\s.…]*$")

# Placeholder xuất hiện trong bản mẫu/template sách — loại hẳn.
_PLACEHOLDER_RE = re.compile(
    r"^(tên chương|tên bài|tên mục|tên hoạt động|tên thực hành|tên luyện tập|tên đề mục|tên phần)$",
    re.IGNORECASE,
)
# Node phụ (giữ trong cây nhưng loại khỏi shortlist map đề thi).
_PHU_TITLE_RE = re.compile(
    r"^(ôn tập|kiểm tra|hoạt động thực hành|luyện tập chung|bài tập cuối|tổng kết chương|câu hỏi ôn tập)",
    re.IGNORECASE,
)

_TOC_SCAN_PAGES = 8
_MAX_CHAPTERS_PER_SEMESTER = 6
_MAX_LESSONS_PER_CHAPTER = 30

TocEntry = tuple[int, str, int]  # (level: 1=chương, 2=bài, page)


def detect_semester_from_filename(filename: str) -> int | None:
    """Đoán học kỳ từ tên file ("tap 1"/"tập 2"/"HK1") → 1 hoặc 2; None nếu không rõ."""
    match = _SEMESTER_RE.search(filename)
    if not match:
        return None
    return int(match.group(1))


def _normalize_title(title: str) -> str:
    """Bỏ số trang cuối dòng + dấu chấm chấm; trim. Giữ nguyên cách viết hoa của sách."""
    return _TRAILING_PAGE_RE.sub("", title).strip(" .…:").strip()


def _is_placeholder(title: str) -> bool:
    """True nếu là placeholder bản mẫu (Tên chương/Tên bài...) → loại hẳn."""
    return bool(_PLACEHOLDER_RE.match(title.strip()))


def _is_phu_title(title: str) -> bool:
    """True nếu là node phụ (Ôn tập chương/Kiểm tra/Hoạt động thực hành...) → gắn cờ is_phu."""
    return bool(_PHU_TITLE_RE.match(title.strip()))


def _parse_toc_json(text: str) -> dict[str, Any] | None:
    """Parse JSON object từ text VLM (bóc code fence, lấy object đầu tiên). None nếu hỏng."""
    cleaned = re.sub(r"^`{3}(?:json)?|`{3}$", "", text.strip(), flags=re.MULTILINE).strip()
    start = cleaned.find("{")
    if start < 0:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(cleaned[start:])
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def _merge_toc_chapters(parsed_pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Gom kết quả từng trang VLM → danh sách chương (gộp trang TOC trải nhiều trang)."""
    chapters: list[dict[str, Any]] = []
    for page in parsed_pages:
        if not page.get("toc_page"):
            continue
        for ch in page.get("chapters", []) or []:
            name = _normalize_title(str(ch.get("name", "")))
            if not name or _is_placeholder(name):
                continue
            if chapters and chapters[-1]["name"] == name:
                target = chapters[-1]  # trang sau lặp lại tên chương → gộp bài
            else:
                target = {"name": name, "is_phu": _is_phu_title(name), "lessons": []}
                chapters.append(target)
            for lesson in ch.get("lessons", []) or []:
                lesson_name = _normalize_title(str(lesson.get("name", "")))
                if not lesson_name or _is_placeholder(lesson_name):
                    continue
                kind = lesson.get("kind")
                target["lessons"].append(
                    {
                        "name": lesson_name,
                        "is_phu": kind == "phu" or _is_phu_title(lesson_name),
                    }
                )
    return chapters


def extract_toc_from_pdf(content: bytes) -> tuple[list[dict[str, Any]], str]:
    """Trích TOC bằng VLM-thuần: render ảnh N trang đầu → VLM nhận diện mục lục + xuất JSON cây."""
    if not vlm.is_configured():
        raise ValueError("Cần cấu hình VLM_API_KEY để nạp sách PDF — VLM là bắt buộc cho luồng này.")
    _TMP_DIR.mkdir(parents=True, exist_ok=True)
    tmp = _TMP_DIR / f"toc_{uuid.uuid4().hex}.pdf"
    tmp.write_bytes(content)
    try:
        pages = vlm.read_pdf_toc(tmp)
    except vlm.VlmUnavailableError as exc:
        raise ValueError(f"VLM đọc mục lục thất bại: {exc}") from exc
    finally:
        tmp.unlink(missing_ok=True)
    parsed = [obj for obj in (_parse_toc_json(page) for page in pages) if obj]
    return _merge_toc_chapters(parsed), "pdf-vlm"


def extract_toc_from_text(text: str) -> list[TocEntry]:
    """Dò dòng "Chương X: Tên" / "Bài n: Tên" trong text → TOC entries (dùng cho TXT/MD tay)."""
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


def _entries_to_chapters(entries: list[TocEntry]) -> list[dict[str, Any]]:
    """Chuyển TocEntry (level/title) → chapters dict; chuẩn hóa + tag phụ + loại placeholder."""
    chapters: list[dict[str, Any]] = []
    for level, title, _page in entries:
        name = _normalize_title(title)
        if not name or _is_placeholder(name):
            continue
        if level == 1:
            chapters.append({"name": name, "is_phu": _is_phu_title(name), "lessons": []})
        elif chapters:
            chapters[-1]["lessons"].append({"name": name, "is_phu": _is_phu_title(name)})
    return chapters


def _sanity_check(chapters: list[dict[str, Any]]) -> list[str]:
    """Cảnh báo bất thường (số chương/bài vượt ngưỡng, trùng tên) — không chặn, chỉ cảnh báo."""
    warnings: list[str] = []
    if len(chapters) > _MAX_CHAPTERS_PER_SEMESTER:
        warnings.append(
            f"Phát hiện {len(chapters)} chương — nhiều hơn mức thường gặp cho 1 học kỳ "
            f"({_MAX_CHAPTERS_PER_SEMESTER}); kiểm tra xem có lẫn nội dung ruột sách không."
        )
    for ch in chapters:
        if len(ch["lessons"]) > _MAX_LESSONS_PER_CHAPTER:
            warnings.append(
                f"Chương '{ch['name']}' có {len(ch['lessons'])} bài — nhiều hơn mức bình thường; kiểm tra lại."
            )
    names = [ch["name"] for ch in chapters]
    if len(set(names)) != len(names):
        warnings.append("Có chương trùng tên — kiểm tra lại trước khi lưu.")
    return warnings


def build_unit_specs_from_chapters(
    chapters: list[dict[str, Any]],
    subject_code: str,
    grade: int,
    semester: int | None,
    include_lessons: bool,
) -> list[dict[str, Any]]:
    """Chuyển chapters → spec curriculum_units: chương C1.., bài con {chương}_B{n} (parent_code)."""
    specs: list[dict[str, Any]] = []
    # subject_code có thể đã gắn khối (TOAN_6, TOAN_7...) từ dropdown 24 môn — nếu hậu tố
    # khớp grade thì bỏ để code node gọn (TOAN6_C1 thay vì TOAN_66_C1).
    base = subject_code.upper().strip()
    if base.endswith(f"_{grade}"):
        base = base[: -len(f"_{grade}")]
    prefix = f"{base}{grade}"
    for idx, ch in enumerate(chapters, start=1):
        code = f"{prefix}_C{idx}"
        specs.append(
            {
                "code": code,
                "name": ch["name"],
                "semester_number": semester,
                "parent_code": None,
                "is_phu": ch.get("is_phu", False),
            }
        )
        if not include_lessons:
            continue
        for jdx, lesson in enumerate(ch.get("lessons", []), start=1):
            specs.append(
                {
                    "code": f"{code}_B{jdx}",
                    "name": lesson["name"],
                    "semester_number": semester,
                    "parent_code": code,
                    "is_phu": lesson.get("is_phu", False),
                }
            )
    return specs


def upsert_unit_tree(
    db: Session,
    specs: list[dict[str, Any]],
    subject_id: int,
    grade: int,
    book_id: int | None = None,
) -> tuple[int, int]:
    """Upsert chương trước, rồi bài con gắn parent_id theo parent_code. Trả (inserted, updated).

    book_id (nếu có) sẽ gắn vào từng node để biết cuốn SGK nguồn.
    """
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
                is_phu=spec.get("is_phu", False),
                book_id=book_id,
            )
            db.add(unit)
            inserted += 1
        else:
            unit.name = spec["name"]
            unit.semester_number = spec["semester_number"]
            unit.parent_id = parent_id
            unit.is_phu = spec.get("is_phu", False)
            unit.is_active = True
            if book_id is not None:
                unit.book_id = book_id
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
    book_id: int | None = None,
) -> dict[str, Any]:
    """Lưu cây chương/bài (đã trích xuất ở bước dry_run) thẳng vào curriculum_units.

    KHÔNG trích lại file, KHÔNG gọi VLM — upsert theo code đã xem trước (idempotent).
    book_id (nếu có) gắn vào node để biết cuốn SGK nguồn.
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
                "is_phu": chapter.get("is_phu", False),
            }
        )
        for lesson in chapter.get("lessons", []):
            specs.append(
                {
                    "code": lesson["code"],
                    "name": lesson["name"],
                    "semester_number": chapter.get("semester_number") or semester,
                    "parent_code": code,
                    "is_phu": lesson.get("is_phu", False),
                }
            )
    if not specs:
        raise ValueError("Không có chương nào để lưu.")
    subject_ids = resolve_subject_ids(db, subject_code, [grade])
    subject_id = subject_ids.get(grade)
    if subject_id is None:
        raise ValueError(f"Không có s360.dim_subject cho {subject_code.upper()}_{grade} — nạp môn trước.")
    inserted, updated = upsert_unit_tree(db, specs, subject_id, grade, book_id=book_id)
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
        "warnings": [],
        "dry_run": False,
        "book_id": book_id,
    }


def _extract(content: bytes, filename: str) -> tuple[list[dict[str, Any]], str]:
    """Chọn extractor theo đuôi file → (chapters, source). PDF = VLM-thuần bắt buộc."""
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return extract_toc_from_pdf(content)
    if ext == ".docx":
        return _entries_to_chapters(extract_toc_from_docx(content)), "docx"
    if ext in (".txt", ".md"):
        text = content.decode("utf-8", errors="replace")
        return _entries_to_chapters(extract_toc_from_text(text)), "text"
    raise ValueError(f"Định dạng không hỗ trợ: {ext} (chỉ PDF/DOCX/TXT/MD)")


def ingest_book(
    db: Session,
    filename: str,
    content: bytes,
    subject_code: str,
    grade: int,
    semester: int | None = None,
    include_lessons: bool = False,
    dry_run: bool = False,
    book_id: int | None = None,
) -> dict[str, Any]:
    """Nạp sách → tách TOC → (dry_run: preview | thật: upsert curriculum_units). KHÔNG RAG."""
    chapters, source = _extract(content, filename)
    if not chapters:
        raise ValueError(
            "Không trích được mục lục: không tìm thấy trang MỤC LỤC trong "
            f"{_TOC_SCAN_PAGES} trang đầu (PDF cần VLM hoạt động; nếu là DOCX/TXT hãy kiểm tra cấu trúc). "
            "Hãy thử lại, hoặc dùng file mục lục JSON/markdown."
        )
    if semester is None:
        semester = detect_semester_from_filename(filename)
    warnings = _sanity_check(chapters)
    specs = build_unit_specs_from_chapters(chapters, subject_code, grade, semester, include_lessons)
    preview_chapters = [
        {
            "code": spec["code"],
            "name": spec["name"],
            "semester_number": spec["semester_number"],
            "is_phu": spec["is_phu"],
            "lessons": [
                {"code": child["code"], "name": child["name"], "is_phu": child["is_phu"]}
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
            "chapters": preview_chapters,
            "inserted": 0,
            "updated": 0,
            "hidden_placeholders": 0,
            "warnings": warnings,
            "dry_run": True,
        }

    subject_ids = resolve_subject_ids(db, subject_code, [grade])
    subject_id = subject_ids.get(grade)
    if subject_id is None:
        raise ValueError(f"Không có s360.dim_subject cho {subject_code.upper()}_{grade} — nạp môn trước.")
    inserted, updated = upsert_unit_tree(db, specs, subject_id, grade, book_id=book_id)
    hidden = deactivate_placeholder_units(db)
    return {
        "subject_code": subject_code.upper(),
        "grade": grade,
        "semester": semester,
        "source": source,
        "chapters": preview_chapters,
        "inserted": inserted,
        "updated": updated,
        "hidden_placeholders": hidden,
        "warnings": warnings,
        "dry_run": False,
    }

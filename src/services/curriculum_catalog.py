"""Nạp catalog chuẩn chương trình (bảng phẳng curriculum_units) — KHÔNG RAG.

Dùng cho API admin (src/api/v1/curriculum.py) và service ingest sách
(src/services/curriculum_ingest.py). M0/M5 trong docs_vsf/plan_cdi_kg_anchored.md:
bảng phẳng = bộ xương chương trình (chương/bài) — LLM map câu hỏi đề thi vào đây;
KHÔNG đi qua Qdrant/Airflow (RAG chỉ dành cho chat hỏi đáp SGK).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from sqlalchemy import delete, or_, select, text, update
from sqlalchemy.orm import Session

from src.models.tables import (
    AssignmentCompetency,
    CurriculumBook,
    CurriculumUnit,
    ExamCompetency,
    Misconception,
    QuestionItem,
    StudentKnowledgeGap,
)

_GRADE_RE = re.compile(r"^##\s*.*?LỚP\s*(\d+)")
_SEMESTER_RE = re.compile(r"^###\s*.*?Tập\s*(\d+)")
_CHAPTER_RE = re.compile(r"^\*\s*\*\*Chương\s+[IVXLCDM]+\s*:\s*(.+?)\*\*\s*$")
_DESC_RE = re.compile(r"^\s{2,}\*\s*(.+)$")


def parse_markdown_catalog(text_content: str, subject_code: str) -> dict[str, Any]:
    """Parse mục lục SGK dạng markdown → catalog dict.

    Format (vd docs/Chuong_Trinh_Toan_Canh_Dieu_6_9.md):
      "## ... LỚP 6" → khối; "### Tập 1" → học kỳ;
      "* **Chương I: Tên**" → chương; "  * Mô tả..." → mô tả.
    Code sinh theo THỨ TỰ chương trong khối (C1, C2, ...) — không phụ thuộc số La Mã.
    """
    grades: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    pending: dict[str, Any] | None = None
    semester = 1
    chapter_index = 0
    for line in text_content.splitlines():
        match = _GRADE_RE.match(line)
        if match:
            if pending is not None and current is not None:
                current["chapters"].append(pending)  # flush chương cuối của khối trước
                pending = None
            if current:
                grades.append(current)
            current = {"grade": int(match.group(1)), "chapters": []}
            semester = 1
            chapter_index = 0
            continue
        if current is None:
            continue
        match = _SEMESTER_RE.match(line)
        if match:
            semester = int(match.group(1))
            continue
        match = _CHAPTER_RE.match(line)
        if match:
            if pending:
                current["chapters"].append(pending)
            chapter_index += 1
            pending = {
                "code": f"{subject_code.upper()}{current['grade']}_C{chapter_index}",
                "name": match.group(1).strip(),
                "semester": semester,
                "description": None,
            }
            continue
        match = _DESC_RE.match(line)
        if match and pending is not None and not pending.get("description"):
            pending["description"] = match.group(1).strip()
    if pending:
        current["chapters"].append(pending)
    if current:
        grades.append(current)
    return {"subject_code": subject_code.upper(), "grades": grades}


def parse_catalog_upload(filename: str, content: str, subject_code: str) -> tuple[dict[str, Any], str]:
    """Phân tích file upload mục lục → (catalog, source). JSON hoặc markdown. KHÔNG RAG."""
    ext = Path(filename).suffix.lower()
    if ext == ".json":
        data = json.loads(content)
        if not data.get("grades"):
            raise ValueError("JSON catalog không có mục 'grades'.")
        data["subject_code"] = subject_code.upper()
        return data, "json"
    data = parse_markdown_catalog(content, subject_code)
    if not data["grades"]:
        raise ValueError("Không tìm thấy cấu trúc '## ... LỚP ...' — định dạng markdown mục lục không hợp lệ.")
    return data, "markdown"


def build_unit_specs(data: dict[str, Any], subject_id_by_grade: dict[int, int]) -> list[dict[str, Any]]:
    """Chuyển catalog thành spec dòng CurriculumUnit; bỏ khối chưa có subject_id."""
    specs: list[dict[str, Any]] = []
    for grade in data["grades"]:
        grade_number = int(grade["grade"])
        subject_id = subject_id_by_grade.get(grade_number)
        if subject_id is None:
            continue
        for chapter in grade["chapters"]:
            specs.append(
                {
                    "subject_id": subject_id,
                    "grade_number": grade_number,
                    "code": chapter["code"],
                    "name": chapter["name"],
                    "description": chapter.get("description"),
                    "semester_number": int(chapter["semester"]),
                    "parent_id": None,
                }
            )
    return specs


def resolve_subject_ids(db: Session, subject_code: str, grades: list[int]) -> dict[int, int]:
    """Tra s360.dim_subject theo code f"{subject_code}_{grade}" → {grade: subject_id}.

    Môn Toán mock v4 lưu theo khối (TOAN_6, TOAN_7...); môn đơn mã (VAN, LY, KHTN...)
    lưu code không hậu tố — fallback sang code gốc khi không có dạng gắn khối.
    """
    result: dict[int, int] = {}
    code = subject_code.upper().strip()
    for grade in grades:
        row = db.execute(
            text("SELECT id FROM s360.dim_subject WHERE code = :code"), {"code": f"{code}_{grade}"}
        ).first()
        if row is None:
            row = db.execute(
                text("SELECT id FROM s360.dim_subject WHERE code = :code"), {"code": code}
            ).first()
        if row is not None:
            result[grade] = int(row[0])
    return result


def upsert_units(db: Session, specs: list[dict[str, Any]]) -> tuple[int, int]:
    """Upsert curriculum_units theo (subject_id, grade_number, code); trả (inserted, updated)."""
    inserted = updated = 0
    for spec in specs:
        unit = db.execute(
            select(CurriculumUnit).where(
                CurriculumUnit.subject_id == spec["subject_id"],
                CurriculumUnit.grade_number == spec["grade_number"],
                CurriculumUnit.code == spec["code"],
            )
        ).scalars().first()
        if unit is None:
            db.add(CurriculumUnit(**spec))
            inserted += 1
        else:
            unit.name = spec["name"]
            unit.description = spec["description"]
            unit.semester_number = spec["semester_number"]
            unit.parent_id = None
            unit.is_active = True
            updated += 1
    db.commit()
    return inserted, updated


def get_or_create_book(
    db: Session,
    subject_code: str,
    grade: int,
    semester: int | None,
    title: str,
    filename: str | None = None,
    source: str | None = None,
    created_by: int | None = None,
) -> int:
    """Get cuốn SGK theo (subject_id, grade, semester, title) — nếu chưa có thì tạo; trả book_id.

    Dùng khi commit nạp sách: mỗi node chương/bài gắn book_id vào cuốn này.
    title rỗng → fallback tên file (để luôn có cuốn theo dõi nguồn gốc).
    """
    subject_ids = resolve_subject_ids(db, subject_code, [grade])
    subject_id = subject_ids.get(grade)
    if subject_id is None:
        raise ValueError(f"Không có s360.dim_subject cho {subject_code.upper()}_{grade} — nạp môn trước.")
    book_title = (title or "").strip() or (filename or "SGK".title())
    book = db.execute(
        select(CurriculumBook).where(
            CurriculumBook.subject_id == subject_id,
            CurriculumBook.grade_number == grade,
            CurriculumBook.semester_number == semester,
            CurriculumBook.title == book_title,
        )
    ).scalars().first()
    if book is None:
        book = CurriculumBook(
            title=book_title,
            subject_code=subject_code.upper(),
            subject_id=subject_id,
            grade_number=grade,
            semester_number=semester,
            filename=filename,
            source=source,
            created_by=created_by,
        )
        db.add(book)
        db.flush()
    return book.id


def deactivate_placeholder_units(db: Session) -> int:
    """Ẩn unit placeholder cũ (code UNIT_% từ mock generator) khỏi picker/shortlist — G6.3."""
    rows = db.execute(
        select(CurriculumUnit).where(CurriculumUnit.code.like("UNIT_%"), CurriculumUnit.is_active.is_(True))
    ).scalars().all()
    for unit in rows:
        unit.is_active = False
    db.commit()
    return len(rows)

def delete_book_and_units(db: Session, book_id: int) -> dict[str, Any]:
    """Xóa 1 cuốn SGK và toàn bộ node chương/bài thuộc cuốn đó (kèm dọn dẹp liên kết)."""
    book = db.get(CurriculumBook, book_id)
    if book is None:
        raise ValueError(f"Cuốn sách id={book_id} không tồn tại.")

    unit_ids = [
        int(uid)
        for uid in db.execute(
            select(CurriculumUnit.id).where(CurriculumUnit.book_id == book_id)
        ).scalars().all()
    ]

    if unit_ids:
        # Xóa các ràng buộc ngoại phụ thuộc nếu có
        db.execute(delete(ExamCompetency).where(ExamCompetency.unit_id.in_(unit_ids)))
        db.execute(delete(StudentKnowledgeGap).where(StudentKnowledgeGap.unit_id.in_(unit_ids)))
        db.execute(delete(AssignmentCompetency).where(AssignmentCompetency.unit_id.in_(unit_ids)))
        db.execute(delete(QuestionItem).where(QuestionItem.unit_id.in_(unit_ids)))
        db.execute(delete(Misconception).where(Misconception.unit_id.in_(unit_ids)))

        # Gỡ liên kết parent_id để tránh lỗi self-referencing foreign key
        db.execute(
            update(CurriculumUnit)
            .where(or_(CurriculumUnit.book_id == book_id, CurriculumUnit.parent_id.in_(unit_ids)))
            .values(parent_id=None)
        )

        # Xóa toàn bộ curriculum_units thuộc book_id
        db.execute(
            delete(CurriculumUnit).where(
                or_(CurriculumUnit.book_id == book_id, CurriculumUnit.id.in_(unit_ids))
            )
        )

    title = book.title
    db.delete(book)
    db.commit()

    return {
        "book_id": book_id,
        "title": title,
        "deleted_units_count": len(unit_ids),
    }



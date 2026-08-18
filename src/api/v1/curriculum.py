"""API admin quản lý catalog chuẩn chương trình (bảng phẳng curriculum_units) — KHÔNG RAG.

M5 bổ sung: xem cây chương/bài, upload mục lục (JSON/markdown) ghi thẳng vào
curriculum_units, bật/tắt node (ẩn khỏi shortlist của LLM map). Chỉ ADMIN.
Dữ liệu này KHÔNG đi qua Qdrant/Airflow — RAG chỉ dành cho chat hỏi đáp SGK.
"""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session

from src.api.deps import get_db, require_roles
from src.models import enums
from src.models.tables import CurriculumUnit
from src.schemas.curriculum import BookIngestResult, CurriculumUnitRead, CurriculumUploadResult
from src.services import curriculum_catalog, curriculum_ingest

router = APIRouter(
    prefix="/curriculum",
    tags=["Curriculum Catalog (phẳng)"],
    dependencies=[Depends(require_roles(enums.UserRole.ADMIN, enums.UserRole.PRINCIPAL, enums.UserRole.SUBJECT_HEAD))],
)


def _subject_ids(db: Session, subject_code: str) -> list[int]:
    """Danh sách s360.dim_subject.id theo mã môn (vd TOAN → TOAN_6..TOAN_12)."""
    rows = db.execute(
        text("SELECT id FROM s360.dim_subject WHERE code LIKE :prefix"), {"prefix": f"{subject_code.upper()}_%"}
    ).fetchall()
    return [int(row.id) for row in rows]


@router.get("/units", response_model=list[CurriculumUnitRead])
def list_units(
    subject_code: str,
    grade: int | None = None,
    semester: int | None = None,
    include_inactive: bool = False,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """Danh sách node chương/bài (có parent_name) theo môn/khối/học kỳ."""
    subject_ids = _subject_ids(db, subject_code)
    if not subject_ids:
        return []
    stmt = select(CurriculumUnit).where(CurriculumUnit.subject_id.in_(subject_ids))
    if grade is not None:
        stmt = stmt.where(CurriculumUnit.grade_number == grade)
    if semester in (1, 2):
        stmt = stmt.where(
            or_(CurriculumUnit.semester_number.is_(None), CurriculumUnit.semester_number == semester)
        )
    if not include_inactive:
        stmt = stmt.where(CurriculumUnit.is_active.is_(True))
    units = list(db.execute(stmt.order_by(CurriculumUnit.grade_number, CurriculumUnit.code)).scalars().all())

    parent_ids = {u.parent_id for u in units if u.parent_id is not None}
    parents: dict[int, CurriculumUnit] = {}
    if parent_ids:
        parents = {
            p.id: p
            for p in db.execute(select(CurriculumUnit).where(CurriculumUnit.id.in_(parent_ids))).scalars()
        }
    return [
        CurriculumUnitRead(
            id=u.id,
            code=u.code,
            name=u.name,
            grade_number=u.grade_number,
            semester_number=u.semester_number,
            parent_id=u.parent_id,
            parent_name=parents[u.parent_id].name if u.parent_id in parents else None,
            is_active=u.is_active,
            description=u.description,
        )
        for u in units
    ]


@router.post("/upload", response_model=CurriculumUploadResult)
def upload_catalog(
    file: Annotated[UploadFile, File()],
    subject_code: Annotated[str, Form()],
    db: Annotated[Session, Depends(get_db)] = None,
):
    """Upload mục lục chương trình (JSON hoặc markdown) → ghi thẳng curriculum_units. KHÔNG RAG."""
    content = file.file.read().decode("utf-8", errors="replace")
    data, source = curriculum_catalog.parse_catalog_upload(file.filename or "", content, subject_code)
    grades = [int(grade["grade"]) for grade in data["grades"]]
    subject_ids = curriculum_catalog.resolve_subject_ids(db, data["subject_code"], grades)
    specs = curriculum_catalog.build_unit_specs(data, subject_ids)
    inserted, updated = curriculum_catalog.upsert_units(db, specs)
    hidden = curriculum_catalog.deactivate_placeholder_units(db)
    return CurriculumUploadResult(
        subject_code=data["subject_code"],
        source=source,
        grades=grades,
        inserted=inserted,
        updated=updated,
        hidden_placeholders=hidden,
    )


@router.post("/ingest-book", response_model=BookIngestResult)
def ingest_book(
    file: Annotated[UploadFile, File()],
    subject_code: Annotated[str, Form()],
    grade: Annotated[int, Form()],
    semester: Annotated[int | None, Form()] = None,
    include_lessons: Annotated[bool, Form()] = False,
    dry_run: Annotated[bool, Form()] = False,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """Nạp sách giáo khoa (PDF/DOCX/TXT/MD) → tự tách mục lục → node chương/bài. KHÔNG RAG.

    dry_run=true chỉ xem trước cây dự kiến (không ghi DB) — UI hiển thị rồi mới lưu thật.
    """
    content = file.file.read()
    try:
        result = curriculum_ingest.ingest_book(
            db,
            file.filename or "book.pdf",
            content,
            subject_code,
            grade,
            semester=semester,
            include_lessons=include_lessons,
            dry_run=dry_run,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return BookIngestResult(**result)


@router.post("/ingest-book/commit", response_model=BookIngestResult)
def commit_book_catalog(
    catalog: Annotated[str, Form()],
    subject_code: Annotated[str, Form()],
    grade: Annotated[int, Form()],
    semester: Annotated[int | None, Form()] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """Lưu cây chương/bài đã xem trước (dry_run) thẳng vào curriculum_units — KHÔNG trích lại/VLM.

    `catalog` = JSON string cây trả về từ POST /curriculum/ingest-book (dry_run=true).
    """
    try:
        chapters = json.loads(catalog)
        if not isinstance(chapters, list):
            raise ValueError("catalog phải là JSON array các chương.")
        result = curriculum_ingest.save_catalog_from_preview(db, chapters, subject_code, grade, semester)
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return BookIngestResult(**result)


@router.post("/units/{unit_id}/toggle-active", response_model=CurriculumUnitRead)
def toggle_unit_active(unit_id: int, db: Annotated[Session, Depends(get_db)] = None):
    """Bật/tắt node (ẩn khỏi shortlist LLM map) — không xóa (giữ tham chiếu exam_competencies)."""
    unit = db.get(CurriculumUnit, unit_id)
    if unit is None:
        raise HTTPException(status_code=404, detail="Node chương trình không tồn tại")
    unit.is_active = not unit.is_active
    db.commit()
    return CurriculumUnitRead(
        id=unit.id,
        code=unit.code,
        name=unit.name,
        grade_number=unit.grade_number,
        semester_number=unit.semester_number,
        parent_id=unit.parent_id,
        is_active=unit.is_active,
        description=unit.description,
    )

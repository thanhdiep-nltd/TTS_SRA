"""API admin quản lý catalog chuẩn chương trình (bảng phẳng curriculum_units) — KHÔNG RAG.

M5 bổ sung: xem cây chương/bài, upload mục lục (JSON/markdown) ghi thẳng vào
curriculum_units, bật/tắt node (ẩn khỏi shortlist của LLM map). Chỉ ADMIN.
Dữ liệu này KHÔNG đi qua Qdrant/Airflow — RAG chỉ dành cho chat hỏi đáp SGK.

Hàng đợi nạp sách giáo khoa: DB-backed (bảng curriculum_ingest_jobs, giống ews_pipeline_jobs),
worker src/services/curriculum_job_worker.py chạy 1 job/lúc theo FIFO. POST /ingest-book tạo
job (202) + lưu file tạm; frontend poll /ingest-book/jobs/{id}; /ingest-book/jobs trả Lịch sử.
"""

import json
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session

from src.api.deps import get_current_user, get_db, require_roles
from src.models import enums
from src.models.tables import CurriculumBook, CurriculumIngestJob, CurriculumUnit, User
from src.schemas.curriculum import (
    BookIngestJobRead,
    BookIngestResult,
    CurriculumBookRead,
    CurriculumUnitRead,
    CurriculumUploadResult,
)
from src.services import curriculum_catalog, curriculum_ingest
from src.services.curriculum_job_worker import process_next_curriculum_ingest_job

router = APIRouter(
    prefix="/curriculum",
    tags=["Curriculum Catalog (phẳng)"],
    dependencies=[Depends(require_roles(enums.UserRole.ADMIN, enums.UserRole.PRINCIPAL, enums.UserRole.SUBJECT_HEAD))],
)

_TMP_DIR = Path(__file__).resolve().parents[2] / "temp"


def _job_to_read(db: Session, job: CurriculumIngestJob) -> BookIngestJobRead:
    """Chuyển row job → DTO (giải mã result_json nếu có)."""
    result = None
    if job.result_json:
        try:
            result = BookIngestResult(**json.loads(job.result_json))
        except (ValueError, TypeError):
            result = None
    return BookIngestJobRead(
        job_id=job.id,
        status=job.status,
        progress=job.progress,
        subject_code=job.subject_code,
        grade_number=job.grade_number,
        semester_number=job.semester_number,
        filename=job.filename,
        book_title=job.book_title,
        result=result,
        error=job.error_message,
        created_at=job.created_at.isoformat() if job.created_at else None,
    )


def _subject_ids(db: Session, subject_code: str) -> list[int]:
    """Danh sách s360.dim_subject.id theo mã môn (vd TOAN_6 → [id TOAN_6]; TOAN → TOAN_6..11).

    Match BOTH dạng khối hoá (TOAN_6, TOAN_7...) và dạng đơn mã (VAN, KHTN, GDCD...):
    toàn bộ ánh xạ môn của mock v4 đều vào tới đây.
    """
    code = subject_code.upper().strip()
    rows = db.execute(
        text("SELECT id FROM s360.dim_subject WHERE code = :code OR code LIKE :prefix"),
        {"code": code, "prefix": f"{code}_%"},
    ).fetchall()
    return [int(row.id) for row in rows]


@router.get("/units", response_model=list[CurriculumUnitRead])
def list_units(
    subject_code: str,
    grade: int | None = None,
    semester: int | None = None,
    include_inactive: bool = False,
    book_id: int | None = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """Danh sách node chương/bài (có parent_name + cuốn sách nguồn) theo môn/khối/học kỳ.

    book_id (nếu có): chỉ lấy node thuộc cuốn sách đó — dùng khi bấm vào 1 cuốn trong
    danh sách sách để xem node của đúng cuốn.
    """
    stmt = select(CurriculumUnit)
    if book_id is not None:
        stmt = stmt.where(CurriculumUnit.book_id == book_id)
    else:
        subject_ids = _subject_ids(db, subject_code)
        if not subject_ids:
            return []
        stmt = stmt.where(CurriculumUnit.subject_id.in_(subject_ids))
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
    book_ids = {u.book_id for u in units if u.book_id is not None}
    parents: dict[int, CurriculumUnit] = {}
    if parent_ids:
        parents = {
            p.id: p
            for p in db.execute(select(CurriculumUnit).where(CurriculumUnit.id.in_(parent_ids))).scalars()
        }
    books: dict[int, str] = {}
    if book_ids:
        books = {
            b.id: b.title
            for b in db.execute(select(CurriculumBook).where(CurriculumBook.id.in_(book_ids))).scalars()
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
            is_phu=u.is_phu,
            description=u.description,
            book_id=u.book_id,
            book_title=books.get(u.book_id) if u.book_id else None,
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


@router.post("/ingest-book", response_model=BookIngestJobRead, status_code=202)
def ingest_book(
    file: Annotated[UploadFile, File()],
    subject_code: Annotated[str, Form()],
    grade: Annotated[int, Form()],
    semester: Annotated[int | None, Form()] = None,
    book_title: Annotated[str | None, Form()] = None,
    include_lessons: Annotated[bool, Form()] = False,
    dry_run: Annotated[bool, Form()] = True,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    background_tasks: BackgroundTasks = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """Nạp sách giáo khoa (PDF/DOCX/TXT/MD) → tách mục lục BẤT ĐỒNG BỘ (DB-backed queue).

    Tạo job pending + lưu file tạm rồi gọi worker (FIFO, 1 job/lúc). Frontend poll
    GET /ingest-book/jobs/{job_id}. dry_run=true: chỉ preview (mặc định); false: tự lưu + gắn book.
    """
    content = file.file.read()
    _TMP_DIR.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "book.pdf").suffix.lower() or ".pdf"
    tmp = _TMP_DIR / f"curri_{uuid.uuid4().hex}{suffix}"
    tmp.write_bytes(content)

    job = CurriculumIngestJob(
        requested_by=current_user.id if current_user else None,
        subject_code=subject_code.upper(),
        grade_number=grade,
        semester_number=semester,
        include_lessons=include_lessons,
        dry_run=dry_run,
        filename=file.filename or "book.pdf",
        book_title=book_title,
        source_filepath=str(tmp),
        status="pending",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    background_tasks.add_task(process_next_curriculum_ingest_job)
    return _job_to_read(db, job)


@router.get("/ingest-book/jobs", response_model=list[BookIngestJobRead])
def list_ingest_jobs(
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """Lịch sử các job nạp sách (mới nhất trước) — để UI hiển thị bảng 'Lịch sử nạp sách'."""
    jobs = list(
        db.execute(select(CurriculumIngestJob).order_by(CurriculumIngestJob.created_at.desc()).limit(limit)).scalars()
    )
    return [_job_to_read(db, j) for j in jobs]


@router.get("/ingest-book/jobs/{job_id}", response_model=BookIngestJobRead)
def get_ingest_job(
    job_id: int,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """Poll trạng thái 1 job nạp sách (pending | processing | completed | failed + result)."""
    job = db.get(CurriculumIngestJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job không tồn tại.")
    return _job_to_read(db, job)


@router.post("/ingest-book/commit", response_model=BookIngestResult)
def commit_book_catalog(
    job_id: Annotated[int, Form()],
    db: Annotated[Session, Depends(get_db)] = None,
):
    """Lưu cây chương/bài của job (đã preview success) thẳng vào curriculum_units — KHÔNG trích lại/VLM.

    Upsert cuốn SGK (get_or_create theo unique) rồi gắn book_id vào node; cập nhật counter job.
    """
    job = db.get(CurriculumIngestJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job không tồn tại.")
    if job.status != "completed" or not job.result_json:
        raise HTTPException(status_code=422, detail="Job chưa trích xuất xong — hãy chờ rồi thử lại.")
    try:
        result = json.loads(job.result_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="Kết quả job hỏng.") from exc

    try:
        book_id = curriculum_catalog.get_or_create_book(
            db,
            job.subject_code,
            job.grade_number,
            job.semester_number,
            job.book_title or "",
            filename=job.filename,
            created_by=job.requested_by,
        )
    except ValueError as exc:
        # Vd môn chưa có trong s360.dim_subject (chưa seed) hoặc subject_code lạ — trả 422 rõ ràng, không 500.
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        saved = curriculum_ingest.save_catalog_from_preview(
            db,
            result["chapters"],
            job.subject_code,
            job.grade_number,
            job.semester_number,
            book_id=book_id,
        )
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    saved["book_id"] = book_id
    job.inserted = saved["inserted"]
    job.updated = saved["updated"]
    job.hidden_placeholders = saved["hidden_placeholders"]
    db.commit()
    return BookIngestResult(**saved)


@router.get("/books", response_model=list[CurriculumBookRead])
def list_books(
    subject_code: str | None = None,
    grade: int | None = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """Danh sách cuốn SGK đã nạp (kèm số node thuộc cuốn) — để UI hiển thị 'Cuốn sách'."""
    stmt = select(CurriculumBook).order_by(CurriculumBook.created_at.desc())
    if subject_code:
        stmt = stmt.where(CurriculumBook.subject_code == subject_code.upper())
    if grade is not None:
        stmt = stmt.where(CurriculumBook.grade_number == grade)
    books = list(db.execute(stmt).scalars().all())
    if not books:
        return []
    counts: dict[int, int] = {}
    for bid in [b.id for b in books]:
        counts[bid] = (
            db.execute(select(CurriculumUnit.id).where(CurriculumUnit.book_id == bid)).scalars().all().__len__()
        )
    return [
        CurriculumBookRead(
            id=b.id,
            title=b.title,
            subject_code=b.subject_code,
            subject_id=b.subject_id,
            grade_number=b.grade_number,
            semester_number=b.semester_number,
            filename=b.filename,
            source=b.source,
            unit_count=counts.get(b.id, 0),
            created_at=b.created_at.isoformat() if b.created_at else None,
        )
        for b in books
    ]


class CurriculumSubjectRead(BaseModel):
    """1 môn trong s360.dim_subject (đồng bộ với mock v4)."""

    code: str
    name: str


@router.get("/subjects", response_model=list[CurriculumSubjectRead])
def list_subjects(db: Annotated[Session, Depends(get_db)] = None):
    """Danh sách môn có trong DB (s360.dim_subject, mock v4 seed) — ĐẦY ĐỦ, không gom.

    SUBJECTS_23 trong generate_full_system_mock_v4.py có 24 dòng: TOAN_6..TOAN_11 (Toán theo
    khối) + VAN, ANH, LY, HOA, SINH, KHTN, LS_DL, CAM_ENG, CAM_MATH, IB_MATH, IB_SCI, TIN,
    ROBOTICS, GPA_HONOR, THE_DUC, MY_THUAT, AM_NHAC, GDCD. Trả NGUYÊN code (TOAN_6, TOAN_7...)
    để dropdown hiển thị đúng 23 môn như SUBJECTS_23, không rút gọn về TOAN.
    """
    rows = db.execute(
        text("SELECT DISTINCT code, name FROM s360.dim_subject WHERE code != '' ORDER BY code")
    ).fetchall()
    return [CurriculumSubjectRead(code=str(r.code), name=str(r.name)) for r in rows]


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
        is_phu=unit.is_phu,
        description=unit.description,
        book_id=unit.book_id,
    )

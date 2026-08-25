"""API admin quản lý catalog chuẩn chương trình (bảng phẳng curriculum_units) — KHÔNG RAG.

M5 bổ sung: xem cây chương/bài, upload mục lục (JSON/markdown) ghi thẳng vào
curriculum_units, bật/tắt node (ẩn khỏi shortlist của LLM map). Chỉ ADMIN.
Dữ liệu này KHÔNG đi qua Qdrant/Airflow — RAG chỉ dành cho chat hỏi đáp SGK.

Hàng đợi nạp sách giáo khoa: DB-backed (bảng curriculum_ingest_jobs, giống ews_pipeline_jobs),
worker src/services/curriculum_job_worker.py chạy 1 job/lúc theo FIFO. POST /ingest-book tạo
job (202) + lưu file tạm; frontend poll /ingest-book/jobs/{id}; /ingest-book/jobs trả Lịch sử.
"""

import json
import logging
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session

from src.api.deps import get_current_user, get_db, require_roles
from src.models import enums
from src.models.tables import CurriculumBook, CurriculumChunk, CurriculumIngestJob, CurriculumUnit, TeachingSchedule, User
from src.schemas.curriculum import (
    BookClearEnrichmentResult,
    BookDeleteResult,
    BookIngestJobRead,
    BookIngestResult,
    BookLockToggleResult,
    BookReEnrichRequest,
    BookReIndexChunksResult,
    CurriculumBookRead,
    CurriculumUnitRead,
    CurriculumUploadResult,
    SchoolYearRead,
    TeachingScheduleRead,
)
from src.services import curriculum_catalog, curriculum_ingest
from src.services.curriculum_job_worker import process_next_curriculum_ingest_job

router = APIRouter(
    prefix="/curriculum",
    tags=["Curriculum Catalog (phẳng)"],
    dependencies=[Depends(require_roles(enums.UserRole.ADMIN, enums.UserRole.PRINCIPAL, enums.UserRole.SUBJECT_HEAD))],
)

_TMP_DIR = Path(__file__).resolve().parents[3] / "uploads" / "curriculum_tmp"
# Thư mục lưu file PDF GỐC của từng cuốn SGK (để render ảnh bìa/trang đầu khi xem danh sách sách).
_BOOK_DIR = Path(__file__).resolve().parents[3] / "uploads" / "curriculum_books"

logger = logging.getLogger(__name__)


def _book_pdf_path(book_id: int) -> Path:
    """Đường dẫn file PDF gốc của cuốn sách (quy ước {book_id}.pdf)."""
    return _BOOK_DIR / f"{book_id}.pdf"


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
        vlm_model=getattr(job, "vlm_model", None),
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
            summary=u.summary,
            keywords=u.keywords,
            sections=u.sections,
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
    vlm_model: Annotated[str | None, Form()] = None,
    include_lessons: Annotated[bool, Form()] = True,
    enrich: Annotated[bool, Form()] = True,
    dry_run: Annotated[bool, Form()] = True,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    background_tasks: BackgroundTasks = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """Nạp sách giáo khoa (PDF/DOCX/TXT/MD) → tự tách mục lục BẤT ĐỒNG BỘ (DB-backed queue).

    PDF: quét TOÀN BỘ cuốn 1 lần bằng VLM (tự định vị MỤC LỤC); enrich=true (mặc định) còn
    làm giàu từng bài (tóm tắt + từ khóa + mục con). Tạo job pending + lưu file tạm rồi gọi
    worker (FIFO, 1 job/lúc). Frontend poll GET /ingest-book/jobs/{job_id}.
    dry_run=true: chỉ preview (mặc định); false: tự lưu + gắn book.
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
        enrich=enrich,
        dry_run=dry_run,
        filename=file.filename or "book.pdf",
        book_title=book_title,
        vlm_model=vlm_model.strip() if vlm_model and vlm_model.strip() else None,
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

    # Giữ file PDF GỐC của cuốn (để render ảnh bìa/trang đầu ở danh sách sách). File tạm của job
    # có thể đã bị worker dọn — nếu còn thì copy sang thư mục bền theo {book_id}.pdf.
    try:
        if job.source_filepath:
            src = Path(job.source_filepath)
            if src.exists():
                _BOOK_DIR.mkdir(parents=True, exist_ok=True)
                dst = _book_pdf_path(book_id)
                dst.write_bytes(src.read_bytes())
                # Dọn file tạm sau khi đã copy sang thư mục bền
                try:
                    src.unlink(missing_ok=True)
                except OSError:
                    pass
                # Cắt lát và index chunks vector (RAG)
                try:
                    from src.services.curriculum_chunking import index_book_chunks
                    index_book_chunks(db, book_id, dst)
                except Exception as chunk_exc:
                    logger.warning("Không index được chunks cho cuốn %s: %s", book_id, chunk_exc)
    except OSError as exc:
        logger.warning("Không lưu được file gốc cuốn %s: %s", book_id, exc)

    return BookIngestResult(**saved)


@router.get("/books", response_model=list[CurriculumBookRead])
def list_books(
    subject_code: str | None = None,
    grade: int | None = None,
    school_year_id: int | None = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """Danh sách cuốn SGK đã nạp (kèm số node thuộc cuốn) — để UI hiển thị 'Cuốn sách'."""
    stmt = select(CurriculumBook).order_by(CurriculumBook.created_at.desc())
    if subject_code:
        stmt = stmt.where(CurriculumBook.subject_code == subject_code.upper())
    if grade is not None:
        stmt = stmt.where(CurriculumBook.grade_number == grade)
    if school_year_id is not None:
        stmt = stmt.where(
            or_(CurriculumBook.school_year_id == school_year_id, CurriculumBook.school_year_id.is_(None))
        )
    books = list(db.execute(stmt).scalars().all())
    if not books:
        return []
    counts: dict[int, int] = {}
    chunk_counts: dict[int, int] = {}
    for bid in [b.id for b in books]:
        counts[bid] = (
            db.execute(select(CurriculumUnit.id).where(CurriculumUnit.book_id == bid)).scalars().all().__len__()
        )
        chunk_counts[bid] = (
            db.execute(select(CurriculumChunk.id).where(CurriculumChunk.book_id == bid)).scalars().all().__len__()
        )
    years: dict[int, str] = {}
    try:
        y_rows = db.execute(text("SELECT id, fullname FROM s360.dim_school_year")).fetchall()
        years = {int(r.id): str(r.fullname) for r in y_rows}
    except Exception:
        pass
    return [
        CurriculumBookRead(
            id=b.id,
            title=b.title,
            subject_code=b.subject_code,
            subject_id=b.subject_id,
            grade_number=b.grade_number,
            semester_number=b.semester_number,
            school_year_id=b.school_year_id,
            school_year_name=years.get(b.school_year_id) if b.school_year_id else (years.get(2025) or "Năm học 2025-2026"),
            is_locked=bool(b.is_locked),
            filename=b.filename,
            source=b.source,
            unit_count=counts.get(b.id, 0),
            chunk_count=chunk_counts.get(b.id, 0),
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


@router.get("/books/{book_id}/cover")
def book_cover(book_id: int, db: Annotated[Session, Depends(get_db)] = None):
    """Ảnh bìa (trang đầu) của cuốn SGK — render từ file PDF gốc đã lưu khi commit.

    Trả PNG để frontend hiển thị thumbnail trong danh sách sách. Nếu chưa có file gốc
    (sách nạp trước khi tính năng này ra đời) → 404, frontend sẽ hiện placeholder.
    """
    book = db.get(CurriculumBook, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Cuốn sách không tồn tại")
    pdf_path = _book_pdf_path(book_id)
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="Chưa có file gốc cho cuốn sách này")
    try:
        import fitz  # PyMuPDF — đã có trong deps

        with fitz.open(pdf_path) as doc:
            if doc.page_count == 0:
                raise HTTPException(status_code=404, detail="PDF trống")
            pix = doc.load_page(0).get_pixmap(dpi=72)
            png = pix.tobytes("png")
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 — file hỏng/không render được
        logger.warning("Không render được bìa cuốn %s: %s", book_id, exc)
        raise HTTPException(status_code=500, detail="Không render được ảnh bìa") from exc
    return Response(content=png, media_type="image/png")


@router.post("/books/{book_id}/re-enrich", response_model=BookIngestJobRead, status_code=202)
def re_enrich_book(
    book_id: int,
    payload: BookReEnrichRequest | None = None,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    background_tasks: BackgroundTasks = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """Chạy LẠI bước làm giàu (tóm tắt/từ khóa/mục con) cho 1 cuốn từ file PDF gốc đã lưu.

    Tạo job nạp lại (dry_run=false, enrich=true) dùng đúng file uploads/curriculum_books/{id}.pdf
    → worker upsert cập nhật summary/keywords/sections cho node đã có (không cần upload lại).
    include_lessons tự dò: cuốn có node bài con (parent_id) thì tách bài như bản gốc.
    """
    book = db.get(CurriculumBook, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Cuốn sách không tồn tại")
    src = _book_pdf_path(book_id)
    if not src.exists():
        raise HTTPException(
            status_code=404,
            detail="Cuốn này chưa có file PDF gốc (nạp trước khi tính năng ra đời) — hãy nạp lại cuốn.",
        )
    has_lessons = (
        db.execute(
            select(CurriculumUnit.id)
            .where(CurriculumUnit.book_id == book_id, CurriculumUnit.parent_id.is_not(None))
            .limit(1)
        ).scalars().first()
        is not None
    )
    _TMP_DIR.mkdir(parents=True, exist_ok=True)
    tmp = _TMP_DIR / f"curri_{uuid.uuid4().hex}.pdf"
    tmp.write_bytes(src.read_bytes())
    job = CurriculumIngestJob(
        requested_by=current_user.id if current_user else None,
        subject_code=book.subject_code,
        grade_number=book.grade_number,
        semester_number=book.semester_number,
        include_lessons=has_lessons,
        enrich=True,
        dry_run=False,
        filename=book.filename,
        book_title=book.title,
        vlm_model=payload.vlm_model if payload else None,
        source_filepath=str(tmp),
        status="pending",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    background_tasks.add_task(process_next_curriculum_ingest_job)
    return _job_to_read(db, job)


@router.post("/books/{book_id}/re-index-chunks", response_model=BookReIndexChunksResult)
def re_index_book_chunks(
    book_id: int,
    payload: BookReEnrichRequest | None = None,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """Cắt lát và index lại chunks RAG vào pgvector cho 1 cuốn sách mà không cần quét lại mục lục/cây bài."""
    book = db.get(CurriculumBook, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Cuốn sách không tồn tại")
    src = _book_pdf_path(book_id)
    if not src.exists():
        raise HTTPException(
            status_code=404,
            detail="Cuốn này chưa có file PDF gốc trong hệ thống — hãy nạp lại cuốn.",
        )
    from src.services.curriculum_chunking import index_book_chunks
    from src.services.curriculum_ingest import _get_runtime_settings

    s = _get_runtime_settings(vlm_model=payload.vlm_model if payload else None)
    try:
        count = index_book_chunks(db, book_id, src, settings=s)
        return BookReIndexChunksResult(
            book_id=book.id,
            title=book.title,
            chunk_count=count,
            message=f"Đã cắt và index thành công {count} chunks RAG vào PostgreSQL (pgvector).",
        )
    except Exception as exc:
        logger.exception("Lỗi khi index chunks cho cuốn %s: %s", book_id, exc)
        raise HTTPException(status_code=500, detail=f"Lỗi khi index chunks: {exc}") from exc


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
        summary=unit.summary,
        keywords=unit.keywords,
        sections=unit.sections,
        book_id=unit.book_id,
    )

@router.get("/school-years", response_model=list[SchoolYearRead])
def list_school_years(db: Annotated[Session, Depends(get_db)] = None):
    """Danh sách năm học từ s360.dim_school_year."""
    try:
        rows = db.execute(
            text("SELECT id, code, fullname, COALESCE(is_current, 0) as is_current, COALESCE(is_locked, 0) as is_locked FROM s360.dim_school_year ORDER BY id DESC")
        ).fetchall()
        if rows:
            return [
                SchoolYearRead(
                    id=int(r.id),
                    code=str(r.code),
                    fullname=str(r.fullname),
                    is_current=bool(r.is_current),
                    is_locked=bool(r.is_locked),
                )
                for r in rows
            ]
    except Exception as exc:
        logger.warning("Không đọc được s360.dim_school_year: %s", exc)
    return [
        SchoolYearRead(id=2025, code="2024-2025", fullname="Năm học 2024-2025", is_current=True, is_locked=False),
        SchoolYearRead(id=2026, code="2025-2026", fullname="Năm học 2025-2026", is_current=False, is_locked=False),
    ]


@router.post("/books/{book_id}/toggle-lock", response_model=BookLockToggleResult)
def toggle_book_lock(book_id: int, db: Annotated[Session, Depends(get_db)] = None):
    """Khóa / mở khóa cuốn sách giáo khoa."""
    book = db.get(CurriculumBook, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Cuốn sách không tồn tại")
    book.is_locked = not book.is_locked
    db.commit()
    status_str = "đã được KHÓA 🔒" if book.is_locked else "đã được MỞ KHÓA 🔓"
    return BookLockToggleResult(
        book_id=book.id,
        title=book.title,
        is_locked=book.is_locked,
        message=f"Cuốn sách '{book.title}' {status_str}.",
    )


@router.get("/teaching-schedules", response_model=list[TeachingScheduleRead])
def list_teaching_schedules(
    school_year_id: int = 2025,
    subject_code: str | None = None,
    grade: int | None = None,
    semester: int | None = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """Danh sách 35 tuần phân phối chương trình môn học."""
    stmt = select(TeachingSchedule).where(TeachingSchedule.school_year_id == school_year_id)
    if grade is not None:
        stmt = stmt.where(TeachingSchedule.grade_number == grade)
    if semester in (1, 2):
        stmt = stmt.where(TeachingSchedule.semester_number == semester)
    if subject_code:
        s_ids = _subject_ids(db, subject_code)
        if s_ids:
            stmt = stmt.where(TeachingSchedule.subject_id.in_(s_ids))

    schedules = list(
        db.execute(stmt.order_by(TeachingSchedule.semester_number, TeachingSchedule.week_number)).scalars().all()
    )
    unit_ids = {s.unit_id for s in schedules if s.unit_id is not None}
    units_map = {}
    if unit_ids:
        units_map = {
            u.id: u for u in db.execute(select(CurriculumUnit).where(CurriculumUnit.id.in_(unit_ids))).scalars().all()
        }

    return [
        TeachingScheduleRead(
            id=s.id,
            school_year_id=s.school_year_id,
            subject_id=s.subject_id,
            grade_number=s.grade_number,
            semester_number=s.semester_number,
            week_number=s.week_number,
            unit_id=s.unit_id,
            unit_code=units_map[s.unit_id].code if s.unit_id in units_map else None,
            unit_name=units_map[s.unit_id].name if s.unit_id in units_map else None,
            topic=s.topic,
            num_periods=s.num_periods,
            notes=s.notes,
        )
        for s in schedules
    ]


@router.post("/books/{book_id}/clear-enrichment", response_model=BookClearEnrichmentResult)
def clear_book_enrichment(book_id: int, db: Annotated[Session, Depends(get_db)] = None):
    """Xóa sạch toàn bộ tóm tắt, từ khóa, mục con của tất cả các node thuộc 1 cuốn sách."""
    book = db.get(CurriculumBook, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Cuốn sách không tồn tại")
    if book.is_locked:
        raise HTTPException(
            status_code=400,
            detail="Cuốn sách đã bị khóa cho năm học này. Vui lòng mở khóa trước khi xóa dữ liệu làm giàu.",
        )

    units = list(
        db.execute(select(CurriculumUnit).where(CurriculumUnit.book_id == book_id)).scalars().all()
    )
    for u in units:
        u.summary = None
        u.keywords = None
        u.sections = None
    db.commit()

    return BookClearEnrichmentResult(
        book_id=book.id,
        title=book.title,
        cleared_units_count=len(units),
        message=f"Đã xóa sạch nội dung làm giàu của {len(units)} node thuộc cuốn '{book.title}'.",
    )


@router.delete("/books/{book_id}", response_model=BookDeleteResult)
def delete_book(book_id: int, db: Annotated[Session, Depends(get_db)] = None):
    """Xóa 1 cuốn SGK và toàn bộ các node chương/bài thuộc cuốn đó."""
    book = db.get(CurriculumBook, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Cuốn sách không tồn tại")
    if book.is_locked:
        raise HTTPException(
            status_code=400,
            detail="Cuốn sách đã bị khóa cho năm học này. Vui lòng mở khóa trước khi xóa sách.",
        )

    try:
        res = curriculum_catalog.delete_book_and_units(db, book_id)
    except Exception as exc:
        db.rollback()
        logger.exception("Lỗi khi xóa cuốn sách %s: %s", book_id, exc)
        raise HTTPException(status_code=500, detail=f"Lỗi khi xóa cuốn sách: {exc}") from exc

    # Xóa file PDF bìa/gốc lưu ở uploads/curriculum_books/{book_id}.pdf
    try:
        pdf_path = _book_pdf_path(book_id)
        if pdf_path.exists():
            pdf_path.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("Không xóa được file gốc cuốn %s: %s", book_id, exc)

    return res


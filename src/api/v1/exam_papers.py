from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.deps import CurrentUser, get_db, require_roles
from src.models import enums
from src.models.tables import ExamPaper
from src.schemas.exam import ExamPaperDetailRead, ExamPaperRead
from src.services import content_difficulty, rbac, storage

_ANALYSIS_ROLES = (enums.UserRole.ADMIN, enums.UserRole.PRINCIPAL)

router = APIRouter(prefix="/exam-papers", tags=["Exam Papers"])


@router.post("", response_model=ExamPaperRead, status_code=201)
def upload_exam(
    user: CurrentUser,
    subject_id: Annotated[UUID, Form()],
    semester_id: Annotated[UUID, Form()],
    title: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
    db: Annotated[Session, Depends(get_db)],
    background_tasks: BackgroundTasks,
    grade_id: Annotated[UUID | None, Form()] = None,
    description: Annotated[str | None, Form()] = None,
):
    """Tải lên file đề thi (PDF/DOC/ảnh) — bất kỳ user đã đăng nhập. Tự động phân tích CDI ở nền."""
    try:
        stored, size, file_type = storage.save_exam_file(file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    paper = ExamPaper(
        school_id=user.school_id,
        subject_id=subject_id,
        semester_id=semester_id,
        grade_id=grade_id,
        title=title,
        description=description,
        file_url=stored,
        file_type=file_type,
        file_size_bytes=size,
        uploaded_by=user.id,
    )
    db.add(paper)
    db.commit()
    db.refresh(paper)
    background_tasks.add_task(content_difficulty.analyze_exam_paper, paper.id)
    return paper


@router.get("", response_model=list[ExamPaperRead])
def list_exams(
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    subject_id: UUID | None = None,
    semester_id: UUID | None = None,
):
    stmt = select(ExamPaper).where(ExamPaper.school_id == user.school_id)
    if subject_id is not None:
        stmt = stmt.where(ExamPaper.subject_id == subject_id)
    if semester_id is not None:
        stmt = stmt.where(ExamPaper.semester_id == semester_id)
    return list(db.execute(stmt.order_by(ExamPaper.created_at.desc()).limit(500)).scalars().all())


def _get_exam_in_school(db: Session, paper_id: UUID, user) -> ExamPaper:
    paper = db.get(ExamPaper, paper_id)
    if paper is None or paper.school_id != user.school_id:
        raise HTTPException(status_code=404, detail="Đề thi không tồn tại")
    return paper


def _can_view_analysis(db: Session, user, subject_id: UUID) -> bool:
    """Chỉ ADMIN/PRINCIPAL hoặc GV/Trưởng bộ môn phụ trách đúng môn được xem ai_analysis (chứa
    trích đoạn nguyên văn đề + nguồn SGK) — tránh lộ nội dung đề cho GV môn khác cùng trường."""
    return user.role in _ANALYSIS_ROLES or rbac.can_manage_question_bank(db, user, subject_id)


@router.get("/{paper_id}", response_model=ExamPaperDetailRead)
def get_exam(paper_id: UUID, user: CurrentUser, db: Annotated[Session, Depends(get_db)]):
    paper = _get_exam_in_school(db, paper_id, user)
    detail = ExamPaperDetailRead.model_validate(paper)
    if not _can_view_analysis(db, user, paper.subject_id):
        detail.ai_analysis = {}
    return detail


@router.get("/{paper_id}/file")
def download_exam(paper_id: UUID, user: CurrentUser, db: Annotated[Session, Depends(get_db)]):
    """Xem/tải file đề (preview)."""
    paper = _get_exam_in_school(db, paper_id, user)
    if not paper.file_url:
        raise HTTPException(status_code=404, detail="Đề thi không tồn tại")
    path = storage.exam_file_path(paper.file_url)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File đề không tìm thấy trên máy chủ")
    return FileResponse(path, filename=f"{paper.title}{path.suffix}")


@router.post("/{paper_id}/analyze", status_code=202)
def trigger_analyze(
    paper_id: UUID,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    background_tasks: BackgroundTasks,
):
    """Phân tích/re-phân tích nội dung đề bằng tay (khi tự động thất bại hoặc đã sửa file)."""
    paper = _get_exam_in_school(db, paper_id, user)
    background_tasks.add_task(content_difficulty.analyze_exam_paper, paper.id)
    return {"status": "queued"}


@router.delete("/{paper_id}", status_code=204, dependencies=[Depends(require_roles(enums.UserRole.ADMIN))])
def delete_exam(paper_id: UUID, user: CurrentUser, db: Annotated[Session, Depends(get_db)]):
    paper = _get_exam_in_school(db, paper_id, user)
    if paper.file_url:
        storage.delete_exam_file(paper.file_url)
    db.delete(paper)
    db.commit()

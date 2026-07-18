from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.deps import CurrentUser, get_db
from src.models import enums
from src.models.tables import Enrollment, Score
from src.repositories.base import CRUDBase
from src.schemas.score import ScoreBatchCreate, ScoreCreate, ScoreRead, ScoreUpdate
from src.services import item_statistics, rbac

router = APIRouter(prefix="/scores", tags=["Scores"])
crud = CRUDBase(Score)

APPROVE_ROLES = {enums.UserRole.ADMIN, enums.UserRole.PRINCIPAL}


def _require_enrolled(db: Session, student_id: UUID, class_id: UUID) -> None:
    stmt = select(Enrollment.id).where(
        Enrollment.student_id == student_id, Enrollment.class_id == class_id, Enrollment.is_active.is_(True)
    )
    if db.execute(stmt).scalar_one_or_none() is None:
        raise HTTPException(status_code=400, detail="Học sinh không thuộc lớp này")


class ScoreFilter:
    """Bộ lọc truy vấn điểm (gom query params, giữ handler gọn)."""

    def __init__(
        self,
        student_id: UUID | None = None,
        subject_id: UUID | None = None,
        semester_id: UUID | None = None,
        class_id: UUID | None = None,
        status: enums.ScoreStatus | None = None,
        score_category: enums.ScoreCategory | None = None,
        skip: int = 0,
        limit: int = Query(default=200, le=1000),
    ) -> None:
        self.student_id = student_id
        self.subject_id = subject_id
        self.semester_id = semester_id
        self.class_id = class_id
        self.status = status
        self.score_category = score_category
        self.skip = skip
        self.limit = limit


def _require_write(db: Session, user, subject_id: UUID, class_id: UUID) -> None:
    if not rbac.can_write_score(db, user, subject_id, class_id):
        raise HTTPException(status_code=403, detail="Bạn không được phân công nhập điểm cho môn/lớp này")


@router.get("", response_model=list[ScoreRead])
def list_scores(user: CurrentUser, f: ScoreFilter = Depends(), db: Session = Depends(get_db)):
    stmt = select(Score)
    for column, value in (
        (Score.student_id, f.student_id),
        (Score.subject_id, f.subject_id),
        (Score.semester_id, f.semester_id),
        (Score.class_id, f.class_id),
        (Score.status, f.status),
        (Score.score_category, f.score_category),
    ):
        if value is not None:
            stmt = stmt.where(column == value)
    scope = rbac.accessible_score_filter(db, user)
    if scope is not None:
        stmt = stmt.where(scope)
    stmt = stmt.offset(f.skip).limit(f.limit)
    return list(db.execute(stmt).scalars().all())


@router.get("/{score_id}", response_model=ScoreRead)
def get_score(score_id: UUID, user: CurrentUser, db: Session = Depends(get_db)):
    stmt = select(Score).where(Score.id == score_id)
    scope = rbac.accessible_score_filter(db, user)
    if scope is not None:
        stmt = stmt.where(scope)
    obj = db.execute(stmt).scalar_one_or_none()
    if obj is None:
        raise HTTPException(status_code=404, detail="Điểm không tồn tại")
    return obj


@router.post("", response_model=ScoreRead, status_code=201)
def create_score(payload: ScoreCreate, user: CurrentUser, db: Session = Depends(get_db)):
    _require_write(db, user, payload.subject_id, payload.class_id)
    _require_enrolled(db, payload.student_id, payload.class_id)
    return crud.create(db, {**payload.model_dump(), "entered_by": user.id})


@router.post("/batch", response_model=list[ScoreRead], status_code=201)
def create_scores_batch(payload: ScoreBatchCreate, user: CurrentUser, db: Session = Depends(get_db)):
    # Batch có thể chứa hàng chục dòng nhưng thường chỉ vài (môn, lớp) khác nhau -> dedup trước
    # khi kiểm quyền/ghi danh để tránh N+1 query lặp lại cho từng dòng.
    assignments = rbac.load_assignments(db, user.id)
    write_pairs = {(item.subject_id, item.class_id) for item in payload.items}
    for subject_id, class_id in write_pairs:
        if not rbac.can_write_score(db, user, subject_id, class_id, assignments=assignments):
            raise HTTPException(status_code=403, detail="Bạn không được phân công nhập điểm cho môn/lớp này")

    enroll_pairs = {(item.student_id, item.class_id) for item in payload.items}
    enrolled_stmt = select(Enrollment.student_id, Enrollment.class_id).where(
        Enrollment.is_active.is_(True),
        Enrollment.class_id.in_({class_id for _, class_id in enroll_pairs}),
    )
    enrolled_pairs = {(row.student_id, row.class_id) for row in db.execute(enrolled_stmt)}
    missing = enroll_pairs - enrolled_pairs
    if missing:
        raise HTTPException(status_code=400, detail="Có học sinh không thuộc lớp trong danh sách nhập điểm")

    objs = [Score(**item.model_dump(), entered_by=user.id) for item in payload.items]
    db.add_all(objs)
    db.commit()
    for obj in objs:
        db.refresh(obj)
    return objs


def _require_not_locked(obj: Score, user) -> None:
    if obj.status == enums.ScoreStatus.APPROVED and user.role not in APPROVE_ROLES:
        raise HTTPException(status_code=403, detail="Điểm đã duyệt — chỉ Ban Giám Hiệu/Admin được sửa hoặc mở khóa")


@router.patch("/{score_id}", response_model=ScoreRead)
def update_score(score_id: UUID, payload: ScoreUpdate, user: CurrentUser, db: Session = Depends(get_db)):
    obj = crud.get(db, score_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Điểm không tồn tại")
    _require_write(db, user, obj.subject_id, obj.class_id)
    _require_not_locked(obj, user)
    data = payload.model_dump(exclude_unset=True)
    approving = data.get("status") == enums.ScoreStatus.APPROVED
    if approving:
        if user.role not in APPROVE_ROLES:
            raise HTTPException(status_code=403, detail="Chỉ Ban Giám Hiệu/Admin được duyệt điểm")
        if obj.approved_at is None:
            data["approved_at"] = datetime.now(UTC)
            data["approved_by"] = user.id
    result = crud.update(db, obj, data)
    if approving and result.exam_paper_id is not None:
        item_statistics.update_from_exam_paper(db, result.exam_paper_id)
    return result


@router.delete("/{score_id}", status_code=204)
def delete_score(score_id: UUID, user: CurrentUser, db: Session = Depends(get_db)):
    obj = crud.get(db, score_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Điểm không tồn tại")
    _require_write(db, user, obj.subject_id, obj.class_id)
    _require_not_locked(obj, user)
    crud.delete(db, obj)

"""Ngân hàng câu hỏi — tạo/sửa/duyệt câu (nguồn sự thật để ráp đề chính thức).

RBAC: GV bộ môn tạo/sửa câu DRAFT môn mình; chỉ Trưởng bộ môn/ADMIN DUYỆT (APPROVED).
Đáp án (answer_key) chỉ trả cho người có quyền quản lý môn — không lộ cho HS.
Xem docs/exam_generation_design.md §5.
"""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.api.deps import CurrentUser, get_db
from src.models import enums
from src.models.tables import QuestionItem, User
from src.schemas.exam_generation import (
    CalibrationRow,
    GenerateItemsRequest,
    QuestionItemCreate,
    QuestionItemDetail,
    QuestionItemListPage,
    QuestionItemRead,
    QuestionItemUpdate,
    ReviewDecision,
)
from src.services import item_calibration, item_generation, notifications, rbac

router = APIRouter(prefix="/question-bank", tags=["Question Bank"])

_EDITABLE = {enums.ItemStatus.DRAFT, enums.ItemStatus.REVIEW}


def _get_owned_item(db: Session, user, item_id: UUID) -> QuestionItem:
    """Lấy câu trong cùng trường, đảm bảo không rò rỉ giữa các trường."""
    item = db.get(QuestionItem, item_id)
    if item is None or item.school_id != user.school_id:
        raise HTTPException(status_code=404, detail="Câu hỏi không tồn tại")
    return item


def _user_names(db: Session, user_ids: set[UUID | None]) -> dict[UUID, str]:
    """Tra tên hiển thị cho tập user_id — tránh trả UUID trần ra FE (D.2 trong tài liệu UI)."""
    ids = {uid for uid in user_ids if uid is not None}
    if not ids:
        return {}
    rows = db.execute(select(User.id, User.full_name).where(User.id.in_(ids))).all()
    return dict(rows)


_COMPUTED_FIELDS = {"created_by_name", "reviewed_by_name"}


def _to_read(item: QuestionItem, names: dict[UUID, str]) -> QuestionItemRead:
    """Map ORM -> schema. Đọc trực tiếp các field gốc rồi GẮN THÊM tên người (không có trên ORM),
    tránh validate thẳng item vào QuestionItemRead (sẽ thiếu created_by_name/reviewed_by_name).
    provenance bỏ stem_embedding trước khi trả ra API — chỉ dùng nội bộ cho dedup (_existing_embeddings),
    không cần/không nên lộ vector embedding thô cho FE."""
    data = {f: getattr(item, f) for f in QuestionItemRead.model_fields if f not in _COMPUTED_FIELDS}
    data["provenance"] = {k: v for k, v in (item.provenance or {}).items() if k != "stem_embedding"}
    data["created_by_name"] = names.get(item.created_by, "?")
    data["reviewed_by_name"] = names.get(item.reviewed_by) if item.reviewed_by else None
    return QuestionItemRead(**data)


def _to_detail(item: QuestionItem, names: dict[UUID, str]) -> QuestionItemDetail:
    return QuestionItemDetail(**_to_read(item, names).model_dump(), answer_key=item.answer_key)


def _to_calibration_row(qi: QuestionItem) -> CalibrationRow:
    """Map QuestionItem -> dòng báo cáo hiệu chỉnh (thống kê + cờ 'bệnh' + khuyến nghị)."""
    p = float(qi.p_value) if qi.p_value is not None else None
    d = float(qi.discrimination) if qi.discrimination is not None else None
    flags = item_calibration.calibration_flags(p, d, qi.bloom_level)
    return CalibrationRow(
        item_id=qi.id,
        stem=qi.stem,
        bloom_level=qi.bloom_level,
        status=qi.status,
        times_used=qi.times_used,
        p_value=p,
        discrimination=d,
        flags=flags,
        recommendation=item_calibration.recommendation(flags),
    )


_RECOMMENDATION_ORDER = {"RETIRE": 0, "REVIEW": 1, None: 2}


def _calibration_sort_key(row: CalibrationRow) -> tuple[int, float, UUID]:
    """Khóa sắp xếp: bucket khuyến nghị (RETIRE trước) -> phân biệt tệ nhất -> id (tiebreaker ổn định)."""
    disc = row.discrimination if row.discrimination is not None else 1.0
    return (_RECOMMENDATION_ORDER.get(row.recommendation, 99), disc, row.item_id)


@router.post("/generate", status_code=202)
def trigger_generation(
    payload: GenerateItemsRequest, user: CurrentUser, background_tasks: BackgroundTasks, db: Session = Depends(get_db)
):
    """Sinh câu DRAFT bằng LLM+RAG ở nền (không chặn request). Xem kết quả qua GET /items?status=DRAFT."""
    if not rbac.can_manage_question_bank(db, user, payload.subject_id):
        raise HTTPException(status_code=403, detail="Bạn không phụ trách môn này")
    background_tasks.add_task(
        item_generation.generate_items_background,
        user.school_id,
        user.id,
        payload.subject_id,
        payload.grade_number,
        payload.unit_id,
        payload.bloom_level,
        payload.question_type,
        payload.count,
    )
    return {"status": "queued", "count": payload.count}


@router.post("/items", response_model=QuestionItemDetail, status_code=201)
def create_item(payload: QuestionItemCreate, user: CurrentUser, db: Session = Depends(get_db)):
    """Tạo câu hỏi thủ công (DRAFT). Câu sinh bằng LLM dùng luồng riêng (Phase 2)."""
    if not rbac.can_manage_question_bank(db, user, payload.subject_id):
        raise HTTPException(status_code=403, detail="Bạn không phụ trách môn này")
    item = QuestionItem(
        **payload.model_dump(),
        school_id=user.school_id,
        source=enums.ItemSource.MANUAL,
        status=enums.ItemStatus.DRAFT,
        created_by=user.id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    notifications.notify_question_submitted_batch(db, [item])
    return _to_detail(item, _user_names(db, {item.created_by}))


@router.get("/items", response_model=QuestionItemListPage)
def list_items(
    subject_id: UUID,
    user: CurrentUser,
    grade_number: int | None = None,
    unit_id: UUID | None = None,
    bloom_level: int | None = None,
    status: enums.ItemStatus | None = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Lọc câu của một môn user phụ trách, phân trang (đáp án ẩn — dùng endpoint chi tiết để xem)."""
    if not rbac.can_manage_question_bank(db, user, subject_id):
        raise HTTPException(status_code=403, detail="Bạn không phụ trách môn này")
    stmt = select(QuestionItem).where(QuestionItem.school_id == user.school_id, QuestionItem.subject_id == subject_id)
    filters = {"grade_number": grade_number, "unit_id": unit_id, "bloom_level": bloom_level, "status": status}
    for field, val in filters.items():
        if val is not None:
            stmt = stmt.where(getattr(QuestionItem, field) == val)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    stmt = stmt.order_by(QuestionItem.created_at.desc()).offset((page - 1) * limit).limit(limit)
    items = list(db.execute(stmt).scalars().all())
    names = _user_names(db, {i.created_by for i in items} | {i.reviewed_by for i in items})
    return QuestionItemListPage(items=[_to_read(i, names) for i in items], total=total)


@router.get("/items/{item_id}", response_model=QuestionItemDetail)
def get_item(item_id: UUID, user: CurrentUser, db: Session = Depends(get_db)):
    """Chi tiết câu kèm đáp án — chỉ người phụ trách môn."""
    item = _get_owned_item(db, user, item_id)
    if not rbac.can_manage_question_bank(db, user, item.subject_id):
        raise HTTPException(status_code=403, detail="Bạn không phụ trách môn này")
    return _to_detail(item, _user_names(db, {item.created_by, item.reviewed_by}))


@router.patch("/items/{item_id}", response_model=QuestionItemDetail)
def update_item(item_id: UUID, payload: QuestionItemUpdate, user: CurrentUser, db: Session = Depends(get_db)):
    """Sửa câu khi còn DRAFT/REVIEW. Câu đã APPROVED phải RETIRE rồi tạo mới (giữ truy vết)."""
    item = _get_owned_item(db, user, item_id)
    if not rbac.can_manage_question_bank(db, user, item.subject_id):
        raise HTTPException(status_code=403, detail="Bạn không phụ trách môn này")
    if item.status not in _EDITABLE:
        raise HTTPException(status_code=409, detail="Chỉ sửa được câu ở trạng thái DRAFT/REVIEW")
    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, val)
    db.commit()
    db.refresh(item)
    return _to_detail(item, _user_names(db, {item.created_by, item.reviewed_by}))


@router.post("/items/{item_id}/review", response_model=QuestionItemDetail)
def review_item(item_id: UUID, decision: ReviewDecision, user: CurrentUser, db: Session = Depends(get_db)):
    """Duyệt câu (Trưởng bộ môn/ADMIN): APPROVED hoặc REJECTED (từ chối phải kèm lý do)."""
    item = _get_owned_item(db, user, item_id)
    if not rbac.can_review_question(db, user, item.subject_id):
        raise HTTPException(status_code=403, detail="Chỉ Trưởng bộ môn được duyệt câu hỏi")
    if not decision.approve and not decision.reason:
        raise HTTPException(status_code=422, detail="Từ chối câu hỏi phải kèm lý do")
    item.status = enums.ItemStatus.APPROVED if decision.approve else enums.ItemStatus.REJECTED
    item.reviewed_by = user.id
    item.reviewed_at = datetime.now(UTC)
    db.commit()
    db.refresh(item)
    notifications.notify_item_reviewed(db, item, approved=decision.approve, reason=decision.reason)
    return _to_detail(item, _user_names(db, {item.created_by, item.reviewed_by}))


@router.get("/calibration", response_model=list[CalibrationRow])
def calibration_report(
    subject_id: UUID,
    user: CurrentUser,
    grade_number: int | None = None,
    db: Session = Depends(get_db),
):
    """Bảng hiệu chỉnh kho câu: chỉ câu APPROVED đã dùng (times_used > 0), xếp câu 'bệnh' nặng nhất trước."""
    if not rbac.can_manage_question_bank(db, user, subject_id):
        raise HTTPException(status_code=403, detail="Bạn không phụ trách môn này")
    stmt = (
        select(QuestionItem)
        .where(
            QuestionItem.school_id == user.school_id,
            QuestionItem.subject_id == subject_id,
            QuestionItem.status == enums.ItemStatus.APPROVED,
            QuestionItem.times_used > 0,
        )
        .order_by(QuestionItem.id)
    )
    if grade_number is not None:
        stmt = stmt.where(QuestionItem.grade_number == grade_number)
    rows = [_to_calibration_row(qi) for qi in db.execute(stmt).scalars().all()]
    rows.sort(key=_calibration_sort_key)
    return rows


@router.post("/items/{item_id}/retire", response_model=QuestionItemDetail)
def retire_item(item_id: UUID, user: CurrentUser, db: Session = Depends(get_db)):
    """Ngừng dùng câu 'bệnh' (Trưởng bộ môn/ADMIN) — giữ nguyên bản ghi để truy vết đề cũ."""
    item = _get_owned_item(db, user, item_id)
    if not rbac.can_review_question(db, user, item.subject_id):
        raise HTTPException(status_code=403, detail="Chỉ Trưởng bộ môn được ngừng dùng câu hỏi")
    if item.status != enums.ItemStatus.APPROVED:
        raise HTTPException(status_code=409, detail="Chỉ ngừng dùng được câu đang APPROVED")
    item.status = enums.ItemStatus.RETIRED
    db.commit()
    db.refresh(item)
    return _to_detail(item, _user_names(db, {item.created_by, item.reviewed_by}))

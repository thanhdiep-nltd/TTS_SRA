"""Thông báo: xem/đánh dấu đã đọc + soạn thông báo chủ động (BGH/Trưởng bộ môn).

Xem docs/exam_generation_ui_design.md mục C.6. RBAC phạm vi gửi được ép buộc trong
services/notifications.create_announcement — endpoint chỉ truyền payload qua, không tự quyết.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.deps import CurrentUser, get_db
from src.schemas.notifications import (
    AnnouncementCreate,
    AnnouncementResult,
    NotificationRead,
    RecipientOption,
    UnreadCountRead,
)
from src.services import notifications

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=list[NotificationRead])
def list_my_notifications(user: CurrentUser, db: Session = Depends(get_db), unread_only: bool = False, limit: int = 20):
    return notifications.list_notifications(db, user.id, unread_only=unread_only, limit=limit)


@router.get("/unread-count", response_model=UnreadCountRead)
def get_unread_count(user: CurrentUser, db: Session = Depends(get_db)):
    return UnreadCountRead(count=notifications.unread_count(db, user.id))


@router.post("/read-all")
def mark_all_read(user: CurrentUser, db: Session = Depends(get_db)):
    marked = notifications.mark_all_read(db, user.id)
    return {"marked": marked}


@router.post("/{notification_id}/read")
def mark_read(notification_id: int, user: CurrentUser, db: Session = Depends(get_db)):
    ok = notifications.mark_read(db, user.id, notification_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Thông báo không tồn tại")
    return {"status": "ok"}


@router.post("/announcements", response_model=AnnouncementResult, status_code=201)
def create_announcement(payload: AnnouncementCreate, user: CurrentUser, db: Session = Depends(get_db)):
    """Soạn thông báo: BGH (toàn trường/1 bộ môn/1 cá nhân) hoặc Trưởng BM (bộ môn/cá nhân trong bộ môn mình)."""
    try:
        count = notifications.create_announcement(db, user, payload)
    except notifications.AnnouncementPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return AnnouncementResult(recipients_count=count)


@router.get("/recipients", response_model=list[RecipientOption])
def list_recipients(user: CurrentUser, db: Session = Depends(get_db), subject_id: int | None = None):

    """Danh sách người có thể chọn làm người nhận khi soạn thông báo phạm vi INDIVIDUAL."""
    try:
        return notifications.list_recipient_candidates(db, user, subject_id)
    except notifications.AnnouncementPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

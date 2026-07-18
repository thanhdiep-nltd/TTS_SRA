"""DTO cho thông báo (sự kiện hệ thống + thông báo chủ động do người soạn).

Xem docs/exam_generation_ui_design.md mục C.6. Tầng schemas — không chứa logic DB/RBAC.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from src.models import enums
from src.schemas.common import ORMBase


class NotificationRead(ORMBase):
    id: UUID
    sender_id: UUID | None
    sender_name: str | None = None
    type: enums.NotificationType
    title: str
    message: str
    entity_type: str | None
    entity_id: UUID | None
    read_at: datetime | None
    created_at: datetime


class UnreadCountRead(BaseModel):
    count: int


class AnnouncementCreate(BaseModel):
    """Soạn thông báo chủ động. ``scope`` quyết định field bắt buộc đi kèm.

    - SCHOOL: không cần subject_id/recipient_user_id (chỉ ADMIN/PRINCIPAL).
    - SUBJECT: cần subject_id (BGH chọn môn bất kỳ; Trưởng BM bị ép về môn mình ở service).
    - INDIVIDUAL: cần recipient_user_id.
    """

    scope: enums.AnnouncementScope
    title: str = Field(min_length=1, max_length=255)
    message: str = Field(min_length=1)
    subject_id: UUID | None = None
    recipient_user_id: UUID | None = None

    @model_validator(mode="after")
    def _check_required_target(self) -> "AnnouncementCreate":
        if self.scope == enums.AnnouncementScope.SUBJECT and self.subject_id is None:
            raise ValueError("Phạm vi SUBJECT phải kèm subject_id")
        if self.scope == enums.AnnouncementScope.INDIVIDUAL and self.recipient_user_id is None:
            raise ValueError("Phạm vi INDIVIDUAL phải kèm recipient_user_id")
        return self


class AnnouncementResult(BaseModel):
    recipients_count: int


class RecipientOption(ORMBase):
    """Lựa chọn người nhận cho UI soạn thông báo (chỉ thông tin hiển thị, không nhạy cảm)."""

    id: UUID
    full_name: str

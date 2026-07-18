"""Thông báo: sự kiện hệ thống tự động + thông báo chủ động do BGH/Trưởng bộ môn soạn.

Sự kiện tự động (2 chiều — vòng phản hồi trách nhiệm sư phạm):
  - GV nộp/AI sinh câu mới (DRAFT) -> báo Trưởng bộ môn của môn đó.
  - Trưởng BM duyệt/từ chối câu -> báo lại tác giả (kèm lý do nếu từ chối).
  - Chốt đề chính thức -> báo người tạo ma trận + Trưởng bộ môn.

Thông báo chủ động (compose): BGH (ADMIN/PRINCIPAL) gửi toàn trường / 1 bộ môn bất kỳ / 1 cá
nhân bất kỳ. Trưởng bộ môn chỉ gửi được trong phạm vi bộ môn mình phụ trách (ép buộc ở RBAC
trong create_announcement — không tin payload từ client).

Xem docs/exam_generation_ui_design.md mục C.6.
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, aliased

from src.models import enums
from src.models.tables import ExamBlueprint, GeneratedExam, Notification, QuestionItem, Subject, TeacherAssignment, User
from src.schemas.notifications import AnnouncementCreate

_BROADCAST_ROLES = {enums.UserRole.ADMIN, enums.UserRole.PRINCIPAL, enums.UserRole.SUBJECT_HEAD}
_SCHOOL_WIDE_ROLES = {enums.UserRole.ADMIN, enums.UserRole.PRINCIPAL}


class AnnouncementPermissionError(Exception):
    """Không có quyền gửi thông báo theo phạm vi yêu cầu (ép buộc ở service, không tin client)."""


# ============================================================
# RESOLVE NGƯỜI NHẬN
# ============================================================


def _active_users_in_school(db: Session, school_id: UUID) -> list[UUID]:
    stmt = select(User.id).where(User.school_id == school_id, User.is_active.is_(True))
    return list(db.execute(stmt).scalars().all())


def _subject_member_ids(db: Session, school_id: UUID, subject_id: UUID) -> list[UUID]:
    """Thành viên bộ môn = GV có môn phụ trách (users.subject_id) khớp, cùng trường, đang hoạt động."""
    stmt = select(User.id).where(User.school_id == school_id, User.subject_id == subject_id, User.is_active.is_(True))
    return list(db.execute(stmt).scalars().all())


def _subject_head_id(db: Session, subject_id: UUID) -> UUID | None:
    """Trưởng bộ môn thật của môn (theo teacher_assignments, KHỚP rbac.can_review_question —
    KHÔNG dùng cột subjects.subject_head_id, cột này không được luồng phân công nào ghi vào)."""
    return (
        db.execute(
            select(TeacherAssignment.user_id).where(
                TeacherAssignment.role_context == enums.RoleContext.SUBJECT_HEAD,
                TeacherAssignment.subject_id == subject_id,
                TeacherAssignment.is_active.is_(True),
            )
        )
        .scalars()
        .first()
    )


def _own_subject_id_as_head(db: Session, user_id: UUID) -> UUID | None:
    """Bộ môn mà user_id đang là Trưởng bộ môn (None nếu không phải Trưởng BM của môn nào)."""
    return (
        db.execute(
            select(TeacherAssignment.subject_id).where(
                TeacherAssignment.role_context == enums.RoleContext.SUBJECT_HEAD,
                TeacherAssignment.user_id == user_id,
                TeacherAssignment.is_active.is_(True),
            )
        )
        .scalars()
        .first()
    )


# ============================================================
# TẠO THÔNG BÁO (lõi)
# ============================================================


def notify(
    db: Session,
    school_id: UUID,
    recipient_ids: list[UUID],
    type_: enums.NotificationType,
    title: str,
    message: str,
    sender_id: UUID | None = None,
    entity_type: str | None = None,
    entity_id: UUID | None = None,
) -> int:
    """Tạo thông báo cho nhiều người nhận (loại bỏ trùng lặp + không tự báo cho chính người gửi)."""
    targets = {r for r in recipient_ids if r is not None and r != sender_id}
    for recipient_id in targets:
        db.add(
            Notification(
                school_id=school_id,
                recipient_id=recipient_id,
                sender_id=sender_id,
                type=type_,
                title=title,
                message=message,
                entity_type=entity_type,
                entity_id=entity_id,
            )
        )
    db.commit()
    return len(targets)


# ============================================================
# SỰ KIỆN HỆ THỐNG TỰ ĐỘNG
# ============================================================


def notify_question_submitted_batch(db: Session, items: list[QuestionItem]) -> int:
    """Báo Trưởng bộ môn khi có câu hỏi mới (thủ công hoặc AI sinh) chờ duyệt."""
    if not items:
        return 0
    first = items[0]
    head_id = _subject_head_id(db, first.subject_id)
    if head_id is None:
        return 0
    subject = db.get(Subject, first.subject_id)
    count_text = "1 câu hỏi mới" if len(items) == 1 else f"{len(items)} câu hỏi mới"
    message = f"{count_text} (môn {subject.name}, khối {first.grade_number}) đang chờ bạn duyệt."
    # KHÔNG truyền sender_id=created_by: đây là nhiệm vụ "cần duyệt", không phải tin báo xã giao —
    # phải báo cả khi người tạo câu chính là Trưởng bộ môn (vẫn cần nhắc quay lại duyệt), nếu dùng
    # sender_id=created_by thì notify() sẽ tự loại trừ chính người nhận (coi là "tự báo cho mình").
    return notify(
        db,
        first.school_id,
        [head_id],
        enums.NotificationType.QUESTION_SUBMITTED,
        title="Có câu hỏi mới chờ duyệt",
        message=message,
        sender_id=None,
        entity_type="question_item",
        entity_id=first.id,
    )


def notify_generation_failed(
    db: Session, school_id: UUID, recipient_id: UUID, subject_id: UUID, grade_number: int, reason: str
) -> int:
    """Báo NGƯỜI BẤM SINH khi luồng nền thất bại — tránh 'hố đen' chờ 2 phút không biết vì sao."""
    subject = db.get(Subject, subject_id)
    subject_name = subject.name if subject else "?"
    return notify(
        db,
        school_id,
        [recipient_id],
        enums.NotificationType.GENERATION_FAILED,
        title="Sinh câu hỏi AI thất bại",
        message=f"Không sinh được câu hỏi (môn {subject_name}, khối {grade_number}). Lý do: {reason}",
        sender_id=None,
        entity_type="question_item",
        entity_id=None,
    )


def notify_item_reviewed(db: Session, item: QuestionItem, approved: bool, reason: str | None) -> int:
    """Báo lại tác giả kết quả duyệt — vòng phản hồi để GV biết sửa nếu bị từ chối."""
    subject = db.get(Subject, item.subject_id)
    verb = "đã được DUYỆT" if approved else "đã bị TỪ CHỐI"
    message = f"Câu hỏi của bạn (môn {subject.name}) {verb}."
    if reason:
        message += f" Lý do: {reason}"
    return notify(
        db,
        item.school_id,
        [item.created_by],
        enums.NotificationType.ITEM_REVIEWED,
        title="Kết quả duyệt câu hỏi",
        message=message,
        sender_id=item.reviewed_by,
        entity_type="question_item",
        entity_id=item.id,
    )


def notify_exam_finalized(db: Session, gen: GeneratedExam, blueprint: ExamBlueprint) -> int:
    """Báo người tạo ma trận + Trưởng bộ môn khi đề được chốt chính thức."""
    recipients = {gen.created_by}
    head_id = _subject_head_id(db, blueprint.subject_id)
    if head_id is not None:
        recipients.add(head_id)
    subject = db.get(Subject, blueprint.subject_id)
    message = f"Đề '{blueprint.title}' (môn {subject.name}) đã được chốt chính thức. Hãy map đề vào cột điểm."
    return notify(
        db,
        gen.school_id,
        list(recipients),
        enums.NotificationType.EXAM_FINALIZED,
        title="Đề thi đã chốt",
        message=message,
        sender_id=gen.created_by,
        entity_type="generated_exam",
        entity_id=gen.id,
    )


# ============================================================
# THÔNG BÁO CHỦ ĐỘNG (compose) — RBAC theo phạm vi
# ============================================================


def create_announcement(db: Session, sender: User, payload: AnnouncementCreate) -> int:
    """Soạn & gửi thông báo chủ động. Raise AnnouncementPermissionError nếu vượt phạm vi quyền.

    Không tin payload từ client cho phạm vi — luôn ép buộc theo vai trò thực tế của sender.
    """
    if sender.role not in _BROADCAST_ROLES:
        raise AnnouncementPermissionError("Vai trò của bạn không được soạn thông báo")

    if payload.scope == enums.AnnouncementScope.SCHOOL:
        if sender.role not in _SCHOOL_WIDE_ROLES:
            raise AnnouncementPermissionError("Chỉ Ban giám hiệu được gửi thông báo toàn trường")
        recipients = _active_users_in_school(db, sender.school_id)

    elif payload.scope == enums.AnnouncementScope.SUBJECT:
        subject_id = payload.subject_id
        if sender.role == enums.UserRole.SUBJECT_HEAD:
            own_subject_id = _own_subject_id_as_head(db, sender.id)
            if own_subject_id is None or subject_id != own_subject_id:
                raise AnnouncementPermissionError("Trưởng bộ môn chỉ gửi thông báo cho bộ môn mình phụ trách")
        subject = db.get(Subject, subject_id)
        if subject is None or subject.school_id != sender.school_id:
            raise AnnouncementPermissionError("Bộ môn không tồn tại")
        recipients = _subject_member_ids(db, sender.school_id, subject_id)

    else:  # INDIVIDUAL
        target = db.get(User, payload.recipient_user_id)
        if target is None or target.school_id != sender.school_id:
            raise AnnouncementPermissionError("Người nhận không tồn tại")
        if sender.role == enums.UserRole.SUBJECT_HEAD:
            own_subject_id = _own_subject_id_as_head(db, sender.id)
            if own_subject_id is None or target.subject_id != own_subject_id:
                raise AnnouncementPermissionError("Trưởng bộ môn chỉ gửi thông báo cho thành viên bộ môn mình")
        recipients = [target.id]

    return notify(
        db,
        sender.school_id,
        recipients,
        enums.NotificationType.ANNOUNCEMENT,
        title=payload.title,
        message=payload.message,
        sender_id=sender.id,
    )


def list_recipient_candidates(db: Session, sender: User, subject_id: UUID | None) -> list[User]:
    """Danh sách người có thể chọn làm người nhận (cho UI soạn thông báo INDIVIDUAL).

    Trưởng bộ môn chỉ thấy thành viên bộ môn mình (bỏ qua subject_id truyền vào — ép buộc).
    BGH: truyền subject_id để lọc theo 1 bộ môn, hoặc bỏ trống để xem toàn trường.
    """
    if sender.role not in _BROADCAST_ROLES:
        raise AnnouncementPermissionError("Vai trò của bạn không được xem danh sách người nhận")

    if sender.role == enums.UserRole.SUBJECT_HEAD:
        own_subject_id = _own_subject_id_as_head(db, sender.id)
        ids = _subject_member_ids(db, sender.school_id, own_subject_id) if own_subject_id else []
    elif subject_id is not None:
        ids = _subject_member_ids(db, sender.school_id, subject_id)
    else:
        ids = _active_users_in_school(db, sender.school_id)

    if not ids:
        return []
    return list(db.execute(select(User).where(User.id.in_(ids))).scalars().all())


# ============================================================
# ĐỌC / ĐÁNH DẤU ĐÃ ĐỌC
# ============================================================


def list_notifications(
    db: Session, recipient_id: UUID, unread_only: bool = False, limit: int = 20
) -> list[Notification]:
    sender_alias = aliased(User)

    stmt = (
        select(Notification, sender_alias.full_name.label("sender_name"))
        .select_from(Notification)
        .outerjoin(sender_alias, Notification.sender_id == sender_alias.id)
        .where(Notification.recipient_id == recipient_id)
    )
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    stmt = stmt.order_by(Notification.created_at.desc()).limit(limit)
    results = db.execute(stmt).all()

    notifications_list = []
    for notif, sender_name in results:
        notif.sender_name = sender_name if sender_name else "Hệ thống"
        notifications_list.append(notif)
    return notifications_list


def unread_count(db: Session, recipient_id: UUID) -> int:
    stmt = (
        select(func.count())
        .select_from(Notification)
        .where(Notification.recipient_id == recipient_id, Notification.read_at.is_(None))
    )
    return db.execute(stmt).scalar_one()


def mark_read(db: Session, recipient_id: UUID, notification_id: UUID) -> bool:
    notif = db.get(Notification, notification_id)
    if notif is None or notif.recipient_id != recipient_id:
        return False
    if notif.read_at is None:
        notif.read_at = datetime.now(UTC)
        db.commit()
    return True


def mark_all_read(db: Session, recipient_id: UUID) -> int:
    stmt = (
        update(Notification)
        .where(Notification.recipient_id == recipient_id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(UTC))
    )
    result = db.execute(stmt)
    db.commit()
    return result.rowcount

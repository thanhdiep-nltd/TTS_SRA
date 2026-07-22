from datetime import UTC
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models import enums
from src.models.tables import AiMessage, AiSession, AiSessionAttachment


def get_active_sessions(db: Session, user_id: int) -> list[AiSession]:
    """Lấy danh sách các session đang hoạt động của user, xếp theo updated_at mới nhất."""
    stmt = (
        select(AiSession).where(AiSession.user_id == user_id, AiSession.is_active).order_by(AiSession.updated_at.desc())
    )
    return list(db.execute(stmt).scalars().all())


def get_session(db: Session, session_id: UUID) -> AiSession | None:
    """Lấy thông tin của một chat session theo ID."""
    return db.get(AiSession, session_id)


def create_session(db: Session, user_id: int, title: str | None = None) -> AiSession:
    """Tạo một chat session mới."""
    session = AiSession(user_id=user_id, title=title)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session



def get_session_messages(db: Session, session_id: UUID, limit: int = 10) -> list[AiMessage]:
    """Lấy tối đa `limit` tin nhắn mới nhất của session, trả về theo thứ tự thời gian tăng dần."""
    stmt = (
        select(AiMessage).where(AiMessage.session_id == session_id).order_by(AiMessage.created_at.desc()).limit(limit)
    )
    messages = list(db.execute(stmt).scalars().all())
    # Đảo ngược danh sách để trả về thứ tự tăng dần (cũ nhất trước, mới nhất sau)
    messages.reverse()
    return messages


def create_message(
    db: Session,
    session_id: UUID,
    role: enums.AiSessionRole,
    content: str,
    generated_sql: str | None = None,
    sources: Any = None,
    model_used: str | None = None,
    latency_ms: int | None = None,
    thought_trace: Any = None,
    input_token_count: int | None = None,
    output_token_count: int | None = None,
    cost: float | None = None,
    llm_provider: str | None = None,
    guardrail_status: enums.GuardrailStatus | None = None,
) -> AiMessage:
    """Lưu một tin nhắn mới (user hoặc assistant) vào DB kèm thông số Telemetry."""
    message = AiMessage(
        session_id=session_id,
        role=role,
        content=content,
        generated_sql=generated_sql,
        sources=sources,
        model_used=model_used,
        latency_ms=latency_ms,
        thought_trace=thought_trace,
        input_token_count=input_token_count,
        output_token_count=output_token_count,
        cost=cost,
        llm_provider=llm_provider,
        guardrail_status=guardrail_status,
    )
    db.add(message)
    # Cập nhật updated_at của session tương ứng
    session = db.get(AiSession, session_id)
    if session:
        from sqlalchemy import func

        session.updated_at = func.now()

    db.commit()
    db.refresh(message)
    return message


def update_message_feedback(
    db: Session,
    message_id: UUID,
    rating: int,
    feedback_tag: str | None = None,
    feedback_text: str | None = None,
) -> AiMessage | None:
    """Cập nhật đánh giá rating (1 hoặc -1), nhãn phân loại feedback_tag và nhận xét của người dùng."""
    from datetime import datetime

    message = db.get(AiMessage, message_id)
    if message:
        message.rating = rating
        message.feedback_tag = feedback_tag
        message.feedback_text = feedback_text
        message.feedback_at = datetime.now(UTC)
        db.commit()
        db.refresh(message)
    return message


def update_session_title(db: Session, session: AiSession, title: str) -> AiSession:
    """Cập nhật tiêu đề của session."""
    session.title = title
    db.commit()
    db.refresh(session)
    return session


def soft_delete_session(db: Session, session: AiSession) -> None:
    """Ẩn session (is_active = False)."""
    session.is_active = False
    db.commit()


def count_attachments(db: Session, session_id: UUID) -> int:
    """Đếm số file đã đính kèm trong session (để giới hạn chat_attachment_max_files_per_session)."""
    stmt = select(AiSessionAttachment).where(AiSessionAttachment.session_id == session_id)
    return len(list(db.execute(stmt).scalars().all()))


def create_attachment(
    db: Session,
    session_id: UUID,
    uploaded_by: int,
    file_name: str,
    stored_name: str,
    file_type: enums.FileType,
    extracted_text: str,
    char_count: int,
    truncated: bool,
) -> AiSessionAttachment:
    """Lưu metadata + nội dung trích xuất của 1 file đính kèm chat."""
    attachment = AiSessionAttachment(
        session_id=session_id,
        uploaded_by=uploaded_by,
        file_name=file_name,
        stored_name=stored_name,
        file_type=file_type,
        extracted_text=extracted_text,
        char_count=char_count,
        truncated=truncated,
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return attachment


def get_session_attachments(db: Session, session_id: UUID) -> list[AiSessionAttachment]:
    """Lấy toàn bộ file đính kèm của session, theo thứ tự thời gian tăng dần."""
    stmt = (
        select(AiSessionAttachment)
        .where(AiSessionAttachment.session_id == session_id)
        .order_by(AiSessionAttachment.created_at.asc())
    )
    return list(db.execute(stmt).scalars().all())



def get_attachment(db: Session, attachment_id: int) -> AiSessionAttachment | None:
    return db.get(AiSessionAttachment, attachment_id)



def delete_attachment(db: Session, attachment: AiSessionAttachment) -> None:
    db.delete(attachment)
    db.commit()

"""Duyệt HÀNG LOẠT toàn bộ câu hỏi DRAFT/REVIEW trong ngân hàng đề thi — CHỈ để có dữ liệu demo
(bảng "Đã duyệt" có nội dung khi trình bày), KHÔNG phải duyệt học thuật thật.

QUAN TRỌNG: hệ thống thiết kế HITL (Human-in-the-loop) — duyệt câu hỏi LUÔN phải do Trưởng bộ môn
đọc và xác nhận đúng/sai nội dung (xem docs/exam_generation_design.md). Script này KHÔNG thay thế
việc đó: nó chỉ gán `reviewed_by` = đúng người có quyền duyệt môn đó (Trưởng bộ môn nếu có phân
công thật trong `teacher_assignments`, fallback ADMIN nếu môn chưa có Trưởng bộ môn) rồi set
APPROVED, để dữ liệu demo nhất quán với RBAC thật. KHÔNG gửi notify_item_reviewed (tránh tạo thông
báo "đã duyệt" giả tới tác giả câu, vì đây không phải phản hồi duyệt thật).

Idempotent: chỉ động tới item đang DRAFT/REVIEW; chạy lại không ảnh hưởng item đã APPROVED/REJECTED.
Chạy: python scripts/approve_pending_questions_demo.py
"""

from datetime import UTC, datetime

from sqlalchemy import select

from src.db.session import SessionLocal
from src.models import enums
from src.models.tables import QuestionItem, TeacherAssignment, User


def _subject_head_id(db, subject_id) -> str | None:
    return db.execute(
        select(TeacherAssignment.user_id).where(
            TeacherAssignment.role_context == enums.RoleContext.SUBJECT_HEAD,
            TeacherAssignment.subject_id == subject_id,
        )
    ).scalars().first()


def _fallback_admin_id(db, school_id) -> str | None:
    return db.execute(select(User.id).where(User.role == enums.UserRole.ADMIN, User.school_id == school_id)).scalars().first()


def main() -> None:
    db = SessionLocal()
    try:
        pending = db.execute(
            select(QuestionItem).where(QuestionItem.status.in_([enums.ItemStatus.DRAFT, enums.ItemStatus.REVIEW]))
        ).scalars().all()

        reviewer_cache: dict = {}
        now = datetime.now(UTC)
        n = 0
        for item in pending:
            if item.subject_id not in reviewer_cache:
                reviewer_cache[item.subject_id] = _subject_head_id(db, item.subject_id) or _fallback_admin_id(
                    db, item.school_id
                )
            reviewer_id = reviewer_cache[item.subject_id]
            if reviewer_id is None:
                continue  # không tìm được ai có quyền duyệt môn này -> bỏ qua, không tự ý gán bừa
            item.status = enums.ItemStatus.APPROVED
            item.reviewed_by = reviewer_id
            item.reviewed_at = now
            n += 1
        db.commit()
        print(f"Done. Da duyet (demo) {n}/{len(pending)} cau dang cho duyet.")
    finally:
        db.close()


if __name__ == "__main__":
    main()

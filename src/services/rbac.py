"""Row-Level Security cho điểm số theo vai trò + phân công giảng dạy.

Quy tắc (theo kế hoạch triển khai):
- ADMIN, PRINCIPAL: xem toàn trường.
- GRADE_HEAD (Cấp 1): xem mọi lớp trong khối phụ trách (read-only).
- HOMEROOM_PRIMARY / HOMEROOM_SECONDARY: xem mọi điểm của lớp chủ nhiệm.
- SUBJECT_TEACHER: xem (và nhập) môn mình dạy ở các lớp được phân công.
- SUBJECT_HEAD: xem môn phụ trách ở mọi lớp (read-only).

Quyền GHI điểm: chỉ ADMIN, HOMEROOM_PRIMARY (lớp mình, mọi môn),
và SUBJECT_TEACHER (đúng môn + đúng lớp được phân công).
"""

from uuid import UUID

from sqlalchemy import and_, false, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from src.models import enums
from src.models.tables import Class, Grade, Score, Subject, TeacherAssignment, User

FULL_ACCESS_ROLES = {enums.UserRole.ADMIN, enums.UserRole.PRINCIPAL}


def _active_assignments(db: Session, user_id: UUID) -> list[TeacherAssignment]:
    stmt = select(TeacherAssignment).where(
        TeacherAssignment.user_id == user_id,
        TeacherAssignment.is_active.is_(True),
    )
    return list(db.execute(stmt).scalars().all())


def load_assignments(db: Session, user_id: UUID) -> list[TeacherAssignment]:
    """Tải phân công đang hoạt động của user 1 lần — dùng khi cần gọi `can_write_score` nhiều
    lần trong 1 request (vd batch) để tránh N+1 query."""
    return _active_assignments(db, user_id)


def accessible_score_filter(db: Session, user: User) -> ColumnElement | None:
    """Trả điều kiện WHERE giới hạn điểm user được xem.

    Giới hạn nghiêm ngặt theo school_id của user để tránh rò rỉ dữ liệu giữa các trường.
    """
    school_filter = Score.class_id.in_(select(Class.id).join(Grade).where(Grade.school_id == user.school_id))

    if user.role in FULL_ACCESS_ROLES:
        return school_filter

    conditions: list[ColumnElement] = []
    grade_ids: list[UUID] = []
    for a in _active_assignments(db, user.id):
        if a.role_context == enums.RoleContext.GRADE_HEAD and a.grade_id:
            grade_ids.append(a.grade_id)
        elif (
            a.role_context in (enums.RoleContext.HOMEROOM_PRIMARY, enums.RoleContext.HOMEROOM_SECONDARY) and a.class_id
        ):
            conditions.append(Score.class_id == a.class_id)
        elif a.role_context == enums.RoleContext.SUBJECT_TEACHER and a.subject_id and a.class_id:
            conditions.append(and_(Score.subject_id == a.subject_id, Score.class_id == a.class_id))
        elif a.role_context == enums.RoleContext.SUBJECT_HEAD and a.subject_id:
            conditions.append(Score.subject_id == a.subject_id)

    if grade_ids:
        conditions.append(Score.class_id.in_(select(Class.id).where(Class.grade_id.in_(grade_ids))))

    if not conditions:
        return false()
    return and_(school_filter, or_(*conditions))


def accessible_class_ids(db: Session, user: User) -> list[UUID] | None:
    """Trả ID các lớp user được phép truy cập (theo phân công).

    Quy ước trả về:
    - ``None``: không giới hạn theo lớp (xem mọi lớp trong trường) — ADMIN/PRINCIPAL
      và Trưởng bộ môn (xem môn mình ở mọi lớp).
    - ``list``: tập lớp cụ thể được phép (có thể rỗng nếu không có quyền lớp nào).

    Việc giới hạn theo ``school_id`` do tầng endpoint đảm nhiệm.
    """
    if user.role in FULL_ACCESS_ROLES:
        return None

    class_ids: set[UUID] = set()
    grade_ids: list[UUID] = []
    for a in _active_assignments(db, user.id):
        if a.role_context == enums.RoleContext.SUBJECT_HEAD:
            return None  # Trưởng bộ môn: xem môn phụ trách ở mọi lớp.
        if a.role_context == enums.RoleContext.GRADE_HEAD and a.grade_id:
            grade_ids.append(a.grade_id)
        elif a.class_id:  # HOMEROOM_* và SUBJECT_TEACHER đều gắn class_id.
            class_ids.add(a.class_id)

    if grade_ids:
        rows = db.execute(select(Class.id).where(Class.grade_id.in_(grade_ids))).scalars().all()
        class_ids.update(rows)
    return list(class_ids)


def scope_summary_for_user(db: Session, user: User) -> str:
    """Mô tả phạm vi phân quyền hiện tại của user dưới dạng chuỗi thân thiện (cho tool báo ACCESS_DENIED).

    Quy ước:
    - ADMIN/PRINCIPAL → "toàn trường (không giới hạn)".
    - Trưởng bộ môn → môn phụ trách ở mọi lớp.
    - Trưởng khối → mọi lớp trong khối phụ trách.
    - GV chủ nhiệm/bộ môn → các lớp/môn được phân công cụ thể.
    - Không có phân công → không thể truy cập dữ liệu điểm.
    """
    if user.role in FULL_ACCESS_ROLES:
        return "toàn trường (không giới hạn)"

    class_ids: set[UUID] = set()
    grade_desc: set[str] = set()
    subject_desc: set[str] = set()
    for a in _active_assignments(db, user.id):
        if a.role_context == enums.RoleContext.GRADE_HEAD and a.grade_id:
            grade = db.get(Grade, a.grade_id)
            if grade is not None:
                grade_desc.add(f"khối {grade.grade_number}")
        elif a.role_context == enums.RoleContext.SUBJECT_HEAD and a.subject_id:
            subject = db.get(Subject, a.subject_id)
            if subject is not None:
                subject_desc.add(f"môn {subject.name}")
        elif a.class_id:
            class_ids.add(a.class_id)
            if a.subject_id:
                subject = db.get(Subject, a.subject_id)
                if subject is not None:
                    subject_desc.add(f"môn {subject.name}")

    parts: list[str] = []
    if grade_desc:
        parts.append(", ".join(sorted(grade_desc)))
    if class_ids:
        class_names = db.execute(select(Class.name).where(Class.id.in_(class_ids))).scalars().all()
        parts.append("lớp " + ", ".join(sorted(class_names)))
    if subject_desc:
        parts.append(", ".join(sorted(subject_desc)))

    if not parts:
        return "không có phân công (không thể truy cập dữ liệu điểm)"
    return "; ".join(parts)


def rbac_denied_message(scope: str) -> str:
    """Tín hiệu ACCESS_DENIED chuẩn để agent DỪNG NGAY thay vì coi là "không có dữ liệu"."""
    return (
        "ACCESS_DENIED: Tài khoản của bạn không có quyền truy cập dữ liệu này — "
        "dữ liệu nằm ngoài phạm vi phân quyền hiện tại. "
        f"Phạm vi bạn được phép truy cập: {scope}."
    )


def can_write_score(
    db: Session, user: User, subject_id: UUID, class_id: UUID, assignments: list[TeacherAssignment] | None = None
) -> bool:
    """Kiểm tra user có quyền nhập/sửa điểm cho (môn, lớp) này không.

    `assignments`: truyền sẵn danh sách phân công đã tải (vd khi kiểm nhiều dòng liên tiếp
    trong 1 request — batch) để tránh N+1 query lặp lại `_active_assignments` cho mỗi lần gọi.
    """
    if user.role == enums.UserRole.ADMIN:
        return True
    for a in assignments if assignments is not None else _active_assignments(db, user.id):
        if a.role_context == enums.RoleContext.HOMEROOM_PRIMARY and a.class_id == class_id:
            return True
        if (
            a.role_context == enums.RoleContext.SUBJECT_TEACHER
            and a.subject_id == subject_id
            and a.class_id == class_id
        ):
            return True
    return False


def can_edit_subject_eval(db: Session, user: User, subject_id: UUID, class_id: UUID) -> bool:
    """Quyền nhập đánh giá học tập (Đạt/CĐ hoặc nhận xét) cho một môn ở một lớp.

    Giống quyền ghi điểm: GV bộ môn đúng môn+lớp; GV chủ nhiệm cấp 1 (dạy mọi môn); ADMIN.
    """
    return can_write_score(db, user, subject_id, class_id)


def can_edit_term_report(db: Session, user: User, class_id: UUID) -> bool:
    """Quyền nhập hạnh kiểm + đánh giá chung: GV chủ nhiệm của lớp, hoặc ADMIN."""
    if user.role == enums.UserRole.ADMIN:
        return True
    homeroom = (enums.RoleContext.HOMEROOM_PRIMARY, enums.RoleContext.HOMEROOM_SECONDARY)
    return any(a.role_context in homeroom and a.class_id == class_id for a in _active_assignments(db, user.id))


def can_map(
    db: Session,
    user: User,
    category: enums.ScoreCategory,
    subject_id: UUID,
    class_id: UUID | None,
    grade_id: UUID | None,
) -> bool:
    """Quyền map đề thi vào cột: GV bộ môn → TX theo lớp; Trưởng bộ môn → GK/CK toàn khối môn mình."""
    if user.role == enums.UserRole.ADMIN:
        return True
    assigns = _active_assignments(db, user.id)
    if category == enums.ScoreCategory.REGULAR:
        return any(
            a.role_context == enums.RoleContext.SUBJECT_TEACHER
            and a.subject_id == subject_id
            and a.class_id == class_id
            for a in assigns
        )
    if category in (enums.ScoreCategory.MIDTERM, enums.ScoreCategory.FINAL):
        return any(a.role_context == enums.RoleContext.SUBJECT_HEAD and a.subject_id == subject_id for a in assigns)
    return False  # ORAL không cho map


def can_manage_question_bank(db: Session, user: User, subject_id: UUID) -> bool:
    """Quyền tạo/sửa câu hỏi + ráp đề cho một môn: GV bộ môn hoặc Trưởng bộ môn của môn đó, hoặc ADMIN."""
    if user.role == enums.UserRole.ADMIN:
        return True
    subject_roles = (enums.RoleContext.SUBJECT_TEACHER, enums.RoleContext.SUBJECT_HEAD)
    return any(a.role_context in subject_roles and a.subject_id == subject_id for a in _active_assignments(db, user.id))


def can_review_question(db: Session, user: User, subject_id: UUID) -> bool:
    """Quyền DUYỆT câu hỏi + chốt đề chính thức: chỉ Trưởng bộ môn của môn đó hoặc ADMIN.

    Đề GK/CK do Trưởng bộ môn chịu trách nhiệm (khớp can_map cho MIDTERM/FINAL).
    """
    if user.role == enums.UserRole.ADMIN:
        return True
    return any(
        a.role_context == enums.RoleContext.SUBJECT_HEAD and a.subject_id == subject_id
        for a in _active_assignments(db, user.id)
    )

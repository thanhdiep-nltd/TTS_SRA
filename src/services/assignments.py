"""Nghiệp vụ phân công giảng dạy.

Quy tắc:
- Mỗi giáo viên chỉ chủ nhiệm tối đa MỘT lớp trong một năm học.
- Giáo viên bộ môn có thể dạy môn phụ trách ở nhiều lớp.
- Khi nhận chủ nhiệm, GV mặc định dạy luôn môn phụ trách (User.subject_id) cho lớp đó.
"""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models import enums
from src.models.tables import AcademicYear, Class, Grade, Subject, TeacherAssignment, User
from src.schemas.user import AssignmentCreate

HOMEROOM_CONTEXTS = (enums.RoleContext.HOMEROOM_PRIMARY, enums.RoleContext.HOMEROOM_SECONDARY)

# role_context -> (field bắt buộc, field cấm). Khớp CHECK constraint assignment_consistency trong DB.
CONTEXT_FIELD_RULES: dict[enums.RoleContext, tuple[frozenset[str], frozenset[str]]] = {
    enums.RoleContext.SUBJECT_TEACHER: (frozenset({"class_id", "subject_id"}), frozenset({"grade_id"})),
    enums.RoleContext.HOMEROOM_PRIMARY: (frozenset({"class_id"}), frozenset({"subject_id", "grade_id"})),
    enums.RoleContext.HOMEROOM_SECONDARY: (frozenset({"class_id"}), frozenset({"subject_id", "grade_id"})),
    enums.RoleContext.GRADE_HEAD: (frozenset({"grade_id"}), frozenset({"class_id", "subject_id"})),
    enums.RoleContext.SUBJECT_HEAD: (frozenset({"subject_id"}), frozenset({"class_id", "grade_id"})),
}

# Vai trò tài khoản KHÔNG được nhận bất kỳ phân công giảng dạy nào (BGH/quản trị).
# Lưu ý: RBAC thực tế (src/services/rbac.py) hoàn toàn dựa vào TeacherAssignment.role_context,
# KHÔNG dựa vào User.role — dữ liệu thật chỉ dùng role ADMIN/PRINCIPAL/SUBJECT_HEAD/SUBJECT_TEACHER;
# một SUBJECT_TEACHER hoàn toàn có thể giữ role_context HOMEROOM_*/GRADE_HEAD qua phân công.
# Các UserRole HOMEROOM_TEACHER_*/GRADE_HEAD_PRIMARY chỉ là nhãn hiển thị tùy chọn, không phải
# điều kiện bắt buộc để nhận role_context tương ứng.
NO_ASSIGNMENT_ROLES = frozenset({enums.UserRole.ADMIN, enums.UserRole.PRINCIPAL})

_FIELD_LABELS = {"class_id": "Lớp", "grade_id": "Khối", "subject_id": "Môn"}


def validate_context_fields(payload: AssignmentCreate) -> None:
    """Kiểm tra tổ hợp Lớp/Khối/Môn bắt buộc và cấm theo role_context."""
    required, forbidden = CONTEXT_FIELD_RULES[payload.role_context]
    missing = [_FIELD_LABELS[f] for f in sorted(required) if getattr(payload, f) is None]
    extra = [_FIELD_LABELS[f] for f in sorted(forbidden) if getattr(payload, f) is not None]
    if missing:
        raise HTTPException(422, f"Phân công {payload.role_context.value}: thiếu {', '.join(missing)}")
    if extra:
        raise HTTPException(422, f"Phân công {payload.role_context.value}: không được kèm {', '.join(extra)}")


def validate_role_context(user: User, role_context: enums.RoleContext) -> None:
    """Kiểm tra vai trò tài khoản có được nhận phân công giảng dạy không (ADMIN/PRINCIPAL thì không)."""
    if user.role in NO_ASSIGNMENT_ROLES:
        raise HTTPException(422, f"Vai trò tài khoản {user.role} không thể nhận phân công {role_context.value}")


def _existing_homeroom(db: Session, payload: AssignmentCreate) -> TeacherAssignment | None:
    """Phân công chủ nhiệm đang hoạt động của GV trong năm học (nếu có)."""
    stmt = select(TeacherAssignment).where(
        TeacherAssignment.user_id == payload.user_id,
        TeacherAssignment.academic_year_id == payload.academic_year_id,
        TeacherAssignment.role_context.in_(HOMEROOM_CONTEXTS),
        TeacherAssignment.is_active.is_(True),
    )
    return db.execute(stmt).scalars().first()


def _auto_subject_teacher(db: Session, payload: AssignmentCreate) -> None:
    """Tự tạo phân công GV bộ môn cho môn phụ trách của GV tại lớp chủ nhiệm."""
    user = db.get(User, payload.user_id)
    if user is None or user.subject_id is None:
        return
    stmt = select(TeacherAssignment).where(
        TeacherAssignment.user_id == payload.user_id,
        TeacherAssignment.academic_year_id == payload.academic_year_id,
        TeacherAssignment.role_context == enums.RoleContext.SUBJECT_TEACHER,
        TeacherAssignment.class_id == payload.class_id,
        TeacherAssignment.subject_id == user.subject_id,
    )
    if db.execute(stmt).scalars().first() is not None:
        return
    db.add(
        TeacherAssignment(
            user_id=payload.user_id,
            academic_year_id=payload.academic_year_id,
            role_context=enums.RoleContext.SUBJECT_TEACHER,
            class_id=payload.class_id,
            subject_id=user.subject_id,
        )
    )


def _duplicate_exists(db: Session, payload: AssignmentCreate) -> bool:
    """True nếu đã có phân công active trùng hệt (user, năm, context, lớp/khối/môn)."""
    stmt = select(TeacherAssignment.id).where(
        TeacherAssignment.user_id == payload.user_id,
        TeacherAssignment.academic_year_id == payload.academic_year_id,
        TeacherAssignment.role_context == payload.role_context,
        TeacherAssignment.class_id == payload.class_id,
        TeacherAssignment.grade_id == payload.grade_id,
        TeacherAssignment.subject_id == payload.subject_id,
        TeacherAssignment.is_active.is_(True),
    )
    return db.execute(stmt).scalar_one_or_none() is not None


def _class_homeroom_holder(db: Session, payload: AssignmentCreate) -> str | None:
    """Tên GV khác đang chủ nhiệm lớp này trong năm học (nếu có)."""
    stmt = (
        select(User.full_name)
        .join(TeacherAssignment, TeacherAssignment.user_id == User.id)
        .where(
            TeacherAssignment.class_id == payload.class_id,
            TeacherAssignment.academic_year_id == payload.academic_year_id,
            TeacherAssignment.role_context.in_(HOMEROOM_CONTEXTS),
            TeacherAssignment.is_active.is_(True),
            TeacherAssignment.user_id != payload.user_id,
        )
    )
    return db.execute(stmt).scalars().first()


def _validate_refs(db: Session, payload: AssignmentCreate, school_id: UUID) -> None:
    """Lớp/Khối/Môn phải thuộc trường của GV; lớp phải đúng niên khóa đã chọn."""
    if payload.class_id is not None:
        stmt = (
            select(Class.academic_year_id)
            .join(Grade, Class.grade_id == Grade.id)
            .where(Class.id == payload.class_id, Grade.school_id == school_id)
        )
        year_id = db.execute(stmt).scalar_one_or_none()
        if year_id is None:
            raise HTTPException(422, "Lớp không thuộc trường của giáo viên")
        if year_id != payload.academic_year_id:
            raise HTTPException(422, "Lớp không thuộc niên khóa đã chọn")
    if payload.grade_id is not None:
        stmt = select(Grade.id).where(Grade.id == payload.grade_id, Grade.school_id == school_id)
        if db.execute(stmt).scalar_one_or_none() is None:
            raise HTTPException(422, "Khối không thuộc trường của giáo viên")
    if payload.subject_id is not None:
        stmt = select(Subject.id).where(Subject.id == payload.subject_id, Subject.school_id == school_id)
        if db.execute(stmt).scalar_one_or_none() is None:
            raise HTTPException(422, "Môn không thuộc trường của giáo viên")


def _validate_year(db: Session, payload: AssignmentCreate, school_id: UUID) -> None:
    """Niên khóa phải thuộc trường của GV."""
    stmt = select(AcademicYear.id).where(
        AcademicYear.id == payload.academic_year_id, AcademicYear.school_id == school_id
    )
    if db.execute(stmt).scalar_one_or_none() is None:
        raise HTTPException(422, "Niên khóa không thuộc trường của giáo viên")


def deactivate_mismatched(db: Session, user: User, new_role: enums.UserRole) -> int:
    """Đổi sang vai trò BGH/quản trị (ADMIN/PRINCIPAL) thì vô hiệu mọi phân công đang có.

    Các vai trò giảng dạy khác (SUBJECT_TEACHER, SUBJECT_HEAD...) đều có thể giữ mọi
    role_context qua phân công, nên đổi qua lại giữa các vai trò này không ảnh hưởng phân công.
    """
    if new_role not in NO_ASSIGNMENT_ROLES:
        return 0
    stmt = select(TeacherAssignment).where(TeacherAssignment.user_id == user.id, TeacherAssignment.is_active.is_(True))
    mismatched = list(db.execute(stmt).scalars().all())
    for assignment in mismatched:
        assignment.is_active = False
    return len(mismatched)


def _validate_create(db: Session, payload: AssignmentCreate) -> User:
    """Chạy toàn bộ kiểm tra trước khi tạo phân công; trả về GV được phân công."""
    user = db.get(User, payload.user_id)
    if user is None:
        raise HTTPException(404, "Giáo viên không tồn tại")
    validate_context_fields(payload)
    validate_role_context(user, payload.role_context)
    _validate_year(db, payload, user.school_id)
    _validate_refs(db, payload, user.school_id)
    if _duplicate_exists(db, payload):
        raise HTTPException(409, "Phân công này đã tồn tại")
    if payload.role_context in HOMEROOM_CONTEXTS:
        existing = _existing_homeroom(db, payload)
        if existing is not None and existing.class_id != payload.class_id:
            raise HTTPException(409, "Giáo viên đã chủ nhiệm một lớp khác trong năm học này")
        holder = _class_homeroom_holder(db, payload)
        if holder is not None:
            raise HTTPException(409, f"Lớp đã có giáo viên chủ nhiệm: {holder}")
    return user


def create_assignment(db: Session, payload: AssignmentCreate) -> TeacherAssignment:
    """Tạo phân công kèm enforce toàn bộ quy tắc + tự dạy môn phụ trách khi nhận chủ nhiệm."""
    _validate_create(db, payload)
    assignment = TeacherAssignment(**payload.model_dump())
    db.add(assignment)
    db.flush()
    if payload.role_context in HOMEROOM_CONTEXTS:
        _auto_subject_teacher(db, payload)
    db.commit()
    db.refresh(assignment)
    return assignment


SLOT_ROLE_CONTEXTS = (
    enums.RoleContext.HOMEROOM_PRIMARY,
    enums.RoleContext.HOMEROOM_SECONDARY,
    enums.RoleContext.SUBJECT_TEACHER,
)


def _deactivate_slot_occupants(db: Session, payload: AssignmentCreate) -> None:
    """Vô hiệu (KHÔNG commit) phân công đang giữ đúng vị trí lớp/môn — dọn chỗ để gán GV mới."""
    stmt = select(TeacherAssignment).where(
        TeacherAssignment.academic_year_id == payload.academic_year_id,
        TeacherAssignment.class_id == payload.class_id,
        TeacherAssignment.is_active.is_(True),
    )
    if payload.role_context in HOMEROOM_CONTEXTS:
        stmt = stmt.where(TeacherAssignment.role_context.in_(HOMEROOM_CONTEXTS))
    else:
        stmt = stmt.where(
            TeacherAssignment.role_context == enums.RoleContext.SUBJECT_TEACHER,
            TeacherAssignment.subject_id == payload.subject_id,
        )
    for occupant in db.execute(stmt).scalars().all():
        occupant.is_active = False
    db.flush()


def reassign_class_slot(db: Session, payload: AssignmentCreate) -> TeacherAssignment:
    """Gán GV mới vào 1 vị trí lớp (chủ nhiệm/GV bộ môn), tự vô hiệu người đang giữ (nếu có).

    Chạy trong 1 transaction: nếu gán mới thất bại (GV đã chủ nhiệm lớp khác, GV không tồn tại...),
    KHÔNG có db.commit() nào chạy -> việc vô hiệu người cũ cũng bị rollback khi session đóng
    (xem src/db/session.py get_db) -> lớp không bao giờ bị "mất trắng" phân công giữa chừng.

    Khóa dòng `classes` (SELECT ... FOR UPDATE) trước khi đọc/ghi occupant để 2 request
    reassign đồng thời trên CÙNG 1 lớp bị serialize — tránh race condition tạo ra 2 phân
    công active cho cùng 1 vị trí (lớp+môn hoặc chủ nhiệm lớp).
    """
    if payload.role_context not in SLOT_ROLE_CONTEXTS:
        raise HTTPException(422, "Chỉ hỗ trợ gán chủ nhiệm hoặc GV bộ môn theo lớp")
    if payload.class_id is None:
        raise HTTPException(422, "Thiếu lớp cần phân công")
    db.execute(select(Class.id).where(Class.id == payload.class_id).with_for_update())
    _deactivate_slot_occupants(db, payload)
    _validate_create(db, payload)
    assignment = TeacherAssignment(**payload.model_dump())
    db.add(assignment)
    db.flush()
    if payload.role_context in HOMEROOM_CONTEXTS:
        _auto_subject_teacher(db, payload)
    db.commit()
    db.refresh(assignment)
    return assignment


# ============================================================
# Coverage (tab "Theo lớp") & options cho form phân công
# ============================================================


def _match_level(applicable: enums.SchoolLevel, class_level: enums.SchoolLevel) -> bool:
    """Môn có áp dụng cho cấp học của lớp không (ALL = mọi cấp)."""
    return applicable in (enums.SchoolLevel.ALL, class_level)


def build_coverage_rows(classes: list, subjects: list, homeroom: dict, subject_teachers: dict) -> list[dict]:
    """Ghép độ phủ phân công cho từng lớp từ dữ liệu đã truy vấn (pure — test offline được)."""
    rows: list[dict] = []
    for cls in classes:
        applicable = [s for s in subjects if _match_level(s.applicable_level, cls.school_level)]
        rows.append(
            {
                "class_id": cls.id,
                "name": cls.name,
                "grade_name": cls.grade_name,
                "homeroom_teacher": homeroom.get(cls.id),
                "subjects": [
                    {
                        "subject_id": s.id,
                        "name": s.name,
                        "teacher_name": subject_teachers.get((cls.id, s.id)),
                    }
                    for s in applicable
                ],
            }
        )
    return rows


def _coverage_classes(db: Session, year: AcademicYear) -> list:
    """Các lớp của niên khóa kèm tên khối + cấp học, sắp theo khối/tên."""
    stmt = (
        select(Class.id, Class.name, Grade.name.label("grade_name"), Grade.school_level)
        .join(Grade, Class.grade_id == Grade.id)
        .where(Class.academic_year_id == year.id, Grade.school_id == year.school_id)
        .order_by(Grade.grade_number, Class.name)
    )
    return list(db.execute(stmt).all())


def _coverage_assignments(db: Session, year: AcademicYear) -> tuple[dict, dict]:
    """Map chủ nhiệm theo lớp + map GV bộ môn theo (lớp, môn) trong niên khóa."""
    stmt = (
        select(TeacherAssignment.role_context, TeacherAssignment.class_id, TeacherAssignment.subject_id, User.full_name)
        .join(User, TeacherAssignment.user_id == User.id)
        .where(TeacherAssignment.academic_year_id == year.id, TeacherAssignment.is_active.is_(True))
    )
    homeroom: dict = {}
    subject_teachers: dict = {}
    for role_context, class_id, subject_id, name in db.execute(stmt).all():
        if role_context in HOMEROOM_CONTEXTS:
            homeroom[class_id] = name
        elif role_context == enums.RoleContext.SUBJECT_TEACHER:
            subject_teachers[(class_id, subject_id)] = name
    return homeroom, subject_teachers


def build_coverage(db: Session, year: AcademicYear) -> list[dict]:
    """Độ phủ phân công (chủ nhiệm + GV từng môn) của mọi lớp trong một niên khóa."""
    subjects_stmt = select(Subject.id, Subject.name, Subject.applicable_level).where(
        Subject.school_id == year.school_id, Subject.is_active.is_(True)
    )
    subjects = list(db.execute(subjects_stmt).all())
    homeroom, subject_teachers = _coverage_assignments(db, year)
    return build_coverage_rows(_coverage_classes(db, year), subjects, homeroom, subject_teachers)


def build_assignment_options(db: Session, target: User) -> dict:
    """Dữ liệu dropdown form phân công — theo TRƯỜNG CỦA GV được phân công."""
    years = (
        db.execute(
            select(AcademicYear)
            .where(AcademicYear.school_id == target.school_id)
            .order_by(AcademicYear.start_date.desc())
        )
        .scalars()
        .all()
    )
    grades = (
        db.execute(select(Grade).where(Grade.school_id == target.school_id).order_by(Grade.grade_number))
        .scalars()
        .all()
    )
    classes = db.execute(
        select(Class.id, Class.name, Class.academic_year_id)
        .join(Grade, Class.grade_id == Grade.id)
        .where(Grade.school_id == target.school_id)
        .order_by(Class.name)
    ).all()
    subjects = (
        db.execute(
            select(Subject)
            .where(Subject.school_id == target.school_id, Subject.is_active.is_(True))
            .order_by(Subject.name)
        )
        .scalars()
        .all()
    )
    allowed_contexts = () if target.role in NO_ASSIGNMENT_ROLES else sorted(enums.RoleContext)
    return {
        "allowed_contexts": allowed_contexts,
        "years": [{"id": y.id, "name": y.name, "is_current": y.is_current} for y in years],
        "classes": [{"id": c.id, "name": c.name, "academic_year_id": c.academic_year_id} for c in classes],
        "grades": [{"id": g.id, "name": g.name} for g in grades],
        "subjects": [{"id": s.id, "name": s.name} for s in subjects],
    }


def list_school_teachers(db: Session, school_id: UUID) -> list:
    """GV (không phải ADMIN/PRINCIPAL) đang hoạt động của 1 trường — phục vụ picker phân công."""
    stmt = (
        select(User.id, User.full_name, User.subject_id)
        .where(User.school_id == school_id, User.is_active.is_(True), User.role.notin_(NO_ASSIGNMENT_ROLES))
        .order_by(User.full_name)
    )
    return list(db.execute(stmt).all())

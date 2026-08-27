from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.crud_router import TenantScope, make_crud_router
from src.api.deps import get_current_user, get_db
from src.models import enums, tables
from src.schemas import school as s
from src.services import rbac

router = APIRouter()

# Lớp user được phép truy cập (theo RBAC) — đăng ký TRƯỚC crud router /classes.
classes_scoped = APIRouter(prefix="/classes", tags=["Classes"])

# Chủ đề/chương lọc ĐÚNG theo môn (+ khối nếu truyền) — đăng ký TRƯỚC crud router
# /curriculum-units để thay GET list mặc định (vốn không lọc gì, lộ chủ đề mọi môn/khối).
curriculum_units_scoped = APIRouter(prefix="/curriculum-units", tags=["Curriculum Units"])

# CurriculumUnit/Semester/Class không có school_id trực tiếp — cô lập tenant qua JOIN 1 cấp.
_VIA_ACADEMIC_YEAR = TenantScope(direct=False, parent_model=tables.AcademicYear, fk_field="academic_year_id")
_VIA_GRADE = TenantScope(direct=False, parent_model=tables.Grade, fk_field="grade_id")
_VIA_SUBJECT = TenantScope(direct=False, parent_model=tables.Subject, fk_field="subject_id")


@classes_scoped.get("/accessible", response_model=list[s.ClassRead])
def list_accessible_classes(
    academic_year_id: UUID | None = None,
    db: Session = Depends(get_db),
    user: tables.User = Depends(get_current_user),
) -> list[tables.Class]:
    """Danh sách lớp user được phép xem/sửa, lọc theo niên khóa nếu truyền."""
    stmt = select(tables.Class).join(tables.Grade).where(tables.Grade.school_id == user.school_id)
    ids = rbac.accessible_class_ids(db, user)
    if ids is not None:
        stmt = stmt.where(tables.Class.id.in_(ids))
    if academic_year_id is not None:
        stmt = stmt.where(tables.Class.academic_year_id == academic_year_id)
    return list(db.execute(stmt).scalars().all())


@curriculum_units_scoped.get("", response_model=list[s.CurriculumUnitRead])
def list_curriculum_units(
    subject_id: UUID,
    db: Session = Depends(get_db),
    user: tables.User = Depends(get_current_user),
    grade_number: int | None = None,
    parent_id: UUID | None = None,
    top_level_only: bool = False,
) -> list[tables.CurriculumUnit]:
    """Chủ đề/chương ĐÚNG môn (lọc subject_id bắt buộc) + ĐÚNG khối (grade_number nếu truyền).

    Trước đây GET /curriculum-units (CRUD generic) không lọc gì -> Trưởng bộ môn Toán
    nhìn thấy lẫn chủ đề của môn khác (vd KHTN) cùng khối. Bắt buộc subject_id để tránh lặp lại.
    Mặc định chỉ trả bản ghi is_active (ẩn chương/chủ đề rác — tàn dư phân mảnh taxonomy cũ,
    còn bị exam_competencies tham chiếu nên không xóa được). `top_level_only=True` chỉ lấy
    CHƯƠNG gốc (parent_id NULL) cho picker phân cấp; `parent_id` lấy đúng BÀI HỌC của 1 chương.
    """
    stmt = (
        select(tables.CurriculumUnit)
        .join(tables.Subject, tables.Subject.id == tables.CurriculumUnit.subject_id)
        .where(
            tables.Subject.school_id == user.school_id,
            tables.CurriculumUnit.subject_id == subject_id,
            tables.CurriculumUnit.is_active.is_(True),
        )
    )
    if grade_number is not None:
        stmt = stmt.where(tables.CurriculumUnit.grade_number == grade_number)
    if top_level_only:
        stmt = stmt.where(tables.CurriculumUnit.parent_id.is_(None))
    elif parent_id is not None:
        stmt = stmt.where(tables.CurriculumUnit.parent_id == parent_id)
    return list(
        db.execute(stmt.order_by(tables.CurriculumUnit.grade_number, tables.CurriculumUnit.code)).scalars().all()
    )


router.include_router(classes_scoped)
router.include_router(curriculum_units_scoped)

router.include_router(
    make_crud_router(
        model=tables.AcademicYear,
        schemas=(s.AcademicYearCreate, s.AcademicYearUpdate, s.AcademicYearRead),
        prefix="/academic-years",
        tag="Academic Years",
    )
)
router.include_router(
    make_crud_router(
        model=tables.Semester,
        schemas=(s.SemesterCreate, s.SemesterUpdate, s.SemesterRead),
        prefix="/semesters",
        tag="Semesters",
        tenant=_VIA_ACADEMIC_YEAR,
    )
)
router.include_router(
    make_crud_router(
        model=tables.Grade,
        schemas=(s.GradeCreate, s.GradeUpdate, s.GradeRead),
        prefix="/grades",
        tag="Grades",
    )
)
router.include_router(
    make_crud_router(
        model=tables.Class,
        schemas=(s.ClassCreate, s.ClassUpdate, s.ClassRead),
        prefix="/classes",
        tag="Classes",
        tenant=_VIA_GRADE,
    )
)
router.include_router(
    make_crud_router(
        model=tables.Subject,
        schemas=(s.SubjectCreate, s.SubjectUpdate, s.SubjectRead),
        prefix="/subjects",
        tag="Subjects",
    )
)
router.include_router(
    make_crud_router(
        model=tables.CurriculumUnit,
        schemas=(s.CurriculumUnitCreate, s.CurriculumUnitUpdate, s.CurriculumUnitRead),
        prefix="/curriculum-units",
        tag="Curriculum Units",
        write_roles=(enums.UserRole.ADMIN, enums.UserRole.PRINCIPAL, enums.UserRole.SUBJECT_HEAD),
        tenant=_VIA_SUBJECT,
    )
)

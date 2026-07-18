from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.crud_router import TenantScope, make_crud_router
from src.api.deps import get_current_user, get_db
from src.models import enums, tables
from src.schemas import student as s

router = APIRouter()

_WRITE = (enums.UserRole.ADMIN, enums.UserRole.PRINCIPAL)
_VIA_STUDENT = TenantScope(direct=False, parent_model=tables.Student, fk_field="student_id")
# Enrollment.class_id không dùng để scope tenant nhưng vẫn phải thuộc trường user khi tạo/sửa.
_CLASS_VIA_GRADE = (tables.Class, TenantScope(direct=False, parent_model=tables.Grade, fk_field="grade_id"))

# Tìm học sinh theo tên gần đúng (index trigram) — đăng ký trước route CRUD động.
search_router = APIRouter(prefix="/students", tags=["Students"])


@search_router.get("/search", response_model=list[s.StudentRead], dependencies=[Depends(get_current_user)])
def search_students(
    q: str, user: tables.User = Depends(get_current_user), limit: int = 20, db: Session = Depends(get_db)
):
    """Tìm học sinh theo họ tên (ILIKE, hỗ trợ bởi index GIN trgm) — chỉ trong trường của mình."""
    stmt = (
        select(tables.Student)
        .where(tables.Student.school_id == user.school_id, tables.Student.full_name.ilike(f"%{q}%"))
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


router.include_router(search_router)
router.include_router(
    make_crud_router(
        model=tables.Student,
        schemas=(s.StudentCreate, s.StudentUpdate, s.StudentRead),
        prefix="/students",
        tag="Students",
        write_roles=_WRITE,
    )
)
router.include_router(
    make_crud_router(
        model=tables.Enrollment,
        schemas=(s.EnrollmentCreate, s.EnrollmentUpdate, s.EnrollmentRead),
        prefix="/enrollments",
        tag="Enrollments",
        write_roles=_WRITE,
        tenant=_VIA_STUDENT,
        cross_school_fields={"class_id": _CLASS_VIA_GRADE},
    )
)

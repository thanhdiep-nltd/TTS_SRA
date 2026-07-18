from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from src.api.deps import get_db, require_roles
from src.core.security import hash_password
from src.models import enums
from src.models.tables import AcademicYear, School, TeacherAssignment, User
from src.schemas.user import (
    AssignmentCreate,
    AssignmentOptions,
    AssignmentRead,
    ClassCoverage,
    CoverageFilter,
    OptionItem,
    PasswordResetPayload,
    TeacherOption,
    UserCreate,
    UserListPage,
    UserListParams,
    UserRead,
    UserUpdate,
    UserUpdateResult,
)
from src.services import assignments as assignment_service

# Đọc: ADMIN + PRINCIPAL (BGH nắm nhân sự, read-only). Ghi: ADMIN only.
read_dep = require_roles(enums.UserRole.ADMIN, enums.UserRole.PRINCIPAL)
admin_dep = require_roles(enums.UserRole.ADMIN)
router = APIRouter(prefix="/users", tags=["Users"])


def _apply_user_filters(stmt: Select, params: UserListParams, current: User) -> Select:
    """Áp bộ lọc danh sách user; PRINCIPAL bị ép về trường mình (MVP: ADMIN thấy mọi trường)."""
    if current.role == enums.UserRole.PRINCIPAL:
        stmt = stmt.where(User.school_id == current.school_id)
    elif params.school_id is not None:
        stmt = stmt.where(User.school_id == params.school_id)
    if params.q:
        like = f"%{params.q.strip()}%"
        stmt = stmt.where(or_(User.full_name.ilike(like), User.email.ilike(like)))
    if params.role is not None:
        stmt = stmt.where(User.role == params.role)
    if params.is_active is not None:
        stmt = stmt.where(User.is_active == params.is_active)
    return stmt


def _get_scoped_user(db: Session, user_id: UUID, current: User) -> User:
    """Lấy user theo id; PRINCIPAL chỉ thấy user trường mình (khác trường -> 404)."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Người dùng không tồn tại")
    if current.role == enums.UserRole.PRINCIPAL and user.school_id != current.school_id:
        raise HTTPException(status_code=404, detail="Người dùng không tồn tại")
    return user


@router.get("", response_model=UserListPage)
def list_users(
    params: UserListParams = Depends(),
    db: Session = Depends(get_db),
    current: User = Depends(read_dep),
):
    base = _apply_user_filters(select(User), params, current)
    total = db.execute(select(func.count()).select_from(base.subquery())).scalar_one()
    stmt = base.order_by(User.full_name).offset((params.page - 1) * params.limit).limit(params.limit)
    items = list(db.execute(stmt).scalars().all())
    return UserListPage(items=items, total=total)


@router.post("", response_model=UserRead, status_code=201, dependencies=[Depends(admin_dep)])
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    if db.get(School, payload.school_id) is None:
        raise HTTPException(status_code=422, detail="Trường không tồn tại")
    data = payload.model_dump()
    password = data.pop("password")
    user = User(**data, hashed_password=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/{user_id}", response_model=UserRead)
def get_user(user_id: UUID, db: Session = Depends(get_db), current: User = Depends(read_dep)):
    return _get_scoped_user(db, user_id, current)


@router.patch("/{user_id}", response_model=UserUpdateResult, dependencies=[Depends(admin_dep)])
def update_user(user_id: UUID, payload: UserUpdate, db: Session = Depends(get_db)):
    """Cập nhật user; nếu đổi vai trò thì tự vô hiệu các phân công không còn hợp lệ."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Người dùng không tồn tại")
    data = payload.model_dump(exclude_unset=True)
    deactivated = 0
    if "role" in data and data["role"] != user.role:
        deactivated = assignment_service.deactivate_mismatched(db, user, data["role"])
    for field, value in data.items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    result = UserUpdateResult.model_validate(user)
    result.deactivated_assignments = deactivated
    return result


@router.post("/{user_id}/reset-password", status_code=204, dependencies=[Depends(admin_dep)])
def reset_password(
    user_id: UUID,
    payload: PasswordResetPayload,
    db: Session = Depends(get_db),
    current: User = Depends(admin_dep),
):
    """ADMIN đặt lại mật khẩu cho user; không reset được tài khoản ADMIN khác."""
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Người dùng không tồn tại")
    if target.role == enums.UserRole.ADMIN and target.id != current.id:
        raise HTTPException(status_code=403, detail="Không thể đặt lại mật khẩu của quản trị viên khác")
    target.hashed_password = hash_password(payload.new_password)
    db.commit()


@router.post("/assignments", response_model=AssignmentRead, status_code=201, dependencies=[Depends(admin_dep)])
def create_assignment(payload: AssignmentCreate, db: Session = Depends(get_db)):
    """Phân công giảng dạy — validate đầy đủ trong service (tổ hợp field, role, trùng, tenant, niên khóa)."""
    return assignment_service.create_assignment(db, payload)


@router.delete("/assignments/{assignment_id}", status_code=204, dependencies=[Depends(admin_dep)])
def delete_assignment(assignment_id: UUID, db: Session = Depends(get_db)):
    """Gỡ một phân công. Phân công GV bộ môn tự sinh (nếu có) phải gỡ riêng."""
    assignment = db.get(TeacherAssignment, assignment_id)
    if assignment is None:
        raise HTTPException(status_code=404, detail="Phân công không tồn tại")
    db.delete(assignment)
    db.commit()


@router.get("/{user_id}/assignments", response_model=list[AssignmentRead])
def list_assignments(user_id: UUID, db: Session = Depends(get_db), current: User = Depends(read_dep)):
    _get_scoped_user(db, user_id, current)
    stmt = select(TeacherAssignment).where(TeacherAssignment.user_id == user_id)
    return list(db.execute(stmt).scalars().all())


@router.get("/assignments/coverage", response_model=list[ClassCoverage])
def assignment_coverage(
    academic_year_id: UUID,
    db: Session = Depends(get_db),
    current: User = Depends(read_dep),
):
    """Độ phủ phân công theo lớp của một niên khóa (tab 'Theo lớp')."""
    year = db.get(AcademicYear, academic_year_id)
    if year is None:
        raise HTTPException(status_code=404, detail="Niên khóa không tồn tại")
    if current.role == enums.UserRole.PRINCIPAL and year.school_id != current.school_id:
        raise HTTPException(status_code=404, detail="Niên khóa không tồn tại")
    return assignment_service.build_coverage(db, year)


@router.put("/assignments/reassign", response_model=AssignmentRead, dependencies=[Depends(admin_dep)])
def reassign_assignment(payload: AssignmentCreate, db: Session = Depends(get_db)):
    """Gán/đổi GV cho 1 vị trí lớp (chủ nhiệm hoặc GV bộ môn) từ tab 'Theo lớp' — atomic."""
    return assignment_service.reassign_class_slot(db, payload)


@router.get("/assignments/teachers", response_model=list[TeacherOption])
def assignment_teachers(school_id: UUID, db: Session = Depends(get_db), current: User = Depends(read_dep)):
    """Danh sách GV của 1 trường cho picker phân công (PRINCIPAL chỉ xem trường mình)."""
    if current.role == enums.UserRole.PRINCIPAL and school_id != current.school_id:
        raise HTTPException(status_code=404, detail="Trường không tồn tại")
    rows = assignment_service.list_school_teachers(db, school_id)
    return [TeacherOption(id=r.id, full_name=r.full_name, subject_id=r.subject_id) for r in rows]


@router.get("/assignments/coverage-filters", response_model=list[CoverageFilter])
def coverage_filters(db: Session = Depends(get_db), current: User = Depends(read_dep)):
    """Danh sách trường + niên khóa cho bộ lọc (ADMIN: mọi trường; PRINCIPAL: trường mình)."""
    stmt = select(School).order_by(School.name)
    if current.role == enums.UserRole.PRINCIPAL:
        stmt = stmt.where(School.id == current.school_id)
    schools = db.execute(stmt).scalars().all()
    years = db.execute(select(AcademicYear).order_by(AcademicYear.start_date.desc())).scalars().all()
    by_school: dict[UUID, list[OptionItem]] = {}
    for y in years:
        by_school.setdefault(y.school_id, []).append(OptionItem(id=y.id, name=y.name, is_current=y.is_current))
    return [CoverageFilter(school_id=s.id, school_name=s.name, years=by_school.get(s.id, [])) for s in schools]


@router.get("/{user_id}/assignment-options", response_model=AssignmentOptions)
def assignment_options(user_id: UUID, db: Session = Depends(get_db), current: User = Depends(read_dep)):
    """Dữ liệu dropdown cho form phân công của 1 GV — theo trường của GV đó."""
    target = _get_scoped_user(db, user_id, current)
    return assignment_service.build_assignment_options(db, target)

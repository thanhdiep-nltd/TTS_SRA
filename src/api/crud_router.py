from dataclasses import dataclass
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from src.api.deps import get_current_user, get_db, require_roles
from src.db.base import Base
from src.models import enums
from src.models.tables import User
from src.repositories.base import CRUDBase


@dataclass(frozen=True)
class TenantScope:
    """Cách xác định trường (tenant) của 1 dòng — dùng để cô lập dữ liệu giữa các trường.

    - direct=True (mặc định): model có cột `school_id` ngay trên bảng -> lọc thẳng.
    - direct=False: phải JOIN sang `parent_model` qua cột FK `fk_field` trên model.
      `parent_model` BẮT BUỘC có `school_id` trực tiếp (chỉ hỗ trợ 1 cấp join).
    """

    direct: bool = True
    parent_model: type[Base] | None = None
    fk_field: str | None = None


def _scope_select(stmt: Select, model: type[Base], tenant: TenantScope, school_id: UUID) -> Select:
    if tenant.direct:
        return stmt.where(model.school_id == school_id)
    fk_col = getattr(model, tenant.fk_field)
    return stmt.join(tenant.parent_model, tenant.parent_model.id == fk_col).where(
        tenant.parent_model.school_id == school_id
    )


def _belongs_to_school(db: Session, model: type[Base], tenant: TenantScope, obj_id, school_id: UUID) -> bool:
    """True nếu obj_id không có (bỏ qua) hoặc tồn tại và thuộc school_id theo tenant scope cho trước."""
    if obj_id is None:
        return True
    stmt = _scope_select(select(model.id), model, tenant, school_id).where(model.id == obj_id)
    return db.execute(stmt).scalar_one_or_none() is not None


def make_crud_router(
    *,
    model: type[Base],
    schemas: tuple[type[BaseModel], type[BaseModel], type[BaseModel]],
    prefix: str,
    tag: str,
    write_roles: tuple[enums.UserRole, ...] = (enums.UserRole.ADMIN, enums.UserRole.PRINCIPAL),
    tenant: TenantScope = TenantScope(),
    cross_school_fields: dict[str, tuple[type[Base], TenantScope]] | None = None,
) -> APIRouter:
    """Sinh router CRUD chuẩn cho một entity, CÔ LẬP THEO TRƯỜNG (tenant).

    - GET: yêu cầu đăng nhập, chỉ trả/thấy dòng thuộc trường của user (theo `tenant`).
    - POST/PATCH/DELETE: yêu cầu vai trò trong `write_roles`; bị động chốt theo trường của
      user (school_id trực tiếp bị ép từ user, hoặc FK tham chiếu phải thuộc trường user).
    - `cross_school_fields`: các field tham chiếu THÊM cần kiểm thuộc trường user khi
      tạo/sửa (vd Enrollment.class_id — không phải field chính dùng để scope tenant).
    """
    create_schema, update_schema, read_schema = schemas
    router = APIRouter(prefix=prefix, tags=[tag])
    crud = CRUDBase(model)
    write_dep = Depends(require_roles(*write_roles))

    def _check_cross_fields(db: Session, data: dict, school_id: UUID) -> None:
        for field_name, (related_model, related_scope) in (cross_school_fields or {}).items():
            if field_name in data and not _belongs_to_school(
                db, related_model, related_scope, data[field_name], school_id
            ):
                raise HTTPException(status_code=403, detail=f"{field_name} không thuộc trường của bạn")

    @router.get("", response_model=list[read_schema])
    def list_items(
        skip: int = 0, limit: int = 100, db: Session = Depends(get_db), user: User = Depends(get_current_user)
    ):
        stmt = _scope_select(select(model), model, tenant, user.school_id).offset(skip).limit(limit)
        return list(db.execute(stmt).scalars().all())

    @router.get("/{item_id}", response_model=read_schema)
    def get_item(item_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
        stmt = _scope_select(select(model), model, tenant, user.school_id).where(model.id == item_id)
        obj = db.execute(stmt).scalar_one_or_none()
        if obj is None:
            raise HTTPException(status_code=404, detail=f"{tag} không tồn tại")
        return obj

    @router.post("", response_model=read_schema, status_code=201, dependencies=[write_dep])
    def create_item(payload: create_schema, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
        data = payload.model_dump()
        if tenant.direct:
            data["school_id"] = user.school_id  # không tin school_id từ client
        elif not _belongs_to_school(db, tenant.parent_model, TenantScope(), data.get(tenant.fk_field), user.school_id):
            raise HTTPException(status_code=403, detail=f"{tenant.fk_field} không thuộc trường của bạn")
        _check_cross_fields(db, data, user.school_id)
        return crud.create(db, data)

    @router.patch("/{item_id}", response_model=read_schema, dependencies=[write_dep])
    def update_item(
        item_id: UUID, payload: update_schema, db: Session = Depends(get_db), user: User = Depends(get_current_user)
    ):
        stmt = _scope_select(select(model), model, tenant, user.school_id).where(model.id == item_id)
        obj = db.execute(stmt).scalar_one_or_none()
        if obj is None:
            raise HTTPException(status_code=404, detail=f"{tag} không tồn tại")
        data = payload.model_dump(exclude_unset=True)
        _check_cross_fields(db, data, user.school_id)
        return crud.update(db, obj, data)

    @router.delete("/{item_id}", status_code=204, dependencies=[write_dep])
    def delete_item(item_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
        stmt = _scope_select(select(model), model, tenant, user.school_id).where(model.id == item_id)
        obj = db.execute(stmt).scalar_one_or_none()
        if obj is None:
            raise HTTPException(status_code=404, detail=f"{tag} không tồn tại")
        crud.delete(db, obj)

    return router

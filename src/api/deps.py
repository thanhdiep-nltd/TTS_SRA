from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer
from jwt import InvalidTokenError
from sqlalchemy.orm import Session

from src.core.security import ACCESS, decode_token
from src.db.session import get_db
from src.models import enums
from src.models.tables import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

_CRED_EXC = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Thông tin xác thực không hợp lệ",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    db: Annotated[Session, Depends(get_db)],
    token: Annotated[str | None, Depends(oauth2_scheme)] = None,
    token_param: str | None = Query(default=None, alias="token"),
) -> User:
    """Giải mã access token và trả về user đang đăng nhập."""
    actual_token = token or token_param
    if not actual_token:
        raise _CRED_EXC
    try:
        payload = decode_token(actual_token)
        if payload.get("type") != ACCESS:
            raise _CRED_EXC
        user_id = payload.get("sub")
    except InvalidTokenError as exc:
        raise _CRED_EXC from exc

    user = db.get(User, int(user_id)) if user_id else None
    if user is None or not user.is_active:
        raise _CRED_EXC
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: enums.UserRole):
    """Tạo dependency yêu cầu user có một trong các vai trò cho trước."""

    def dependency(user: CurrentUser) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền thực hiện thao tác này",
            )
        return user

    return dependency


__all__ = ["get_db", "get_current_user", "require_roles", "oauth2_scheme", "CurrentUser"]

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from src.api.deps import CurrentUser, get_db
from src.config import get_settings
from src.core import security
from src.models.tables import RefreshToken, User
from src.schemas.auth import LoginRequest, RefreshRequest, TokenResponse
from src.schemas.user import UserRead
from src.services import login_rate_limit

router = APIRouter(prefix="/auth", tags=["Auth"])


def _issue_tokens(db: Session, user: User) -> TokenResponse:
    access = security.create_access_token(str(user.id))
    refresh = security.create_refresh_token(str(user.id))
    expires_at = datetime.now(UTC) + timedelta(days=get_settings().refresh_token_expire_days)
    db.add(RefreshToken(user_id=user.id, token_hash=security.hash_token(refresh), expires_at=expires_at))
    return TokenResponse(access_token=access, refresh_token=refresh)


def _cleanup_expired_tokens(db: Session, user_id) -> None:
    """Dọn refresh token đã hết hạn/thu hồi của user này — chạy mỗi lần login thay vì cron
    riêng (bảng này không có job dọn định kỳ, sẽ phình vô hạn theo số lần login/refresh)."""
    now = datetime.now(UTC)
    db.execute(
        delete(RefreshToken).where(
            RefreshToken.user_id == user_id,
            or_(RefreshToken.expires_at < now, RefreshToken.revoked_at.is_not(None)),
        )
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    email_key = payload.email.strip().lower()
    if login_rate_limit.is_locked(email_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Đăng nhập sai quá nhiều lần. Vui lòng thử lại sau ít phút.",
        )

    user = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if user is None or not security.verify_password(payload.password, user.hashed_password):
        login_rate_limit.register_failure(email_key)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sai email hoặc mật khẩu")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tài khoản đã bị vô hiệu hóa")

    login_rate_limit.reset(email_key)
    _cleanup_expired_tokens(db, user.id)
    tokens = _issue_tokens(db, user)
    user.last_login_at = datetime.now(UTC)
    db.commit()
    return tokens


def _validate_refresh(db: Session, raw_token: str) -> tuple[str, RefreshToken]:
    try:
        payload = security.decode_token(raw_token)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Refresh token không hợp lệ") from exc
    if payload.get("type") != security.REFRESH:
        raise HTTPException(status_code=401, detail="Refresh token không hợp lệ")
    row = db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == security.hash_token(raw_token))
    ).scalar_one_or_none()
    if row is None or row.revoked_at is not None or row.expires_at < datetime.now(UTC):
        raise HTTPException(status_code=401, detail="Refresh token đã hết hạn hoặc bị thu hồi")
    return payload["sub"], row


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    user_id, row = _validate_refresh(db, payload.refresh_token)
    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Tài khoản không khả dụng")
    row.revoked_at = datetime.now(UTC)  # rotate: thu hồi token cũ
    tokens = _issue_tokens(db, user)
    db.commit()
    return tokens


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(payload: RefreshRequest, db: Session = Depends(get_db)):
    row = db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == security.hash_token(payload.refresh_token))
    ).scalar_one_or_none()
    if row is not None and row.revoked_at is None:
        row.revoked_at = datetime.now(UTC)
        db.commit()


@router.get("/me", response_model=UserRead)
def me(user: CurrentUser, db: Session = Depends(get_db)):
    from src.models.tables import School

    school = db.get(School, user.school_id)

    from src.models.tables import User as DBUser

    principal = (
        db.execute(select(DBUser).where(DBUser.school_id == user.school_id, DBUser.role == "PRINCIPAL"))
        .scalars()
        .first()
    )

    from src.models import enums as db_enums
    from src.models.tables import TeacherAssignment

    homeroom_assignment = (
        db.execute(
            select(TeacherAssignment).where(
                TeacherAssignment.user_id == user.id,
                TeacherAssignment.role_context.in_(
                    [db_enums.RoleContext.HOMEROOM_PRIMARY, db_enums.RoleContext.HOMEROOM_SECONDARY]
                ),
                TeacherAssignment.is_active.is_(True),
            )
        )
        .scalars()
        .first()
    )

    user_read = UserRead.model_validate(user)
    user_read.school_name = school.name if school else None
    user_read.principal_name = principal.full_name if principal else "Nguyễn Minh Triết"
    user_read.homeroom_class_id = homeroom_assignment.class_id if homeroom_assignment else None
    return user_read

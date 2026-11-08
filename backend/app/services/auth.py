import hmac
from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import Settings
from app.core.errors import AppError
from app.models.users import User


def login(session: Session, email: str, password: str) -> tuple[User, int]:
    user = session.scalar(select(User).where(User.email == email).with_for_update())
    now = security.utcnow()
    correct = security.verify_password(password, user.password_hash if user else None)
    if user is None or not user.is_active:
        raise AppError("INVALID_CREDENTIALS", "Email hoặc mật khẩu không đúng.", 401)
    if user.locked_until and user.locked_until > now:
        raise AppError("ACCOUNT_LOCKED", "Tài khoản tạm khoá. Vui lòng thử lại sau 15 phút.", 423)
    if user.locked_until:
        user.failed_login_attempts = 0
        user.locked_until = None
    if not correct:
        user.failed_login_attempts += 1
        locked = user.failed_login_attempts >= 5
        if locked:
            user.locked_until = now + timedelta(minutes=15)
            user.auth_version += 1
        session.commit()  # Failed attempts must survive the error response.
        if locked:
            raise AppError(
                "ACCOUNT_LOCKED", "Tài khoản tạm khoá. Vui lòng thử lại sau 15 phút.", 423
            )
        raise AppError("INVALID_CREDENTIALS", "Email hoặc mật khẩu không đúng.", 401)
    if security.password_hasher.check_needs_rehash(user.password_hash):
        user.password_hash = security.hash_password(password)
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = now
    user.auth_version += 1
    version = user.auth_version
    session.commit()
    return user, version


def authenticate(
    session: Session,
    token: str | None,
    kind: str,
    settings: Settings,
    *,
    csrf: str | None = None,
    lock: bool = False,
) -> tuple[User, dict[str, Any]]:
    claims = security.decode_token(token, kind, settings)
    query = select(User).where(User.id == UUID(claims["sub"]))
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    user = session.scalar(query)
    if (
        user is None
        or not user.is_active
        or user.auth_version != claims["ver"]
        or (user.locked_until is not None and user.locked_until > security.utcnow())
    ):
        raise security.unauthorized()
    if csrf is not None and not hmac.compare_digest(claims["csrf"], security.csrf_digest(csrf)):
        raise AppError("CSRF_INVALID", "Vui lòng tải lại trang rồi thử lại.", 403)
    return user, claims


def revoke(session: Session, user: User) -> int:
    user.auth_version += 1
    version = user.auth_version
    session.commit()
    return version


def change_password(session: Session, user: User, current_password: str, new_password: str) -> None:
    if not security.verify_password(current_password, user.password_hash):
        raise AppError("INVALID_CREDENTIALS", "Mật khẩu hiện tại không đúng.", 400)
    user.password_hash = security.hash_password(new_password)
    revoke(session, user)

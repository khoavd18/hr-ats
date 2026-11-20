from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.core.errors import AppError
from app.core.security import validate_csrf
from app.models.users import User
from app.services.auth import authenticate

DB = Annotated[Session, Depends(get_session)]
Config = Annotated[Settings, Depends(get_settings)]


def require_csrf(request: Request, settings: Config) -> str:
    origin = request.headers.get("origin")
    if origin is not None and origin != settings.frontend_origin:
        raise AppError("CSRF_INVALID", "Yêu cầu không được phép.", 403)
    cookie = request.cookies.get("csrf_token")
    validate_csrf(cookie, request.headers.get("x-csrf-token"), settings)
    assert cookie is not None
    return cookie


CSRF = Annotated[str, Depends(require_csrf)]


def current_user(request: Request, session: DB, settings: Config) -> User:
    unsafe = request.method not in {"GET", "HEAD", "OPTIONS"}
    csrf = require_csrf(request, settings) if unsafe else None
    if unsafe and request.url.path.startswith("/api/v1/users"):
        # Acquire before locking the actor: two admins editing each other cannot deadlock.
        session.execute(select(func.pg_advisory_xact_lock(70404)))
    user, _ = authenticate(
        session, request.cookies.get("access_token"), "access", settings, csrf=csrf, lock=unsafe
    )
    return user


CurrentUser = Annotated[User, Depends(current_user)]

from fastapi import APIRouter, Depends, Request, Response

from app.api.dependencies import CSRF, DB, Config, CurrentUser
from app.api.rate_limits import limit_login
from app.core import security
from app.core.errors import AppError
from app.models.users import User
from app.schemas.users import ChangePasswordInput, LoginInput, UserResponse
from app.services import auth

router = APIRouter(prefix="/auth", tags=["auth"])


def set_csrf(response: Response, csrf: str, settings: Config) -> None:
    response.set_cookie(
        "csrf_token",
        csrf,
        max_age=security.REFRESH_SECONDS,
        httponly=False,
        secure=settings.app_env == "prod",
        samesite="lax",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"


def set_session(
    response: Response, user: User, settings: Config, *, auth_version: int | None = None
) -> None:
    csrf = security.new_csrf(settings)
    for name, kind, seconds in (
        ("access_token", "access", security.ACCESS_SECONDS),
        ("refresh_token", "refresh", security.REFRESH_SECONDS),
    ):
        response.set_cookie(
            name,
            security.encode_token(user, kind, csrf, settings, auth_version=auth_version),
            max_age=seconds,
            httponly=True,
            secure=settings.app_env == "prod",
            samesite="lax",
            path="/",
        )
    set_csrf(response, csrf, settings)


def clear_session(response: Response, settings: Config) -> None:
    for name in ("access_token", "refresh_token", "csrf_token"):
        response.delete_cookie(
            name,
            path="/",
            secure=settings.app_env == "prod",
            samesite="lax",
            httponly=name != "csrf_token",
        )
    response.headers["Cache-Control"] = "no-store"


@router.get("/csrf", status_code=204)
def csrf_token(request: Request, response: Response, settings: Config) -> None:
    # Preserve a current session's token; bootstrapping another tab must not invalidate it.
    token = request.cookies.get("csrf_token")
    try:
        security.validate_csrf(token, token, settings)
    except AppError:
        token = security.new_csrf(settings)
    assert token is not None
    set_csrf(response, token, settings)


@router.post("/login", response_model=UserResponse, dependencies=[Depends(limit_login)])
def login(data: LoginInput, response: Response, session: DB, settings: Config, csrf: CSRF) -> User:
    user, version = auth.login(session, data.email, data.password.get_secret_value())
    set_session(response, user, settings, auth_version=version)
    return user


@router.post("/refresh", response_model=UserResponse)
def refresh(
    request: Request, response: Response, session: DB, settings: Config, csrf: CSRF
) -> User:
    user, _ = auth.authenticate(
        session, request.cookies.get("refresh_token"), "refresh", settings, csrf=csrf, lock=True
    )
    version = auth.revoke(session, user)
    set_session(response, user, settings, auth_version=version)
    return user


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, session: DB, settings: Config, csrf: CSRF) -> None:
    # Logout also works when the short-lived access token has expired.
    user, _ = auth.authenticate(
        session, request.cookies.get("refresh_token"), "refresh", settings, csrf=csrf, lock=True
    )
    auth.revoke(session, user)
    clear_session(response, settings)


@router.get("/me", response_model=UserResponse)
def me(response: Response, user: CurrentUser) -> User:
    response.headers["Cache-Control"] = "no-store"
    return user


@router.post("/change-password", status_code=204)
def change_password(
    data: ChangePasswordInput, response: Response, session: DB, settings: Config, user: CurrentUser
) -> None:
    auth.change_password(
        session,
        user,
        data.current_password.get_secret_value(),
        data.new_password.get_secret_value(),
    )
    clear_session(response, settings)

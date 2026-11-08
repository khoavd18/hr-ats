import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import Settings
from app.core.errors import AppError
from app.models.users import User

ACCESS_SECONDS = 30 * 60
REFRESH_SECONDS = 7 * 24 * 60 * 60
password_hasher = PasswordHasher()
# Equal-cost verification for missing accounts; the value is random and never usable for login.
_dummy_hash = password_hasher.hash(secrets.token_urlsafe(32))


def utcnow() -> datetime:
    return datetime.now(UTC)


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        valid = password_hasher.verify(password_hash or _dummy_hash, password)
        return valid and password_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def unauthorized() -> AppError:
    return AppError("UNAUTHORIZED", "Vui lòng đăng nhập lại.", 401)


def csrf_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_csrf(settings: Settings) -> str:
    nonce = secrets.token_urlsafe(32)
    signature = hmac.new(
        settings.secret_key.get_secret_value().encode(),
        ("csrf:" + nonce).encode(),
        hashlib.sha256,
    ).hexdigest()
    return nonce + "." + signature


def validate_csrf(cookie: str | None, header: str | None, settings: Settings) -> None:
    valid = False
    if (
        cookie
        and header
        and len(cookie) <= 256
        and cookie.isascii()
        and header.isascii()
        and hmac.compare_digest(cookie, header)
    ):
        nonce, _, signature = cookie.partition(".")
        expected = hmac.new(
            settings.secret_key.get_secret_value().encode(),
            ("csrf:" + nonce).encode(),
            hashlib.sha256,
        ).hexdigest()
        valid = bool(nonce) and hmac.compare_digest(signature, expected)
    if not valid:
        raise AppError("CSRF_INVALID", "Vui lòng tải lại trang rồi thử lại.", 403)


def encode_token(
    user: User, kind: str, csrf: str, settings: Settings, *, auth_version: int | None = None
) -> str:
    now = utcnow()
    lifetime = ACCESS_SECONDS if kind == "access" else REFRESH_SECONDS
    return jwt.encode(
        {
            "sub": str(user.id),
            "type": kind,
            "ver": user.auth_version if auth_version is None else auth_version,
            "csrf": csrf_digest(csrf),
            "iat": now,
            "exp": now + timedelta(seconds=lifetime),
            "iss": "hr-ats",
            "aud": "hr-ats-web",
            "jti": secrets.token_urlsafe(24),
        },
        settings.secret_key.get_secret_value(),
        algorithm="HS256",
    )


def decode_token(token: str | None, kind: str, settings: Settings) -> dict[str, Any]:
    if not token:
        raise unauthorized()
    try:
        payload = jwt.decode(
            token,
            settings.secret_key.get_secret_value(),
            algorithms=["HS256"],
            issuer="hr-ats",
            audience="hr-ats-web",
            options={"require": ["sub", "type", "ver", "csrf", "iat", "exp", "jti"]},
        )
        UUID(payload["sub"])
        if (
            payload["type"] != kind
            or type(payload["ver"]) is not int
            or not isinstance(payload["csrf"], str)
        ):
            raise ValueError
        return payload
    except (jwt.PyJWTError, ValueError, TypeError, AttributeError):
        raise unauthorized() from None

import hashlib
import hmac
import re
import secrets
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import IntegrationToken, User
from app.services.audit import record_audit

ServiceScope = Literal["tasks:create", "reports:summary", "cv:upload"]
SERVICE_SCOPES = ("tasks:create", "reports:summary", "cv:upload")
TOKEN_FORMAT = re.compile(r"atsint_([a-f0-9]{32})\.[a-zA-Z0-9_-]{43}", re.ASCII)


def issue_token(
    session: Session, sponsor_id: UUID, scopes: list[str], expires_at: datetime
) -> tuple[UUID, str]:
    sponsor = session.get(User, sponsor_id)
    if sponsor is None or not sponsor.is_active:
        raise ValueError("Integration sponsor must be an active ATS user")
    if not scopes or any(scope not in SERVICE_SCOPES for scope in scopes):
        raise ValueError("Invalid integration scopes")
    if expires_at <= datetime.now(UTC):
        raise ValueError("Integration token expiration must be in the future")
    token_id = uuid4()
    raw = f"atsint_{token_id.hex}.{secrets.token_urlsafe(32)}"
    session.add(
        IntegrationToken(
            id=token_id,
            sponsor_id=sponsor_id,
            token_hash=hashlib.sha256(raw.encode("ascii")).hexdigest(),
            scopes=sorted(set(scopes)),
            expires_at=expires_at,
        )
    )
    record_audit(
        session,
        actor_id=None,
        action="integration.token_issued",
        entity="integration_token",
        entity_id=token_id,
    )
    return token_id, raw


def revoke_token(session: Session, token_id: UUID) -> bool:
    token = session.get(IntegrationToken, token_id, with_for_update=True)
    if token is None:
        return False
    if token.revoked_at is None:
        token.revoked_at = datetime.now(UTC)
        record_audit(
            session,
            actor_id=None,
            action="integration.token_revoked",
            entity="integration_token",
            entity_id=token.id,
        )
    return True


def authenticate_token(session: Session, raw: str) -> tuple[IntegrationToken, User]:
    match = TOKEN_FORMAT.fullmatch(raw)
    token = session.get(IntegrationToken, UUID(hex=match[1])) if match else None
    if (
        token is None
        or not hmac.compare_digest(
            token.token_hash, hashlib.sha256(raw.encode("ascii")).hexdigest()
        )
        or token.revoked_at is not None
        or token.expires_at <= datetime.now(UTC)
    ):
        raise AppError("INVALID_SERVICE_TOKEN", "Token dịch vụ không hợp lệ.", 401)
    sponsor = session.get(User, token.sponsor_id)
    if sponsor is None or not sponsor.is_active:
        raise AppError("INVALID_SERVICE_TOKEN", "Token dịch vụ không hợp lệ.", 401)
    return token, sponsor

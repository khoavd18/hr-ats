"""Shared audit metadata writer. Callers commit with their business transaction."""

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.activity import AuditLog


def record_audit(
    session: Session,
    *,
    actor_id: UUID | None,
    action: str,
    entity: str,
    entity_id: UUID,
    ip: str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_id=actor_id,
        action=action,
        entity=entity,
        entity_id=entity_id,
        ip=ip,
        details=details or {},
    )
    session.add(entry)
    return entry

from dataclasses import dataclass
from uuid import UUID

from app.core.errors import AppError
from app.models.users import User, UserRole


@dataclass(frozen=True)
class ResourceScope:
    """T05 services resolve membership from the DB, never from a request body."""

    owner_id: UUID | None = None
    member_ids: frozenset[UUID] = frozenset()


def authorize(user: User, action: str, resource: ResourceScope | None = None) -> None:
    allowed = False
    if user.is_active:
        if action in {"users.manage", "data_requests.manage", "audit_log.view"}:
            allowed = user.role == UserRole.admin
        elif action in {"email_templates.manage", "hiring_units.manage"}:
            allowed = user.role in {UserRole.admin, UserRole.lead}
        elif action in {"jobs.view", "job_candidates.view", "applications.move", "emails.send"}:
            allowed = user.role in {UserRole.admin, UserRole.lead} or (
                user.role == UserRole.recruiter
                and resource is not None
                and (user.id == resource.owner_id or user.id in resource.member_ids)
            )
        elif action == "cv_bank.search":
            allowed = user.role in set(UserRole)
        elif action == "reports.view":
            allowed = user.role in {UserRole.admin, UserRole.lead} or (
                user.role == UserRole.recruiter
                and resource is not None
                and resource.owner_id == user.id
            )
    if not allowed:
        raise AppError("FORBIDDEN", "Bạn không có quyền thực hiện thao tác này.", 403)

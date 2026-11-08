from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.applications import Application
from app.models.candidates import Candidate
from app.models.jobs import Job, JobMember
from app.models.users import User, UserRole


@dataclass(frozen=True)
class ResourceScope:
    """T05 services resolve membership from the DB, never from a request body."""

    owner_id: UUID | None = None
    member_ids: frozenset[UUID] = frozenset()


def _has_job_access(
    session: Session, user: User, resource: Job | Candidate | Application, action: str
) -> bool:
    membership = exists().where(JobMember.job_id == Job.id, JobMember.user_id == user.id)
    query = select(Job.id).where(or_(Job.owner_id == user.id, membership))
    if isinstance(resource, Job):
        query = query.where(Job.id == resource.id)
    elif isinstance(resource, Candidate) and action == "job_candidates.view":
        query = (
            query.join(Application, Application.job_id == Job.id)
            .join(Candidate, Candidate.id == Application.candidate_id)
            .where(
                Candidate.id == resource.id,
                Candidate.deleted_at.is_(None),
                Application.deleted_at.is_(None),
            )
        )
    elif isinstance(resource, Application) and action != "jobs.view":
        query = (
            query.join(Application, Application.job_id == Job.id)
            .join(Candidate, Candidate.id == Application.candidate_id)
            .where(
                Application.id == resource.id,
                Application.deleted_at.is_(None),
                Candidate.deleted_at.is_(None),
            )
        )
    else:
        return False
    # Resolve IDs against persisted ownership/membership; do not flush untrusted pending edits.
    with session.no_autoflush:
        return session.scalar(select(query.exists())) is True


def authorize(
    user: User,
    action: str,
    resource: ResourceScope | Job | Candidate | Application | None = None,
    *,
    session: Session | None = None,
) -> None:
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
                and (
                    (
                        isinstance(resource, ResourceScope)
                        and (user.id == resource.owner_id or user.id in resource.member_ids)
                    )
                    or (
                        isinstance(resource, (Job, Candidate, Application))
                        and session is not None
                        and _has_job_access(session, user, resource, action)
                    )
                )
            )
        elif action == "cv_bank.search":
            allowed = user.role in set(UserRole)
        elif action == "reports.view":
            allowed = user.role in {UserRole.admin, UserRole.lead} or (
                user.role == UserRole.recruiter
                and isinstance(resource, ResourceScope)
                and resource.owner_id == user.id
            )
    if not allowed:
        raise AppError("FORBIDDEN", "Bạn không có quyền thực hiện thao tác này.", 403)

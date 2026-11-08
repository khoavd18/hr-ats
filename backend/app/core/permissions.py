from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.applications import Application
from app.models.candidates import Candidate, CvFile
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


def _has_cv_access(session: Session, user: User, resource: CvFile) -> bool:
    # Read persisted scope so unflushed changes cannot grant access.
    with session.no_autoflush:
        scope = session.execute(
            select(CvFile.job_id, CvFile.candidate_id, CvFile.uploaded_by).where(
                CvFile.id == resource.id, CvFile.deleted_at.is_(None)
            )
        ).one_or_none()
        if scope is None:
            return False
        job_id, candidate_id, uploaded_by = scope
        if job_id is not None and _has_job_access(session, user, Job(id=job_id), "jobs.view"):
            return True
        if candidate_id is not None and _has_job_access(
            session, user, Candidate(id=candidate_id), "job_candidates.view"
        ):
            return True
        # Parsing attaches a candidate even for a private, unassigned upload.
        # Preserve the uploader's access to that file, without granting access
        # to other files of the candidate or overriding an assigned Job's scope.
        return job_id is None and uploaded_by == user.id


def authorize(
    user: User,
    action: str,
    resource: ResourceScope | Job | Candidate | Application | CvFile | None = None,
    *,
    session: Session | None = None,
) -> None:
    allowed = False
    if user.is_active:
        if action in {"users.manage", "data_requests.manage", "audit_log.view"}:
            allowed = user.role == UserRole.admin
        elif action in {"email_templates.manage", "hiring_units.manage"}:
            allowed = user.role in {UserRole.admin, UserRole.lead}
        elif action in {
            "jobs.view",
            "jobs.manage",
            "job_candidates.view",
            "applications.move",
            "emails.send",
        }:
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
        elif action == "cv_files.view":
            allowed = (
                isinstance(resource, CvFile)
                and session is not None
                and (
                    user.role in {UserRole.admin, UserRole.lead}
                    or (user.role == UserRole.recruiter and _has_cv_access(session, user, resource))
                )
            )
        elif action in {"cv_bank.search", "cv_files.upload", "jobs.create"}:
            allowed = user.role in set(UserRole)
        elif action == "reports.view":
            allowed = user.role in {UserRole.admin, UserRole.lead} or (
                user.role == UserRole.recruiter
                and isinstance(resource, ResourceScope)
                and resource.owner_id == user.id
            )
    if not allowed:
        raise AppError("FORBIDDEN", "Bạn không có quyền thực hiện thao tác này.", 403)

"""Job writes validate the effective record and commit members/vector atomically."""

from datetime import UTC, datetime
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import delete, exists, func, or_, select
from sqlalchemy.orm import Session

from app.ai.embed import EmbeddingError
from app.core.config import Settings
from app.core.errors import AppError
from app.core.permissions import authorize
from app.models.applications import Application
from app.models.enums import JobStatus
from app.models.jobs import HiringUnit, Job, JobMember
from app.models.users import User, UserRole
from app.schemas.core import HiringUnitRead, JobRead
from app.schemas.jobs import (
    Choice,
    HiringUnitCreate,
    HiringUnitList,
    HiringUnitPatch,
    JobCreate,
    JobList,
    JobOptions,
    JobPatch,
    JobResponse,
)
from app.services.embeddings import embed_job
from app.services.ranking import counts_for_jobs


def list_units(session: Session, actor: User, page: int, page_size: int) -> HiringUnitList:
    authorize(actor, "hiring_units.manage")
    rows = session.scalars(
        select(HiringUnit)
        .order_by(HiringUnit.created_at, HiringUnit.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return HiringUnitList(
        items=[HiringUnitRead.model_validate(row) for row in rows],
        total=session.scalar(select(func.count()).select_from(HiringUnit)) or 0,
    )


def save_unit(
    session: Session,
    actor: User,
    data: HiringUnitCreate | HiringUnitPatch,
    unit_id: UUID | None = None,
) -> HiringUnit:
    authorize(actor, "hiring_units.manage")
    unit = session.get(HiringUnit, unit_id) if unit_id is not None else HiringUnit()
    if unit is None:
        raise AppError("NOT_FOUND", "Không tìm thấy đơn vị tuyển.", 404)
    for key, value in data.model_dump(exclude_unset=unit_id is not None).items():
        setattr(unit, key, value)
    session.add(unit)
    session.commit()
    return unit


def options(session: Session, actor: User) -> JobOptions:
    authorize(actor, "jobs.create")
    return JobOptions(
        hiring_units=[
            Choice(id=row.id, name=row.name)
            for row in session.scalars(
                select(HiringUnit)
                .where(HiringUnit.is_active.is_(True))
                .order_by(HiringUnit.name, HiringUnit.id)
            )
        ],
        users=[
            Choice(id=row.id, name=row.full_name)
            for row in session.scalars(
                select(User).where(User.is_active.is_(True)).order_by(User.full_name, User.id)
            )
        ],
    )


def get_job(session: Session, actor: User, job_id: UUID, *, lock: bool = False) -> Job:
    query = select(Job).where(Job.id == job_id)
    if lock:
        query = query.with_for_update()
    job = session.scalar(query)
    if job is None:
        raise AppError("NOT_FOUND", "Không tìm thấy việc tuyển dụng.", 404)
    authorize(actor, "jobs.manage" if lock else "jobs.view", job, session=session)
    return job


def response(session: Session, job: Job, *, needs_rescore: bool = False) -> JobResponse:
    return JobResponse(
        **JobRead.model_validate(job).model_dump(),
        hiring_unit_name=session.get(HiringUnit, job.hiring_unit_id).name,  # type: ignore[union-attr]
        owner_name=session.get(User, job.owner_id).full_name,  # type: ignore[union-attr]
        member_ids=list(
            session.scalars(
                select(JobMember.user_id)
                .where(JobMember.job_id == job.id)
                .order_by(JobMember.user_id)
            )
        ),
        needs_rescore=needs_rescore,
        ai_counts=counts_for_jobs(session, [job.id])[job.id],
    )


def list_jobs(
    session: Session,
    actor: User,
    page: int,
    page_size: int,
    status: JobStatus | None,
    owner_id: UUID | None,
    q: str,
) -> JobList:
    authorize(actor, "jobs.create")
    query = select(Job)
    if actor.role == UserRole.recruiter:
        query = query.where(
            or_(
                Job.owner_id == actor.id,
                exists().where(JobMember.job_id == Job.id, JobMember.user_id == actor.id),
            )
        )
    if status is not None:
        query = query.where(Job.status == status)
    if owner_id is not None:
        query = query.where(Job.owner_id == owner_id)
    if q.strip():
        # autoescape treats %, _ and / as text, not caller-supplied SQL wildcards.
        query = query.where(Job.title.icontains(q.strip(), autoescape=True))
    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = session.scalars(
        query.order_by(Job.created_at.desc(), Job.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    # Batch names/members for the page instead of one query per cell.
    units = {
        row.id: row.name
        for row in session.scalars(
            select(HiringUnit).where(HiringUnit.id.in_({job.hiring_unit_id for job in rows}))
        )
    }
    owners = {
        row.id: row.full_name
        for row in session.scalars(select(User).where(User.id.in_({job.owner_id for job in rows})))
    }
    members: dict[UUID, list[UUID]] = {job.id: [] for job in rows}
    counts = counts_for_jobs(session, [job.id for job in rows])
    for member in session.scalars(
        select(JobMember).where(JobMember.job_id.in_(members)).order_by(JobMember.user_id)
    ):
        members[member.job_id].append(member.user_id)
    return JobList(
        items=[
            JobResponse(
                **JobRead.model_validate(job).model_dump(),
                hiring_unit_name=units[job.hiring_unit_id],
                owner_name=owners[job.owner_id],
                member_ids=members[job.id],
                ai_counts=counts[job.id],
            )
            for job in rows
        ],
        total=total,
    )


def _validate_references(session: Session, data: JobCreate, previous: Job | None) -> None:
    unit = session.get(HiringUnit, data.hiring_unit_id)
    if unit is None or (
        not unit.is_active and (previous is None or previous.hiring_unit_id != unit.id)
    ):
        raise AppError("INVALID_HIRING_UNIT", "Hãy chọn đơn vị tuyển đang hoạt động.", 422)
    owner = session.get(User, data.owner_id)
    if owner is None or (
        not owner.is_active and (previous is None or previous.owner_id != owner.id)
    ):
        raise AppError("INVALID_JOB_USER", "Hãy chọn người dùng đang hoạt động.", 422)


def _replace_members(session: Session, job: Job, user_ids: list[UUID]) -> None:
    requested = set(user_ids)
    current = set(session.scalars(select(JobMember.user_id).where(JobMember.job_id == job.id)))
    active = set(
        session.scalars(
            select(User.id).where(User.id.in_(requested - current), User.is_active.is_(True))
        )
    )
    if active != requested - current:
        raise AppError("INVALID_JOB_USER", "Hãy chọn người dùng đang hoạt động.", 422)
    session.execute(
        delete(JobMember).where(JobMember.job_id == job.id, JobMember.user_id.not_in(requested))
    )
    session.add_all(JobMember(job_id=job.id, user_id=user_id) for user_id in requested - current)


def save_job(
    session: Session,
    actor: User,
    data: JobCreate | JobPatch,
    settings: Settings,
    job_id: UUID | None = None,
) -> JobResponse:
    authorize(actor, "jobs.create")
    job = get_job(session, actor, job_id, lock=True) if job_id is not None else None
    changes = data.model_dump(exclude_unset=job is not None)
    # Validate merged fields, including one-sided salary updates and removing the last requirement.
    merged = JobRead.model_validate(job).model_dump() if job is not None else {}
    effective = {key: value for key, value in merged.items() if key in JobCreate.model_fields}
    effective.update(changes)
    try:
        validated = JobCreate.model_validate(effective)
    except ValidationError:
        raise AppError(
            "VALIDATION_ERROR",
            "Kiểm tra tiêu đề, khoảng lương và yêu cầu bắt buộc khi mở tuyển.",
            422,
        ) from None
    if actor.role == UserRole.recruiter and (
        (job is None and validated.owner_id != actor.id)
        or (job is not None and validated.owner_id != job.owner_id)
    ):
        raise AppError("FORBIDDEN", "Chỉ quản trị hoặc trưởng nhóm được đổi người phụ trách.", 403)
    _validate_references(session, validated, job)
    requirements_changed = job is not None and (
        job.must_have != validated.must_have or job.nice_to_have != validated.nice_to_have
    )
    needs_rescore = bool(
        requirements_changed
        and session.scalar(
            select(exists().where(Application.job_id == job_id, Application.deleted_at.is_(None)))
        )
    )
    old_status = job.status if job is not None else JobStatus.draft
    job = job or Job()
    for key, value in changes.items():
        if key != "member_ids":
            setattr(job, key, value)
    now = datetime.now(UTC)
    if old_status != validated.status:
        if validated.status == JobStatus.open:
            job.opened_at = now
            job.closed_at = None
        elif validated.status == JobStatus.closed:
            job.closed_at = now
    session.add(job)
    try:
        embed_job(job, settings=settings)
        session.flush()
        if "member_ids" in changes:
            _replace_members(session, job, validated.member_ids)
        session.commit()
    except EmbeddingError:
        session.rollback()
        raise AppError(
            "EMBEDDING_UNAVAILABLE", "Chưa thể lưu việc tuyển dụng. Vui lòng thử lại.", 503
        ) from None
    except Exception:
        session.rollback()
        raise
    return response(session, job, needs_rescore=needs_rescore)


def replace_members(
    session: Session, actor: User, job_id: UUID, user_ids: list[UUID]
) -> JobResponse:
    job = get_job(session, actor, job_id, lock=True)
    _replace_members(session, job, user_ids)
    session.commit()
    return response(session, job)

"""Task scope follows current Job membership, including for background reminders."""

from datetime import UTC, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.permissions import authorize
from app.models import Application, Job, JobMember, Task, User
from app.models.enums import ActivityType, TaskStatus
from app.models.users import UserRole
from app.schemas.tasks import TaskCreate, TaskList, TaskPatch, TaskRead
from app.services.activity import log_activity
from app.services.applications import accessible_job
from app.services.profile import accessible_application
from app.services.ranking import visible_applications

VIETNAM = ZoneInfo("Asia/Ho_Chi_Minh")
OPEN = (TaskStatus.todo, TaskStatus.doing)
CONTACT = "Liên hệ ứng viên"
RESULT = "Cập nhật kết quả phỏng vấn"


def job_scope(actor: User):
    query = select(Job.id)
    if actor.role == UserRole.recruiter:
        query = query.where(
            or_(
                Job.owner_id == actor.id,
                exists().where(JobMember.job_id == Job.id, JobMember.user_id == actor.id),
            )
        )
    return query


def visible_tasks(actor: User, mine: bool = True):
    authorize(actor, "jobs.create")
    if not mine and actor.role == UserRole.recruiter:
        raise AppError("FORBIDDEN", "Bạn chỉ được xem việc của mình.", 403)
    eligible = visible_applications().with_only_columns(Application.id)
    query = select(Task).where(
        Task.deleted_at.is_(None),
        or_(Task.job_id.is_(None), Task.job_id.in_(job_scope(actor))),
        or_(Task.application_id.is_(None), Task.application_id.in_(eligible)),
    )
    if mine:
        query = query.where(Task.assignee_id == actor.id)
    return query


def list_tasks(
    session: Session,
    actor: User,
    mine: bool = True,
    status: TaskStatus | None = None,
    due_before: datetime | None = None,
    page: int = 1,
    page_size: int = 20,
) -> TaskList:
    query = visible_tasks(actor, mine).where(
        Task.status == status if status else Task.status.in_(OPEN)
    )
    if due_before is not None:
        query = query.where(Task.due_at < due_before)
    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = session.scalars(
        query.order_by(Task.due_at.asc().nulls_last(), Task.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return TaskList(items=[TaskRead.model_validate(row) for row in rows], total=total)


def create_task(session: Session, actor: User, body: TaskCreate) -> TaskRead:
    authorize(actor, "jobs.create")
    assignee = session.get(User, body.assignee_id or actor.id)
    if assignee is None or not assignee.is_active:
        raise AppError("INVALID_TASK_ASSIGNEE", "Người nhận việc không còn hoạt động.", 422)
    if actor.role == UserRole.recruiter and assignee.id != actor.id:
        raise AppError("FORBIDDEN", "Bạn chỉ được tạo việc cho mình.", 403)
    with session.begin_nested():
        # Share the generator lock so a manual reminder and a rule cannot race.
        session.execute(select(func.pg_advisory_xact_lock(250025)))
        job_id = body.job_id
        if body.application_id:
            application = accessible_application(session, actor, body.application_id)
            if job_id is not None and job_id != application.job_id:
                raise AppError(
                    "INVALID_TASK_LINK", "Hồ sơ không thuộc việc tuyển dụng đã chọn.", 422
                )
            job_id = application.job_id
        if job_id:
            job = accessible_job(session, actor, job_id)
            authorize(assignee, "jobs.view", job, session=session)
        row = Task(
            **body.model_dump(exclude={"assignee_id", "job_id"}),
            assignee_id=assignee.id,
            created_by=actor.id,
            job_id=job_id,
        )
        session.add(row)
        session.flush()
        result = TaskRead.model_validate(row)
    session.commit()
    return result


def patch_task(session: Session, actor: User, task_id: UUID, body: TaskPatch) -> TaskRead:
    authorize(actor, "jobs.create")
    with session.begin_nested():
        row = session.scalar(
            select(Task)
            .where(Task.id == task_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if row is None or row.deleted_at is not None:
            raise AppError("NOT_FOUND", "Không tìm thấy việc cần làm.", 404)
        mine = actor.role == UserRole.recruiter
        allowed = session.scalar(visible_tasks(actor, mine).where(Task.id == row.id))
        if allowed is None:
            raise AppError("FORBIDDEN", "Bạn không có quyền sửa việc này.", 403)
        was_done = row.status == TaskStatus.done
        for key, value in body.model_dump(exclude_unset=True).items():
            setattr(row, key, value)
        if row.status == TaskStatus.done and not was_done:
            row.completed_at = datetime.now(UTC)
            candidate_id = None
            if row.application_id:
                application = session.get(Application, row.application_id)
                assert application is not None
                candidate_id = application.candidate_id
            log_activity(
                session,
                type=ActivityType.task_done,
                actor_id=actor.id,
                job_id=row.job_id,
                application_id=row.application_id,
                candidate_id=candidate_id,
                payload={"task_id": str(row.id)},
            )
        elif row.status != TaskStatus.done:
            row.completed_at = None
        session.flush()
        result = TaskRead.model_validate(row)
    session.commit()
    return result


def day_bounds(now: datetime):
    start = datetime.combine(now.astimezone(VIETNAM).date(), time.min, VIETNAM)
    return start, start + timedelta(days=1)


def due_tasks(session: Session, actor: User, now: datetime) -> list[Task]:
    _, end = day_bounds(now)
    return list(
        session.scalars(
            visible_tasks(actor)
            .where(Task.status.in_(OPEN), Task.due_at < end)
            .order_by(Task.due_at, Task.id)
        )
    )

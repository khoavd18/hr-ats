from datetime import UTC, datetime, timedelta

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from app.models import Application, AuditLog, Candidate, Interview, Job, Placement, User
from app.models.enums import ApplicationStage, JobStatus
from app.schemas.tasks import Overview, OverviewInterview, OverviewJob
from app.services.ranking import visible_applications
from app.services.tasks import day_bounds, job_scope, list_tasks


def overview(session: Session, actor: User) -> Overview:
    now = datetime.now(UTC)
    start, end = day_bounds(now)
    applications = visible_applications().where(Application.job_id.in_(job_scope(actor)))
    interview_query = (
        applications.join(Interview, Interview.application_id == Application.id)
        .join(Job, Job.id == Application.job_id)
        .where(
            Interview.deleted_at.is_(None),
            Interview.scheduled_at >= start,
            Interview.scheduled_at < end + timedelta(days=1),
        )
    )
    interviews = session.execute(
        interview_query.with_only_columns(
            Interview.id,
            Application.id.label("application_id"),
            Job.id.label("job_id"),
            Candidate.full_name.label("candidate_name"),
            Job.title.label("job_title"),
            Interview.scheduled_at,
        )
        .order_by(Interview.scheduled_at, Interview.id)
        .limit(20)
    ).mappings()
    placements = (
        select(func.count())
        .select_from(Placement)
        .join(Application, Application.id == Placement.application_id)
        .where(Application.job_id == Job.id, Placement.deleted_at.is_(None))
        .correlate(Job)
        .scalar_subquery()
    )
    jobs_query = select(Job).where(
        Job.id.in_(job_scope(actor)),
        Job.status == JobStatus.open,
        Job.deadline >= start.date(),
        Job.deadline <= start.date() + timedelta(days=7),
        placements < Job.headcount,
    )
    jobs = session.scalars(jobs_query.order_by(Job.deadline, Job.id).limit(20))
    viewed = exists().where(
        AuditLog.actor_id == actor.id,
        AuditLog.entity == "candidate",
        AuditLog.action == "view",
        AuditLog.entity_id == Candidate.id,
        AuditLog.occurred_at >= Application.created_at,
    )
    unseen = applications.where(Application.stage == ApplicationStage.new, ~viewed)
    return Overview(
        today_tasks=list_tasks(session, actor, due_before=end, page_size=20),
        interviews=[OverviewInterview.model_validate(row) for row in interviews],
        interview_total=session.scalar(select(func.count()).select_from(interview_query.subquery()))
        or 0,
        jobs=[
            OverviewJob(id=row.id, title=row.title, deadline=row.deadline.isoformat())
            for row in jobs
            if row.deadline is not None
        ],
        job_total=session.scalar(select(func.count()).select_from(jobs_query.subquery())) or 0,
        unseen_cv_count=session.scalar(select(func.count()).select_from(unseen.subquery())) or 0,
    )

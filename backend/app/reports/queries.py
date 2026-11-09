"""T26 draft metric v1, specified in docs/specs/06-email-reports.md.

Each KPI accepts a UTC [start, end) and Filters. Results are keyed by None
(total), or by attributed user ID when grouped=True. SQL does the aggregation;
grouped reports never average individual ratios or medians. No CV text is read.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import Select, and_, case, exists, func, literal, or_, select, union_all
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.permissions import ResourceScope, authorize
from app.models import (
    Activity,
    AiFeedback,
    Application,
    CvFile,
    Interview,
    Job,
    JobMember,
    Offer,
    Placement,
    StageEvent,
    User,
)
from app.models.enums import ActivityType, ApplicationStage, JobStatus
from app.models.users import UserRole
from app.schemas.reports import (
    AgreementMetric,
    DailyCVs,
    FunnelStage,
    InterviewMetric,
    MedianMetric,
    Metrics,
    ReportInput,
    ReportPeriod,
    RevenueMetric,
)
from app.services.applications import accessible_job

VIETNAM = ZoneInfo("Asia/Ho_Chi_Minh")
FORWARD = tuple(ApplicationStage)[:6]
Key = UUID | None


@dataclass(frozen=True)
class Filters:
    actor: User
    as_of: datetime
    recruiter_id: UUID | None = None
    job_id: UUID | None = None
    hiring_unit_id: UUID | None = None
    grouped: bool = False

    @property
    def owner(self) -> UUID | None:
        owner = self.recruiter_id
        if self.actor.role == UserRole.recruiter and owner is None:
            owner = self.actor.id
        authorize(self.actor, "reports.view", ResourceScope(owner_id=owner))
        return owner


def prepare(
    session: Session, actor: User, params: ReportInput, *, now: datetime | None = None
) -> tuple[datetime, datetime, Filters, ReportPeriod]:
    filters = Filters(
        actor=actor,
        as_of=now or datetime.now(UTC),
        recruiter_id=params.recruiter_id,
        job_id=params.job_id,
        hiring_unit_id=params.hiring_unit_id,
    )
    owner = filters.owner
    if params.job_id is not None:
        accessible_job(session, actor, params.job_id)
    if owner is not None and session.get(User, owner) is None:
        raise AppError("NOT_FOUND", "Không tìm thấy người phụ trách.", 404)
    start = datetime.combine(params.from_date, time.min, VIETNAM).astimezone(UTC)
    end = datetime.combine(params.to_date, time.min, VIETNAM).astimezone(UTC)
    period = ReportPeriod(
        from_date=params.from_date,
        to_date=params.to_date,
        as_of=filters.as_of,
        recruiter_id=owner,
        job_id=params.job_id,
        hiring_unit_id=params.hiring_unit_id,
    )
    return start, end, filters, period


def _jobs(filters: Filters):
    query = select(Job.id)
    if filters.actor.role == UserRole.recruiter:
        member = exists().where(JobMember.job_id == Job.id, JobMember.user_id == filters.actor.id)
        query = query.where(or_(Job.owner_id == filters.actor.id, member))
    if filters.job_id is not None:
        query = query.where(Job.id == filters.job_id)
    if filters.hiring_unit_id is not None:
        query = query.where(Job.hiring_unit_id == filters.hiring_unit_id)
    return query


def _scope(query: Select, owner, job_id, filters: Filters, *, nullable_job=False) -> Select:
    attributed = filters.owner  # Service-level authorization, including direct KPI callers.
    if attributed is not None:
        query = query.where(owner == attributed)
    job_access = job_id.in_(_jobs(filters))
    if nullable_job and filters.job_id is None and filters.hiring_unit_id is None:
        job_access = or_(job_id.is_(None), job_access)
    return query.where(job_access)


def _application_query(model, filters: Filters) -> Select:
    return _scope(
        select().select_from(model).join(Application, Application.id == model.application_id),
        Application.owner_id,
        Application.job_id,
        filters,
    ).where(model.deleted_at.is_(None), Application.deleted_at.is_(None))


def _period(column, start: datetime, end: datetime):
    return and_(column >= start, column < end)


def _aggregate(session: Session, query: Select, owner, filters: Filters, *values):
    key = owner if filters.grouped else literal(None)
    query = query.add_columns(key.label("recruiter_id"), *values)
    if filters.grouped:
        query = query.group_by(owner)
    return session.execute(query).mappings().all()


def _count(session: Session, query: Select, owner, filters: Filters) -> dict[Key, int]:
    return {
        row["recruiter_id"]: row["count"]
        for row in _aggregate(session, query, owner, filters, func.count().label("count"))
    }


def _cv_query(start: datetime, end: datetime, filters: Filters):
    owner = func.coalesce(CvFile.uploaded_by, Job.owner_id)
    query = _scope(
        select().select_from(CvFile).outerjoin(Job, Job.id == CvFile.job_id),
        owner,
        CvFile.job_id,
        filters,
        nullable_job=True,
    ).where(CvFile.deleted_at.is_(None), _period(CvFile.created_at, start, end))
    return query, owner


def new_cvs(session: Session, start: datetime, end: datetime, filters: Filters) -> dict[Key, int]:
    query, owner = _cv_query(start, end, filters)
    return _count(session, query, owner, filters)


def new_cvs_by_day(
    session: Session, start: datetime, end: datetime, filters: Filters
) -> list[DailyCVs]:
    query, _ = _cv_query(start, end, filters)
    day_column = func.date(func.timezone("Asia/Ho_Chi_Minh", CvFile.created_at))
    counts = {
        day: count
        for day, count in session.execute(
            query.add_columns(day_column, func.count()).group_by(day_column)
        )
    }
    first, stop = start.astimezone(VIETNAM).date(), end.astimezone(VIETNAM).date()
    return [
        DailyCVs(date=day, count=counts.get(day, 0))
        for offset in range((stop - first).days)
        if (day := first + timedelta(days=offset)) < stop
    ]


def screened(session: Session, start: datetime, end: datetime, filters: Filters) -> dict[Key, int]:
    query = _application_query(StageEvent, filters).where(
        _period(StageEvent.occurred_at, start, end),
        StageEvent.from_stage == ApplicationStage.new,
        StageEvent.to_stage != ApplicationStage.new,
    )
    return _count(session, query, Application.owner_id, filters)


def submitted(session: Session, start: datetime, end: datetime, filters: Filters) -> dict[Key, int]:
    query = _application_query(StageEvent, filters).where(
        _period(StageEvent.occurred_at, start, end),
        StageEvent.to_stage == ApplicationStage.submitted,
    )
    return _count(session, query, Application.owner_id, filters)


def interviews(
    session: Session, start: datetime, end: datetime, filters: Filters
) -> dict[Key, InterviewMetric]:
    query = _application_query(Interview, filters).where(
        _period(Interview.scheduled_at, start, end)
    )
    return {
        row["recruiter_id"]: InterviewMetric(
            total=row["total"], elapsed=row["elapsed"], upcoming=row["upcoming"]
        )
        for row in _aggregate(
            session,
            query,
            Application.owner_id,
            filters,
            func.count().label("total"),
            func.count().filter(Interview.scheduled_at < filters.as_of).label("elapsed"),
            func.count().filter(Interview.scheduled_at >= filters.as_of).label("upcoming"),
        )
    }


def offers(session: Session, start: datetime, end: datetime, filters: Filters) -> dict[Key, int]:
    query = _application_query(Offer, filters).where(_period(Offer.sent_at, start, end))
    return _count(session, query, Application.owner_id, filters)


def placements(
    session: Session, start: datetime, end: datetime, filters: Filters
) -> dict[Key, int]:
    query = _application_query(Placement, filters).where(_period(Placement.created_at, start, end))
    return _count(session, query, Application.owner_id, filters)


def _visits(filters: Filters):
    events = _application_query(StageEvent, filters).add_columns(
        Application.owner_id.label("owner_id"),
        Application.id.label("application_id"),
        StageEvent.to_stage.label("stage"),
        StageEvent.occurred_at.label("entered_at"),
        StageEvent.created_at.label("recorded_at"),
        StageEvent.id.label("event_id"),
        literal(1).label("entry_order"),
    )
    # T12 creates applications without an initial StageEvent. Fill only that
    # missing entry; an explicit initial event always takes precedence.
    initial = _scope(
        select().select_from(Application), Application.owner_id, Application.job_id, filters
    ).where(
        Application.deleted_at.is_(None),
        ~exists().where(
            StageEvent.application_id == Application.id,
            StageEvent.from_stage.is_(None),
            StageEvent.to_stage == ApplicationStage.new,
            StageEvent.deleted_at.is_(None),
        ),
    )
    initial = initial.add_columns(
        Application.owner_id,
        Application.id,
        literal(ApplicationStage.new.value, type_=StageEvent.to_stage.type),
        Application.created_at,
        Application.created_at,
        Application.id,
        literal(0),
    )
    return union_all(events, initial).subquery()


def stage_conversion(
    session: Session, start: datetime, end: datetime, filters: Filters
) -> dict[Key, list[FunnelStage]]:
    visits = _visits(filters)
    owner = visits.c.owner_id if filters.grouped else literal(None)
    rows = session.execute(
        select(owner, visits.c.stage, func.count(func.distinct(visits.c.application_id)))
        .where(_period(visits.c.entered_at, start, end))
        .group_by(owner, visits.c.stage)
    )
    counts: dict[Key, dict[ApplicationStage, int]] = {}
    for key, stage, count in rows:
        counts.setdefault(key, {})[stage] = count
    if not filters.grouped:
        counts.setdefault(None, {})
    return {key: funnel_rows(values) for key, values in counts.items()}


def funnel_rows(counts: dict[ApplicationStage, int]) -> list[FunnelStage]:
    result = []
    for stage in ApplicationStage:
        next_stage = FORWARD[FORWARD.index(stage) + 1] if stage in FORWARD[:-1] else None
        count = counts.get(stage, 0)
        next_count = counts.get(next_stage, 0) if next_stage is not None else None
        result.append(
            FunnelStage(
                stage=stage,
                count=count,
                next_stage=next_stage,
                next_count=next_count,
                conversion_rate=next_count / count if count and next_count is not None else None,
            )
        )
    return result


def time_to_fill(
    session: Session, start: datetime, end: datetime, filters: Filters
) -> dict[Key, MedianMetric]:
    query = (
        _application_query(Placement, filters)
        .join(Job, Job.id == Application.job_id)
        .where(_period(Placement.created_at, start, end))
    )
    valid = and_(Job.opened_at.is_not(None), Placement.created_at >= Job.opened_at)
    days = func.extract("epoch", Placement.created_at - Job.opened_at) / 86400.0
    return {
        row["recruiter_id"]: MedianMetric(
            days=row["days"], sample_count=row["samples"], excluded_count=row["excluded"]
        )
        for row in _aggregate(
            session,
            query,
            Application.owner_id,
            filters,
            func.percentile_cont(0.5).within_group(case((valid, days))).label("days"),
            func.count().filter(valid).label("samples"),
            func.count().filter(~valid).label("excluded"),
        )
    }


def stage_duration(
    session: Session, start: datetime, end: datetime, filters: Filters
) -> dict[Key, dict[ApplicationStage, MedianMetric]]:
    visits = _visits(filters)
    closed = select(
        visits,
        func.lead(visits.c.entered_at)
        .over(
            partition_by=visits.c.application_id,
            order_by=(
                visits.c.entered_at,
                visits.c.entry_order,
                visits.c.recorded_at,
                visits.c.event_id,
            ),
        )
        .label("exited_at"),
    ).subquery()
    owner = closed.c.owner_id if filters.grouped else literal(None)
    days = func.extract("epoch", closed.c.exited_at - closed.c.entered_at) / 86400.0
    rows = session.execute(
        select(
            owner,
            closed.c.stage,
            func.percentile_cont(0.5).within_group(days),
            func.count(),
        )
        .where(_period(closed.c.exited_at, start, end))
        .group_by(owner, closed.c.stage)
    )
    result: dict[Key, dict[ApplicationStage, MedianMetric]] = {}
    for key, stage, median, samples in rows:
        result.setdefault(key, {})[stage] = MedianMetric(days=median, sample_count=samples)
    return result


def overdue_jobs(
    session: Session, start: datetime, end: datetime, filters: Filters
) -> dict[Key, int]:
    # Snapshot at as_of, not a flow inside [start, end). Count all placements
    # on the Job before applying recruiter attribution to the Job itself.
    filled = (
        select(func.count())
        .select_from(Placement)
        .join(Application, Application.id == Placement.application_id)
        .where(
            Application.job_id == Job.id,
            Application.deleted_at.is_(None),
            Placement.deleted_at.is_(None),
        )
        .correlate(Job)
        .scalar_subquery()
    )
    query = _scope(select().select_from(Job), Job.owner_id, Job.id, filters).where(
        Job.status == JobStatus.open,
        Job.deadline < filters.as_of.astimezone(VIETNAM).date(),
        filled < Job.headcount,
    )
    return _count(session, query, Job.owner_id, filters)


def placement_revenue(
    session: Session, start: datetime, end: datetime, filters: Filters
) -> dict[Key, RevenueMetric]:
    query = _application_query(Placement, filters).where(_period(Placement.created_at, start, end))
    return {
        row["recruiter_id"]: RevenueMetric(
            amount=int(row["amount"]) if row["amount"] is not None else None,
            known_count=row["known"],
            missing_count=row["missing"],
        )
        for row in _aggregate(
            session,
            query,
            Application.owner_id,
            filters,
            func.sum(Placement.fee_amount).label("amount"),
            func.count(Placement.fee_amount).label("known"),
            func.count().filter(Placement.fee_amount.is_(None)).label("missing"),
        )
    }


def ai_agreement(
    session: Session, start: datetime, end: datetime, filters: Filters
) -> dict[Key, AgreementMetric]:
    query = _application_query(AiFeedback, filters).where(
        _period(AiFeedback.created_at, start, end)
    )
    result = {}
    for row in _aggregate(
        session,
        query,
        Application.owner_id,
        filters,
        func.count().filter(AiFeedback.verdict == "agree").label("agree"),
        func.count().filter(AiFeedback.verdict == "disagree").label("disagree"),
    ):
        total = row["agree"] + row["disagree"]
        result[row["recruiter_id"]] = AgreementMetric(
            agree=row["agree"],
            disagree=row["disagree"],
            total=total,
            rate=row["agree"] / total if total else None,
        )
    return result


def activities(
    session: Session, start: datetime, end: datetime, filters: Filters
) -> dict[Key, dict[ActivityType, int]]:
    job_id = func.coalesce(Activity.job_id, Application.job_id)
    query = _scope(
        select()
        .select_from(Activity)
        .outerjoin(Application, Application.id == Activity.application_id),
        Activity.actor_id,
        job_id,
        filters,
        nullable_job=True,
    ).where(
        Activity.deleted_at.is_(None),
        or_(Activity.application_id.is_(None), Application.deleted_at.is_(None)),
        _period(Activity.occurred_at, start, end),
    )
    owner = Activity.actor_id if filters.grouped else literal(None)
    rows = session.execute(
        query.add_columns(owner, Activity.type, func.count()).group_by(owner, Activity.type)
    )
    result: dict[Key, dict[ActivityType, int]] = {}
    for key, kind, count in rows:
        result.setdefault(key, {})[kind] = count
    return result


def collect(
    session: Session, start: datetime, end: datetime, filters: Filters
) -> dict[Key, Metrics]:
    """At most one SQL aggregate per KPI, regardless of the number of recruiters."""
    functions: dict[str, Callable[[Session, datetime, datetime, Filters], dict[Key, Any]]] = {
        "new_cvs": new_cvs,
        "screened": screened,
        "submitted": submitted,
        "interviews": interviews,
        "offers": offers,
        "placements": placements,
        "funnel": stage_conversion,
        "time_to_fill": time_to_fill,
        "stage_duration": stage_duration,
        "overdue_jobs": overdue_jobs,
        "placement_revenue": placement_revenue,
        "ai_agreement": ai_agreement,
        "activities": activities,
    }
    values: dict[Key, dict[str, Any]] = {}
    for name, query in functions.items():
        for key, value in query(session, start, end, filters).items():
            values.setdefault(key, {})[name] = value
    return {key: complete_metrics(Metrics(**metrics)) for key, metrics in values.items()}


def complete_metrics(metrics: Metrics) -> Metrics:
    if not metrics.funnel:
        metrics.funnel = funnel_rows({})
    metrics.stage_duration = {
        stage: metrics.stage_duration.get(stage, MedianMetric()) for stage in ApplicationStage
    }
    metrics.activities = {kind: metrics.activities.get(kind, 0) for kind in ActivityType}
    return metrics

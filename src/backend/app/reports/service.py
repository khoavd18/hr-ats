from dataclasses import replace
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User
from app.models.users import UserRole
from app.reports import queries
from app.schemas.reports import (
    AgreementMetric,
    AgreementReport,
    FunnelReport,
    Metrics,
    RecruiterMetrics,
    RecruitersReport,
    ReportInput,
    ReportPeriod,
    SummaryReport,
)


def summary(
    session: Session, actor: User, params: ReportInput, *, now: datetime | None = None
) -> SummaryReport:
    start, end, filters, period = queries.prepare(session, actor, params, now=now)
    return SummaryReport(
        period=period,
        metrics=queries.collect(session, start, end, filters)[None],
        new_cvs_by_day=queries.new_cvs_by_day(session, start, end, filters),
    )


def funnel(session: Session, actor: User, params: ReportInput) -> FunnelReport:
    start, end, filters, period = queries.prepare(session, actor, params)
    return FunnelReport(
        period=period, stages=queries.stage_conversion(session, start, end, filters)[None]
    )


def agreement(session: Session, actor: User, params: ReportInput) -> AgreementReport:
    start, end, filters, period = queries.prepare(session, actor, params)
    return AgreementReport(
        period=period,
        agreement=queries.ai_agreement(session, start, end, filters).get(None, AgreementMetric()),
    )


def recruiter_rows(
    session: Session,
    start: datetime,
    end: datetime,
    filters: queries.Filters,
    period: ReportPeriod,
) -> RecruitersReport:
    values = queries.collect(session, start, end, replace(filters, grouped=True))
    users = select(User.id, User.full_name)
    if filters.owner is not None:
        users = users.where(User.id == filters.owner)
    else:
        # Include inactive people and non-recruiter roles with attributed data;
        # zero rows for recruiters keep a quiet period visible to the team lead.
        users = users.where(
            (User.role == UserRole.recruiter) | User.id.in_([key for key in values if key])
        )
    items = [
        RecruiterMetrics(
            recruiter_id=row.id,
            recruiter_name=row.full_name,
            metrics=values.get(row.id) or queries.complete_metrics(Metrics()),
        )
        for row in session.execute(users.order_by(User.full_name, User.id))
    ]
    if None in values:
        items.append(RecruiterMetrics(recruiter_id=None, recruiter_name=None, metrics=values[None]))
    return RecruitersReport(period=period, items=items)


def recruiters(session: Session, actor: User, params: ReportInput) -> RecruitersReport:
    start, end, filters, period = queries.prepare(session, actor, params)
    return recruiter_rows(session, start, end, filters, period)

"""Read-only ranking and page-batched counts, scoped to authorized Jobs by callers."""

from datetime import datetime
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import String, case, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.applications import Application
from app.models.candidates import Candidate
from app.models.enums import AiLevel, ApplicationStage, ProcessingStatus
from app.models.users import User
from app.schemas.ranking import AiCounts, ApplicationRanking, RankedApplication
from app.services.applications import accessible_job


def visible_applications():
    today = datetime.now(ZoneInfo(get_settings().tz)).date()
    return (
        select(Application)
        .join(Candidate, Candidate.id == Application.candidate_id)
        .where(
            Application.deleted_at.is_(None),
            Candidate.deleted_at.is_(None),
            Candidate.merged_into_id.is_(None),
            Candidate.retention_until >= today,
        )
    )


def counts_for_jobs(session: Session, job_ids: list[UUID]) -> dict[UUID, AiCounts]:
    counts = {job_id: AiCounts() for job_id in job_ids}
    if not counts:
        return counts
    bucket = case(
        (
            Application.ai_status == ProcessingStatus.done,
            func.coalesce(Application.ai_level.cast(String), "insufficient"),
        ),
        else_=Application.ai_status.cast(String),
    )
    query = (
        visible_applications()
        .where(Application.job_id.in_(job_ids))
        .with_only_columns(Application.job_id, bucket.label("bucket"), func.count())
        .group_by(Application.job_id, bucket)
    )
    for job_id, key, count in session.execute(query):
        setattr(counts[job_id], key, count)
    return counts


def list_applications(
    session: Session,
    actor: User,
    job_id: UUID,
    page: int,
    page_size: int,
    stage: ApplicationStage | None,
    ai_level: AiLevel | None,
    q: str,
    sort: Literal["ai_score", "created_at"],
) -> ApplicationRanking:
    accessible_job(session, actor, job_id)
    query = visible_applications().where(Application.job_id == job_id)
    if stage is not None:
        query = query.where(Application.stage == stage)
    if ai_level is not None:
        query = query.where(
            Application.ai_status == ProcessingStatus.done, Application.ai_level == ai_level
        )
    if q.strip():
        term = q.strip()
        query = query.where(
            or_(
                Candidate.full_name.icontains(term, autoescape=True),
                Candidate.current_title.icontains(term, autoescape=True),
                Candidate.skills.cast(String).icontains(term, autoescape=True),
            )
        )
    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    level_order = case(
        (Application.ai_status != ProcessingStatus.done, 4),
        (Application.ai_level == AiLevel.high, 0),
        (Application.ai_level == AiLevel.medium, 1),
        (Application.ai_level == AiLevel.low, 2),
        else_=3,
    )
    order = [Application.created_at.desc(), Application.id]
    if sort == "ai_score":
        order = [level_order, Application.ai_score.desc().nulls_last(), *order]
    rows = session.execute(
        query.with_only_columns(
            Application.id,
            Candidate.id.label("candidate_id"),
            Candidate.full_name.label("candidate_name"),
            Candidate.skills,
            Candidate.years_experience,
            Application.stage,
            Application.created_at,
            Application.ai_status,
            Application.ai_level,
        )
        .order_by(*order)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return ApplicationRanking(
        items=[RankedApplication(**row._mapping) for row in rows],
        total=total,
        ai_counts=counts_for_jobs(session, [job_id])[job_id],
    )

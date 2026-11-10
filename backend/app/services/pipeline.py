"""Human-only pipeline transitions; history and activity commit with the stage."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.permissions import authorize
from app.models.activity import Activity
from app.models.applications import Application, StageEvent
from app.models.candidates import Candidate
from app.models.enums import ActivityType, ApplicationStage
from app.models.users import User, UserRole
from app.schemas.core import ApplicationRead
from app.schemas.pipeline import (
    JobPipeline,
    MoveInput,
    PipelineCard,
    PipelineColumn,
    RejectedReason,
    StageLabel,
)
from app.services.activity import log_activity
from app.services.applications import accessible_job, application_for_update, eligible_candidate
from app.services.ranking import visible_applications

OPEN_STAGES = (
    ApplicationStage.new,
    ApplicationStage.screening,
    ApplicationStage.submitted,
    ApplicationStage.interview,
    ApplicationStage.offer,
)
FORWARD_STAGES = (*OPEN_STAGES, ApplicationStage.hired)


def stage_labels(hiring_unit_label: str) -> list[StageLabel]:
    labels = (
        "Mới nhận",
        "Đang sàng lọc",
        f"Đã gửi {hiring_unit_label}",
        "Phỏng vấn",
        "Offer",
        "Nhận việc",
        "Không phù hợp",
        "Ứng viên rút",
    )
    return [
        StageLabel(code=stage, label=label)
        for stage, label in zip(ApplicationStage, labels, strict=True)
    ]


def can_move(from_stage: ApplicationStage, to_stage: ApplicationStage) -> bool:
    if from_stage not in OPEN_STAGES:
        return False
    if to_stage in {ApplicationStage.rejected, ApplicationStage.withdrawn}:
        return True
    return (
        to_stage in FORWARD_STAGES
        and abs(FORWARD_STAGES.index(from_stage) - FORWARD_STAGES.index(to_stage)) == 1
    )


def locked_application(session: Session, actor: User, application_id: UUID) -> Application:
    application = application_for_update(session, application_id)
    if application is None:
        raise AppError("NOT_FOUND", "Không tìm thấy hồ sơ ứng tuyển.", 404)
    authorize(actor, "applications.move", application, session=session)
    eligible_candidate(session, application.candidate_id)
    return application


def _change(
    session: Session,
    application: Application,
    to_stage: ApplicationStage,
    actor: User,
    now: datetime,
    *,
    note: str | None = None,
    rejected_reason: RejectedReason | None = None,
    undo_of: UUID | None = None,
) -> ApplicationRead:
    previous = application.stage
    application.stage = to_stage
    application.stage_entered_at = now
    application.rejected_reason = rejected_reason
    event = StageEvent(
        application_id=application.id,
        from_stage=previous,
        to_stage=to_stage,
        actor_id=actor.id,
        note=note,
        occurred_at=now,
    )
    session.add(event)
    session.flush()
    log_activity(
        session,
        type=ActivityType.stage_changed,
        actor_id=actor.id,
        job_id=application.job_id,
        application_id=application.id,
        candidate_id=application.candidate_id,
        occurred_at=now,
        payload={
            "from_stage": previous,
            "to_stage": to_stage,
            "stage_event_id": str(event.id),
            "undo_of": str(undo_of) if undo_of else None,
        },
    )
    # Free-form HR notes stay in stage_events, never metadata or application logs.
    return ApplicationRead.model_validate(application)


def move(
    session: Session,
    actor: User,
    application_id: UUID,
    to_stage: ApplicationStage,
    note: str | None = None,
    rejected_reason: RejectedReason | None = None,
    *,
    commit: bool = True,
) -> ApplicationRead:
    # Validate direct service callers as well as HTTP callers, without leaking input.
    try:
        data = MoveInput(to_stage=to_stage, note=note, rejected_reason=rejected_reason)
    except ValidationError:
        raise AppError("VALIDATION_ERROR", "Dữ liệu không hợp lệ.", 422) from None
    with session.begin_nested():
        application = locked_application(session, actor, application_id)
        if not can_move(application.stage, data.to_stage):
            raise AppError("INVALID_STAGE_TRANSITION", "Không thể chuyển sang bước này.", 409)
        snapshot = _change(
            session,
            application,
            data.to_stage,
            actor,
            datetime.now(UTC),
            note=data.note,
            rejected_reason=data.rejected_reason,
        )
    if commit:
        session.commit()
    return snapshot


def undo(session: Session, actor: User, application_id: UUID) -> ApplicationRead:
    with session.begin_nested():
        application = locked_application(session, actor, application_id)
        event = session.scalar(
            select(StageEvent)
            .where(
                StageEvent.application_id == application.id,
                StageEvent.deleted_at.is_(None),
            )
            .order_by(StageEvent.occurred_at.desc(), StageEvent.created_at.desc(), StageEvent.id)
            .limit(1)
        )
        if (
            event is None
            or event.from_stage is None
            or event.to_stage != application.stage
            or not can_move(event.from_stage, event.to_stage)
        ):
            raise AppError("UNDO_NOT_AVAILABLE", "Không có lần đổi bước nào để hoàn tác.", 409)
        is_undo = session.scalar(
            select(Activity.id)
            .where(
                Activity.application_id == application.id,
                Activity.type == ActivityType.stage_changed,
                Activity.payload["stage_event_id"].astext == str(event.id),
                Activity.payload["undo_of"].astext.is_not(None),
            )
            .limit(1)
        )
        if is_undo is not None:
            raise AppError("UNDO_NOT_AVAILABLE", "Lần đổi bước này đã được hoàn tác.", 409)
        if actor.id != event.actor_id and actor.role not in {UserRole.admin, UserRole.lead}:
            raise AppError("UNDO_FORBIDDEN", "Bạn chỉ có thể hoàn tác lần đổi bước của mình.", 403)
        now = datetime.now(UTC)
        if not timedelta(0) <= now - event.occurred_at <= timedelta(hours=24):
            raise AppError("UNDO_EXPIRED", "Chỉ có thể hoàn tác trong vòng 24 giờ.", 409)
        snapshot = _change(session, application, event.from_stage, actor, now, undo_of=event.id)
    session.commit()
    return snapshot


def for_job(session: Session, actor: User, job_id: UUID) -> JobPipeline:
    accessible_job(session, actor, job_id)
    rows = session.execute(
        visible_applications()
        .where(Application.job_id == job_id)
        .with_only_columns(
            Application.id,
            Candidate.id.label("candidate_id"),
            Candidate.full_name.label("candidate_name"),
            Application.stage,
            Application.stage_entered_at,
            Application.owner_id,
            Application.ai_status,
            Application.ai_level,
        )
        .order_by(Application.stage_entered_at, Application.id)
    ).all()
    columns = {stage: PipelineColumn(stage=stage, items=[], total=0) for stage in ApplicationStage}
    for row in rows:
        card = PipelineCard(**row._mapping)
        columns[card.stage].items.append(card)
        columns[card.stage].total += 1
    return JobPipeline(columns=list(columns.values()), total=len(rows))

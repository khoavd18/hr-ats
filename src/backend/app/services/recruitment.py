"""Human actions only; business records and pipeline history share a transaction."""

from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from icalendar import Calendar, Event, Timezone
from pydantic import ValidationError
from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.applications import Application
from app.models.enums import ActivityType, ApplicationStage
from app.models.jobs import Job, JobMember
from app.models.recruitment import Interview, Offer, Placement
from app.models.users import User, UserRole
from app.schemas.recruitment import (
    InterviewCreate,
    InterviewList,
    InterviewPatch,
    InterviewRead,
    OfferCreate,
    OfferPatch,
    OfferRead,
    PlacementCreate,
    PlacementPatch,
    PlacementRead,
    RecruitmentRecords,
)
from app.services import pipeline
from app.services.activity import log_activity
from app.services.applications import accessible_job, eligible_candidate
from app.services.ranking import visible_applications

VIETNAM = ZoneInfo("Asia/Ho_Chi_Minh")


def records(session: Session, application_id: UUID) -> RecruitmentRecords:
    """Internal only: caller must have authorized the application."""
    interviews = session.scalars(
        select(Interview)
        .where(Interview.application_id == application_id, Interview.deleted_at.is_(None))
        .order_by(Interview.scheduled_at, Interview.id)
    )
    offers = session.scalars(
        select(Offer)
        .where(Offer.application_id == application_id, Offer.deleted_at.is_(None))
        .order_by(Offer.created_at.desc(), Offer.id)
    )
    placement = session.scalar(
        select(Placement).where(
            Placement.application_id == application_id, Placement.deleted_at.is_(None)
        )
    )
    return RecruitmentRecords(
        interviews=[InterviewRead.model_validate(row) for row in interviews],
        offers=[OfferRead.model_validate(row) for row in offers],
        placement=PlacementRead.model_validate(placement) if placement else None,
    )


def _record[Record: (Interview, Offer, Placement)](
    session: Session, actor: User, model: type[Record], record_id: UUID
) -> Record:
    row = session.get(model, record_id)
    if row is None or row.deleted_at is not None:
        raise AppError("NOT_FOUND", "Không tìm thấy dữ liệu.", 404)
    application = session.get(Application, row.application_id)
    if application is None or application.deleted_at is not None:
        raise AppError("NOT_FOUND", "Không tìm thấy hồ sơ ứng tuyển.", 404)
    accessible_job(session, actor, application.job_id)
    eligible_candidate(session, application.candidate_id)
    return row


def _locked_record[Record: (Interview, Offer, Placement)](
    session: Session, actor: User, model: type[Record], record_id: UUID
) -> Record:
    row = _record(session, actor, model, record_id)
    pipeline.locked_application(session, actor, row.application_id)
    # The application lock serializes every recruitment write, including concurrent PATCHes.
    session.refresh(row)
    if row.deleted_at is not None:
        raise AppError("NOT_FOUND", "Không tìm thấy dữ liệu.", 404)
    return row


def _advance(session: Session, actor: User, application: Application, target: ApplicationStage):
    if application.stage == target:
        return
    predecessor = {
        ApplicationStage.interview: ApplicationStage.submitted,
        ApplicationStage.offer: ApplicationStage.interview,
        ApplicationStage.hired: ApplicationStage.offer,
    }[target]
    if application.stage != predecessor:
        raise AppError("INVALID_STAGE_TRANSITION", "Hãy chuyển hồ sơ đến bước trước đó trước.", 409)
    pipeline.move(session, actor, application.id, target, commit=False)


def create_interview(
    session: Session, actor: User, application_id: UUID, body: InterviewCreate
) -> InterviewRead:
    with session.begin_nested():
        application = pipeline.locked_application(session, actor, application_id)
        _advance(session, actor, application, ApplicationStage.interview)
        row = Interview(application_id=application.id, **body.model_dump())
        session.add(row)
        session.flush()
        log_activity(
            session,
            type=ActivityType.interview_scheduled,
            actor_id=actor.id,
            job_id=application.job_id,
            application_id=application.id,
            candidate_id=application.candidate_id,
            payload={"interview_id": str(row.id)},
        )
        snapshot = InterviewRead.model_validate(row)
    session.commit()
    return snapshot


def patch_interview(
    session: Session, actor: User, interview_id: UUID, body: InterviewPatch
) -> InterviewRead:
    with session.begin_nested():
        row = _locked_record(session, actor, Interview, interview_id)
        for key, value in body.model_dump(exclude_unset=True).items():
            setattr(row, key, value)
        session.flush()
        snapshot = InterviewRead.model_validate(row)
    session.commit()
    return snapshot


def _offer_sent(session: Session, actor: User, application: Application, row: Offer):
    _advance(session, actor, application, ApplicationStage.offer)
    row.status = "sent"
    row.sent_at = datetime.now(UTC)
    session.flush()
    log_activity(
        session,
        type=ActivityType.offer_made,
        actor_id=actor.id,
        job_id=application.job_id,
        application_id=application.id,
        candidate_id=application.candidate_id,
        payload={"offer_id": str(row.id)},
    )


def create_offer(
    session: Session, actor: User, application_id: UUID, body: OfferCreate
) -> OfferRead:
    with session.begin_nested():
        application = pipeline.locked_application(session, actor, application_id)
        row = Offer(application_id=application.id, **body.model_dump())
        session.add(row)
        # sent_at must be set before flushing the row's sent-status CHECK.
        if row.status == "sent":
            row.sent_at = datetime.now(UTC)
        session.flush()
        if row.status == "sent":
            _offer_sent(session, actor, application, row)
        snapshot = OfferRead.model_validate(row)
    session.commit()
    return snapshot


def patch_offer(session: Session, actor: User, offer_id: UUID, body: OfferPatch) -> OfferRead:
    with session.begin_nested():
        row = _locked_record(session, actor, Offer, offer_id)
        previous = row.status
        target = body.status or previous
        transitions = {"draft": {"sent"}, "sent": {"accepted", "declined"}}
        if target != previous and target not in transitions.get(previous, set()):
            raise AppError("INVALID_OFFER_STATUS", "Không thể đổi trạng thái offer này.", 409)
        # Move before modifying the row so pipeline's savepoint cannot flush invalid sent_at.
        if previous == "draft" and target == "sent":
            application = pipeline.locked_application(session, actor, row.application_id)
            _offer_sent(session, actor, application, row)
        for key, value in body.model_dump(exclude_unset=True).items():
            setattr(row, key, value)
        session.flush()
        snapshot = OfferRead.model_validate(row)
    session.commit()
    return snapshot


def create_placement(
    session: Session, actor: User, application_id: UUID, body: PlacementCreate
) -> PlacementRead:
    with session.begin_nested():
        application = pipeline.locked_application(session, actor, application_id)
        if session.scalar(select(Placement.id).where(Placement.application_id == application.id)):
            raise AppError("PLACEMENT_EXISTS", "Hồ sơ đã có bản ghi nhận việc.", 409)
        _advance(session, actor, application, ApplicationStage.hired)
        row = Placement(application_id=application.id, **body.model_dump())
        session.add(row)
        session.flush()
        snapshot = PlacementRead.model_validate(row)
    session.commit()
    return snapshot


def patch_placement(
    session: Session, actor: User, placement_id: UUID, body: PlacementPatch
) -> PlacementRead:
    with session.begin_nested():
        row = _locked_record(session, actor, Placement, placement_id)
        values = body.model_dump(exclude_unset=True)
        try:
            PlacementCreate(
                start_date=values.get("start_date", row.start_date),
                fee_amount=values.get("fee_amount", row.fee_amount),
                guarantee_until=values.get("guarantee_until", row.guarantee_until),
            )
        except ValidationError:
            raise AppError(
                "VALIDATION_ERROR", "Hạn bảo hành phải từ ngày nhận việc.", 422
            ) from None
        for key, value in values.items():
            setattr(row, key, value)
        session.flush()
        snapshot = PlacementRead.model_validate(row)
    session.commit()
    return snapshot


def list_interviews(
    session: Session,
    actor: User,
    from_date: date | datetime | None,
    to_date: date | datetime | None,
    mine: bool,
    page: int,
    page_size: int,
) -> InterviewList:
    def boundary(value: date | datetime) -> datetime:
        return value if isinstance(value, datetime) else datetime.combine(value, time.min, VIETNAM)

    start = boundary(from_date) if from_date is not None else None
    end = boundary(to_date) if to_date is not None else None
    if start and end and start >= end:
        raise AppError("VALIDATION_ERROR", "Khoảng thời gian không hợp lệ.", 422)
    query = (
        visible_applications()
        .join(Job, Job.id == Application.job_id)
        .join(Interview, Interview.application_id == Application.id)
        .where(Interview.deleted_at.is_(None))
        .with_only_columns(Interview)
    )
    if actor.role == UserRole.recruiter:
        member = exists().where(JobMember.job_id == Job.id, JobMember.user_id == actor.id)
        query = query.where(or_(Job.owner_id == actor.id, member))
    if mine:
        query = query.where(Application.owner_id == actor.id)
    if start:
        query = query.where(Interview.scheduled_at >= start)
    if end:
        query = query.where(Interview.scheduled_at < end)
    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = session.scalars(
        query.order_by(Interview.scheduled_at, Interview.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return InterviewList(items=[InterviewRead.model_validate(row) for row in rows], total=total)


def calendar_file(session: Session, actor: User, interview_id: UUID) -> bytes:
    row = _record(session, actor, Interview, interview_id)
    start = row.scheduled_at.astimezone(VIETNAM)
    end = start + timedelta(minutes=row.duration_minutes)
    calendar = Calendar()
    calendar.add("prodid", "-//hr-ats//Lich phong van//VI")
    calendar.add("version", "2.0")
    calendar.add_component(
        Timezone.from_tzinfo(
            VIETNAM, first_date=start.date(), last_date=end.date() + timedelta(days=1)
        )
    )
    event = Event()
    event.add("uid", f"{row.id}@hr-ats.invalid")
    event.add("dtstamp", row.updated_at.astimezone(UTC))
    event.add("dtstart", start)
    event.add("dtend", end)
    event.add("summary", f"Phỏng vấn · Vòng {row.round}")
    if row.location_or_link:
        event.add("location", row.location_or_link)
    # No CV, candidate contacts, feedback, attendees or email dispatch in calendar export.
    calendar.add_component(event)
    return calendar.to_ical()

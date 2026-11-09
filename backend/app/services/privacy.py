"""Retention and erasure. Preserve anonymous facts, never log request evidence."""

from datetime import UTC, date, datetime, timedelta
from hashlib import sha256
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, null, or_, select, update
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.permissions import authorize
from app.models import (
    Activity,
    AiFeedback,
    Application,
    AuditLog,
    Candidate,
    CvFile,
    DataRequest,
    EmailMessage,
    InboundEmail,
    Interview,
    Offer,
    StageEvent,
    Task,
    User,
)
from app.models.enums import EmailStatus
from app.schemas.privacy import (
    AuditList,
    AuditRead,
    ConsentInput,
    DataRequestInput,
    DataRequestList,
    DataRequestRead,
    RetentionList,
    RetentionRead,
)
from app.services.audit import record_audit
from app.storage import Storage, StorageError
from app.workers.tasks import retention_date


def local_day(now: datetime) -> date:
    return now.astimezone(ZoneInfo("Asia/Ho_Chi_Minh")).date()


def _privacy_lock(session: Session) -> None:
    # Serializes two purge operators and the daily job, not ordinary HR traffic.
    session.execute(select(func.pg_advisory_xact_lock(290029)))


def _candidate(session: Session, candidate_id: UUID, *, lock: bool = False) -> Candidate:
    query = select(Candidate).where(Candidate.id == candidate_id)
    if lock:
        query = query.with_for_update()
    row = session.scalar(query.execution_options(populate_existing=True))
    if row is None:
        raise AppError("NOT_FOUND", "Không tìm thấy ứng viên.", 404)
    return row


def record_consent(
    session: Session,
    actor: User,
    candidate_id: UUID,
    body: ConsentInput,
    *,
    now: datetime | None = None,
) -> RetentionRead:
    now = now or datetime.now(UTC)
    candidate = _candidate(session, candidate_id, lock=True)
    authorize(actor, "job_candidates.view", candidate, session=session)
    if candidate.deleted_at or candidate.merged_into_id or candidate.purge_pending_at:
        raise AppError("NOT_FOUND", "Không tìm thấy ứng viên.", 404)
    if body.consent_at > now:
        raise AppError("INVALID_CONSENT", "Thời điểm đồng ý không được ở tương lai.", 422)
    if candidate.consent_at and body.consent_at <= candidate.consent_at:
        # Replay is harmless, but cannot grant another year using the same evidence.
        if (
            not body.extend_retention
            and body.consent_at == candidate.consent_at
            and body.note == candidate.consent_note
        ):
            return RetentionRead.model_validate(candidate)
        raise AppError("CONSENT_NOT_NEW", "Cần bằng chứng đồng ý mới hơn để cập nhật.", 409)
    if body.extend_retention:
        authorize(actor, "data_requests.manage")
        if local_day(body.consent_at) < local_day(now) - timedelta(days=30):
            raise AppError(
                "CONSENT_NOT_NEW", "Cần đồng ý mới trong 30 ngày gần đây để gia hạn.", 409
            )
        candidate.retention_until = retention_date(
            max(candidate.retention_until, local_day(now)), 12
        )
        candidate.expired_at = None
    candidate.consent_at = body.consent_at
    candidate.consent_note = body.note
    record_audit(
        session,
        actor_id=actor.id,
        action="candidate.retention_extend" if body.extend_retention else "candidate.consent",
        entity="candidate",
        entity_id=candidate.id,
    )
    session.flush()
    result = RetentionRead.model_validate(candidate)
    session.commit()
    return result


def retention_list(
    session: Session,
    actor: User,
    *,
    state: str = "expiring",
    q: str = "",
    page: int = 1,
    page_size: int = 20,
    now: datetime | None = None,
) -> RetentionList:
    authorize(actor, "data_requests.manage")
    today = local_day(now or datetime.now(UTC))
    query = select(Candidate).where(
        Candidate.merged_into_id.is_(None), Candidate.purged_at.is_(None)
    )
    if state == "expiring":
        query = query.where(Candidate.retention_until.between(today, today + timedelta(days=30)))
    elif state == "expired":
        query = query.where(Candidate.retention_until < today)
    if q.strip():
        query = query.where(Candidate.full_name.icontains(q.strip(), autoescape=True))
    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = session.scalars(
        query.order_by(Candidate.retention_until, Candidate.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return RetentionList(items=[RetentionRead.model_validate(row) for row in rows], total=total)


def _request_read(session: Session, row: DataRequest) -> DataRequestRead:
    result = DataRequestRead.model_validate(row)
    result.candidate_name = session.scalar(
        select(Candidate.full_name).where(Candidate.id == row.candidate_id)
    )
    return result


def create_request(session: Session, actor: User, body: DataRequestInput) -> DataRequestRead:
    authorize(actor, "data_requests.manage")
    candidate = _candidate(session, body.candidate_id, lock=True)
    if candidate.merged_into_id or candidate.purged_at:
        raise AppError("NOT_FOUND", "Không tìm thấy ứng viên.", 404)
    existing = session.scalar(
        select(DataRequest)
        .where(
            DataRequest.candidate_id == candidate.id,
            DataRequest.kind == body.kind,
            DataRequest.status == "open",
        )
        .order_by(DataRequest.created_at, DataRequest.id)
    )
    if existing:
        return _request_read(session, existing)
    row = DataRequest(**body.model_dump())
    session.add(row)
    session.flush()
    record_audit(
        session,
        actor_id=actor.id,
        action="data_request.create",
        entity="data_request",
        entity_id=row.id,
    )
    result = _request_read(session, row)
    session.commit()
    return result


def list_requests(
    session: Session, actor: User, *, page: int = 1, page_size: int = 20
) -> DataRequestList:
    authorize(actor, "data_requests.manage")
    total = session.scalar(select(func.count()).select_from(DataRequest)) or 0
    rows = session.execute(
        select(DataRequest, Candidate.full_name)
        .join(Candidate, Candidate.id == DataRequest.candidate_id)
        .order_by(DataRequest.created_at.desc(), DataRequest.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return DataRequestList(
        items=[
            DataRequestRead.model_validate(row).model_copy(update={"candidate_name": name})
            for row, name in rows
        ],
        total=total,
    )


def list_audit(
    session: Session,
    actor: User,
    *,
    actor_id: UUID | None = None,
    action: str = "",
    entity: str = "",
    system: bool = False,
    page: int = 1,
    page_size: int = 20,
) -> AuditList:
    authorize(actor, "audit_log.view")
    query = select(AuditLog)
    if actor_id is not None:
        query = query.where(AuditLog.actor_id == actor_id)
    if system:
        query = query.where(AuditLog.actor_id.is_(None))
    if action:
        query = query.where(AuditLog.action == action)
    if entity:
        query = query.where(AuditLog.entity == entity)
    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = session.scalars(
        query.order_by(AuditLog.occurred_at.desc(), AuditLog.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return AuditList(items=[AuditRead.model_validate(row) for row in rows], total=total)


def _family(session: Session, candidate_id: UUID) -> list[UUID]:
    # Merge retains aliases with their own PII; erase all predecessors too.
    family = select(Candidate.id).where(Candidate.id == candidate_id).cte(recursive=True)
    family = family.union(
        select(Candidate.id).join(family, Candidate.merged_into_id == family.c.id)
    )
    return list(session.scalars(select(family.c.id).order_by(family.c.id)))


def freeze_candidate(session: Session, candidate_id: UUID, now: datetime) -> None:
    _privacy_lock(session)
    # Same identity lock as merge/parse; the family cannot change while frozen.
    session.execute(select(func.pg_advisory_xact_lock(0x4356, 10)))
    candidate = _candidate(session, candidate_id, lock=True)
    if candidate.merged_into_id:
        raise AppError("NOT_FOUND", "Hồ sơ đã được gộp. Hãy chọn hồ sơ đang sử dụng.", 404)
    for row in session.scalars(
        select(Candidate)
        .where(Candidate.id.in_(_family(session, candidate_id)))
        .order_by(Candidate.id)
        .with_for_update()
    ):
        if row.purge_pending_at is None:
            row.purge_pending_at = now
        if row.deleted_at is None:
            row.deleted_at = now
    # Durable denial of access even if storage is unavailable or the process dies.
    session.commit()


def purge_candidate(
    session: Session,
    storage: Storage,
    candidate_id: UUID,
    *,
    actor_id: UUID | None,
    now: datetime,
) -> None:
    _privacy_lock(session)
    candidate = _candidate(session, candidate_id)
    if candidate.purge_pending_at is None:
        raise ValueError("Freeze required before erasure")
    ids = _family(session, candidate_id)
    if candidate.purged_at is None:
        # No Candidate row lock here: old writers may hold a child row while
        # checking eligibility. They must see the committed freeze and exit.
        files = list(
            session.scalars(
                select(CvFile)
                .where(CvFile.candidate_id.in_(ids))
                .order_by(CvFile.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )
        try:
            for file in files:
                if file.storage_key:
                    storage.delete(file.storage_key)
        except StorageError:
            session.rollback()
            raise AppError(
                "STORAGE_UNAVAILABLE",
                "Chưa xoá hết tệp. Hồ sơ đã bị khoá; hãy thử lại yêu cầu xoá.",
                503,
            ) from None
        apps = select(Application.id).where(Application.candidate_id.in_(ids))
        file_ids = [file.id for file in files]
        # Preserve deleted_at on historical facts so KPI populations do not change.
        session.execute(
            update(CvFile)
            .where(CvFile.candidate_id.in_(ids))
            .values(
                storage_key=None,
                original_filename=None,
                sha256=None,
                extracted_text=None,
                parsed_json=null(),
                error=None,
            )
        )
        session.execute(
            update(Application)
            .where(Application.candidate_id.in_(ids))
            .values(
                rejected_reason=None,
                ai_criteria=null(),
                ai_reasons=null(),
                ai_flags=null(),
            )
        )
        session.execute(
            update(StageEvent).where(StageEvent.application_id.in_(apps)).values(note=None)
        )
        session.execute(
            update(AiFeedback).where(AiFeedback.application_id.in_(apps)).values(comment=None)
        )
        session.execute(
            update(Interview)
            .where(Interview.application_id.in_(apps))
            .values(feedback=None, location_or_link=None, interviewers=null())
        )
        session.execute(
            update(Offer).where(Offer.application_id.in_(apps)).values(notes=None, salary=None)
        )
        session.execute(
            update(Task)
            .where(Task.application_id.in_(apps))
            .values(title=None, description=None, deleted_at=now)
        )
        # Daily task-reminder snapshots can contain HR-authored candidate names.
        # They have no application FK, so erase snapshots for affected assignees.
        from app.workers.reminders import is_reminder

        assignees = select(Task.assignee_id).where(Task.application_id.in_(apps))
        reminder_ids = [
            row.id
            for row in session.scalars(
                select(EmailMessage).where(
                    EmailMessage.created_by.in_(assignees), EmailMessage.application_id.is_(None)
                )
            )
            if is_reminder(row)
        ]
        session.execute(
            update(EmailMessage)
            .where(
                or_(
                    EmailMessage.application_id.in_(apps),
                    EmailMessage.id.in_([*file_ids, *reminder_ids]),
                )
            )
            .values(
                to_email=None,
                cc=null(),
                subject=None,
                body_html=None,
                message_id=None,
                scheduled_for=None,
                error=None,
                deleted_at=now,
                status=EmailStatus.cancelled,
            )
        )
        contacts = select(Candidate.email).where(
            Candidate.id.in_(ids), Candidate.email.is_not(None)
        )
        inbound_ids = []
        for payload in session.scalars(
            select(Activity.payload).where(
                Activity.payload["cv_file_id"].astext.in_([str(value) for value in file_ids])
            )
        ):
            for reference in payload.get("inbound_messages", []):
                try:
                    inbound_ids.append(UUID(reference["inbound_email_id"]))
                except (ValueError, TypeError, KeyError):
                    continue
        for inbound in session.scalars(
            select(InboundEmail)
            .where(or_(InboundEmail.from_email.in_(contacts), InboundEmail.id.in_(inbound_ids)))
            .with_for_update()
        ):
            if inbound.message_id and not inbound.message_id.startswith("purged:"):
                # Preserve an opaque dedupe marker, never the original header.
                inbound.message_id = "purged:" + sha256(inbound.message_id.encode()).hexdigest()
            inbound.from_email = None
            inbound.subject = None
            inbound.error = None
            inbound.deleted_at = now
        # Resolve inbox references before clearing their source metadata. Upload
        # activities may predate candidate/application assignment.
        session.execute(
            update(Activity)
            .where(
                or_(
                    Activity.candidate_id.in_(ids),
                    Activity.application_id.in_(apps),
                    Activity.payload["cv_file_id"].astext.in_([str(value) for value in file_ids]),
                )
            )
            .values(payload={})
        )
        session.execute(
            update(DataRequest)
            .where(DataRequest.candidate_id.in_(ids))
            .values(requested_by_note=None)
        )
        for person_id in ids:
            person = _candidate(session, person_id)
            if person.purged_at is None:
                record_audit(
                    session,
                    actor_id=actor_id,
                    action="candidate.purge",
                    entity="candidate",
                    entity_id=person_id,
                )
        session.execute(
            update(Candidate)
            .where(Candidate.id.in_(ids))
            .values(
                full_name=None,
                email=None,
                phone=None,
                location=None,
                current_title=None,
                years_experience=None,
                skills=null(),
                languages=null(),
                education=null(),
                experiences=null(),
                consent_at=None,
                consent_note=None,
                anonymized_text=None,
                embedding=None,
                purged_at=now,
            )
        )
    session.execute(
        update(DataRequest)
        .where(
            DataRequest.candidate_id.in_(ids),
            DataRequest.kind == "delete",
            DataRequest.status == "open",
        )
        .values(status="done", handled_by=actor_id, handled_at=now, requested_by_note=None)
    )
    session.commit()


def execute_request(
    session: Session, actor: User, request_id: UUID, storage: Storage
) -> DataRequestRead:
    authorize(actor, "data_requests.manage")
    row = session.get(DataRequest, request_id)
    if row is None:
        raise AppError("NOT_FOUND", "Không tìm thấy yêu cầu.", 404)
    if row.status == "done":
        return _request_read(session, row)
    if row.status != "open" or row.kind != "delete":
        raise AppError("INVALID_DATA_REQUEST", "Yêu cầu không thể thực thi xoá.", 409)
    now = datetime.now(UTC)
    candidate_id = row.candidate_id
    freeze_candidate(session, candidate_id, now)
    purge_candidate(session, storage, candidate_id, actor_id=actor.id, now=now)
    return _request_read(session, session.get_one(DataRequest, request_id, populate_existing=True))


def enforce_retention(session: Session, storage: Storage, *, now: datetime | None = None) -> None:
    now = now or datetime.now(UTC)
    today = local_day(now)
    ids = list(
        session.scalars(
            select(Candidate.id)
            .where(
                Candidate.merged_into_id.is_(None),
                Candidate.purged_at.is_(None),
                or_(Candidate.retention_until < today, Candidate.purge_pending_at.is_not(None)),
            )
            .order_by(Candidate.id)
        )
    )
    for candidate_id in ids:
        _privacy_lock(session)
        session.execute(select(func.pg_advisory_xact_lock(0x4356, 10)))
        candidate = _candidate(session, candidate_id, lock=True)
        if candidate.purged_at:
            session.commit()
            continue
        if candidate.retention_until < today and candidate.expired_at is None:
            candidate.expired_at = now
        due = candidate.retention_until + timedelta(days=30) <= today
        pending = candidate.purge_pending_at is not None
        if not due and not pending:
            session.commit()
            continue
        # Freeze while still holding the retention row lock; a concurrent
        # extension either wins before this check or sees the frozen record.
        freeze_candidate(session, candidate_id, now)
        try:
            purge_candidate(session, storage, candidate_id, actor_id=None, now=now)
        except AppError:
            session.rollback()
            # Retry on the next daily run; one storage failure cannot stop peers.
            continue

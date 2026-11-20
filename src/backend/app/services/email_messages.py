"""Drafts are inert. Only the explicit send action may authorize a delivery."""

from datetime import UTC, datetime
from email.utils import make_msgid
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.core.permissions import authorize
from app.email.render import markdown_html, render_email
from app.models import EmailMessage, EmailTemplate, HiringUnit, Interview, Job, User
from app.models.enums import ApplicationStage, EmailStatus
from app.schemas.email import (
    MessageCreate,
    MessageList,
    MessageRead,
    SendTemplateChoice,
    SendTemplateChoices,
    SuggestedEmail,
)
from app.services.applications import eligible_candidate
from app.services.email_templates import build_context
from app.services.profile import accessible_application


def active_template(session: Session, template_id: UUID) -> EmailTemplate:
    row = session.get(EmailTemplate, template_id, populate_existing=True)
    if row is None or not row.is_active:
        raise AppError("EMAIL_TEMPLATE_INACTIVE", "Mẫu email đã ngừng dùng.", 422)
    return row


def latest_interview(session: Session, application_id: UUID) -> Interview:
    row = session.scalar(
        select(Interview)
        .where(Interview.application_id == application_id, Interview.deleted_at.is_(None))
        .order_by(Interview.scheduled_at.desc(), Interview.id)
        .limit(1)
    )
    if row is None:
        raise AppError("EMAIL_MISSING_INTERVIEW_TIME", "Cần đặt lịch phỏng vấn trước khi gửi.", 422)
    return row


def preview(
    session: Session, actor: User, application_id: UUID, template_id: UUID, settings: Settings
) -> SuggestedEmail:
    application = accessible_application(session, actor, application_id)
    authorize(actor, "emails.send", application, session=session)
    template = active_template(session, template_id)
    candidate = eligible_candidate(session, application.candidate_id)
    recipient = candidate.email
    to_unit = template.stage == ApplicationStage.submitted or template.key == "submitted_to_unit"
    if to_unit:
        job = session.get_one(Job, application.job_id)
        unit = session.get_one(HiringUnit, job.hiring_unit_id)
        recipient = unit.contact_email
    if not recipient:
        code = "EMAIL_UNIT_NO_ADDRESS" if to_unit else "EMAIL_NO_ADDRESS"
        raise AppError(code, "Chưa có địa chỉ email người nhận.", 422)
    rendered = render_email(
        template.subject, template.body, build_context(session, actor, application_id, settings)
    )
    has_calendar = template.key == "interview_invite"
    if has_calendar:
        latest_interview(session, application_id)
    try:
        return SuggestedEmail(
            application_id=application_id,
            template_id=template.id,
            to_email=recipient,
            subject=rendered.subject,
            body=rendered.body,
            body_html=rendered.body_html,
            has_calendar=has_calendar,
        )
    except ValidationError:
        raise AppError(
            "EMAIL_INVALID_DRAFT", "Kiểm tra lại địa chỉ và nội dung email.", 422
        ) from None


def suggestion(
    session: Session, actor: User, application_id: UUID, stage: ApplicationStage, settings: Settings
) -> tuple[SuggestedEmail | None, str | None]:
    template = session.scalar(
        select(EmailTemplate)
        .where(EmailTemplate.stage == stage, EmailTemplate.is_active.is_(True))
        .order_by(EmailTemplate.created_at, EmailTemplate.id)
        .limit(1)
    )
    if template is None:
        return None, None
    try:
        return preview(session, actor, application_id, template.id, settings), None
    except AppError as exc:
        # A missing address/schedule/offer must not roll back a human stage change.
        if exc.status != 422:
            raise
        return None, exc.code


def template_choices(session: Session, actor: User, application_id: UUID) -> SendTemplateChoices:
    accessible_application(session, actor, application_id)
    rows = session.scalars(
        select(EmailTemplate)
        .where(EmailTemplate.is_active.is_(True))
        .order_by(EmailTemplate.created_at, EmailTemplate.id)
    )
    return SendTemplateChoices(items=[SendTemplateChoice(id=row.id, name=row.name) for row in rows])


def create(session: Session, actor: User, data: MessageCreate) -> MessageRead:
    application = accessible_application(session, actor, data.application_id)
    authorize(actor, "emails.send", application, session=session)
    if data.template_id:
        template = active_template(session, data.template_id)
        if template.key == "interview_invite":
            latest_interview(session, application.id)
    row = EmailMessage(
        application_id=application.id,
        template_id=data.template_id,
        to_email=data.to_email,
        subject=data.subject,
        body_html=markdown_html(data.body),
        created_by=actor.id,
        status=EmailStatus.draft,
    )
    session.add(row)
    session.flush()
    snapshot = MessageRead.model_validate(row)
    session.commit()
    return snapshot


def locked_message(session: Session, actor: User, message_id: UUID) -> EmailMessage:
    row = session.scalar(
        select(EmailMessage)
        .where(EmailMessage.id == message_id, EmailMessage.deleted_at.is_(None))
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row is None or row.application_id is None:
        raise AppError("NOT_FOUND", "Không tìm thấy email.", 404)
    application = accessible_application(session, actor, row.application_id)
    authorize(actor, "emails.send", application, session=session)
    return row


def send(session: Session, actor: User, message_id: UUID) -> MessageRead:
    row = locked_message(session, actor, message_id)
    if row.status in {EmailStatus.queued, EmailStatus.sent}:
        return MessageRead.model_validate(row)
    if row.status not in {EmailStatus.draft, EmailStatus.failed}:
        raise AppError("EMAIL_INVALID_STATUS", "Email này không thể gửi.", 409)
    if row.template_id:
        template = active_template(session, row.template_id)
        if template.key == "interview_invite":
            assert row.application_id is not None
            latest_interview(session, row.application_id)
    row.status = EmailStatus.queued
    row.created_by = actor.id
    row.error = None
    row.scheduled_for = datetime.now(UTC)
    # A new confirmation invalidates every older retry/delivery for this record.
    row.message_id = make_msgid(domain="hr-ats.invalid")
    delivery_id = row.message_id
    session.flush()
    snapshot = MessageRead.model_validate(row)
    session.commit()  # The independent worker must see authorization before publish.
    from app.workers.email import send_email_message

    try:
        assert snapshot.scheduled_for is not None
        send_email_message.apply_async(
            args=[str(row.id), delivery_id, snapshot.scheduled_for.isoformat()]
        )
    except Exception:
        session.expire_all()
        current = locked_message(session, actor, message_id)
        if current.status == EmailStatus.queued and current.message_id == delivery_id:
            current.status = EmailStatus.failed
            current.scheduled_for = None
            current.error = "Không thể xếp hàng gửi email. Vui lòng bấm gửi lại."
            session.commit()
        raise AppError(
            "EMAIL_QUEUE_UNAVAILABLE", "Chưa thể xếp hàng gửi email. Vui lòng thử lại.", 503
        ) from None
    return snapshot


def cancel(session: Session, actor: User, message_id: UUID) -> MessageRead:
    row = locked_message(session, actor, message_id)
    if row.status == EmailStatus.sent:
        raise AppError("EMAIL_INVALID_STATUS", "Email đã gửi không thể huỷ.", 409)
    row.status = EmailStatus.cancelled
    row.scheduled_for = None
    row.error = None
    session.flush()
    snapshot = MessageRead.model_validate(row)
    session.commit()
    return snapshot


def list_messages(
    session: Session, actor: User, application_id: UUID, page: int, page_size: int
) -> MessageList:
    accessible_application(session, actor, application_id)
    query = select(EmailMessage).where(
        EmailMessage.application_id == application_id, EmailMessage.deleted_at.is_(None)
    )
    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = session.scalars(
        query.order_by(EmailMessage.created_at.desc(), EmailMessage.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return MessageList(items=[MessageRead.model_validate(row) for row in rows], total=total)

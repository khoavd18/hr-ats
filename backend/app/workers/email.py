"""Deliver human-confirmed mail or verified intake receipts; queue only metadata."""

from datetime import UTC, datetime, timedelta
from email.message import EmailMessage as MIMEMessage
from email.utils import format_datetime
from uuid import UUID

from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.errors import AppError
from app.email.smtp import deliver, plain_text
from app.models import CvFile, EmailMessage, EmailTemplate, User
from app.models.enums import ActivityType, EmailStatus
from app.services.activity import log_activity
from app.services.email_messages import latest_interview
from app.services.profile import accessible_application
from app.services.recruitment import calendar_file
from app.workers.celery_app import celery_app
from app.workers.tasks import worker_session

RETRY_DELAYS = (60, 300, 900)
DELIVERY_FAILED = "Không thể gửi email. Vui lòng kiểm tra và gửi lại."


@celery_app.task(bind=True, name="send_email_message", max_retries=None, acks_late=True)
def send_email_message(
    self, message_id: str, delivery_id: str, scheduled_for: str, attempt: int = 0
) -> None:
    try:
        record_id = UUID(message_id)
    except (ValueError, TypeError, AttributeError):
        return
    delay: int | None = None
    next_attempt = attempt
    with worker_session() as session:
        # One global lock across workers makes the rolling-hour limit exact for
        # accepted messages, without introducing a counter table or another service.
        session.execute(select(func.pg_advisory_xact_lock(230023)))
        row = session.scalar(
            select(EmailMessage)
            .where(EmailMessage.id == record_id, EmailMessage.deleted_at.is_(None))
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if (
            row is None
            or row.message_id != delivery_id
            or row.status not in {EmailStatus.queued, EmailStatus.failed}
            or row.scheduled_for is None
            or row.scheduled_for.isoformat() != scheduled_for
        ):
            return
        now = datetime.now(UTC)
        actor = session.get(User, row.created_by, populate_existing=True)
        settings = get_settings()
        try:
            if actor is None:
                raise AppError("NOT_FOUND", "Không tìm thấy dữ liệu.", 404)
            if not actor.is_active:
                raise AppError("FORBIDDEN", "Tài khoản đã ngừng dùng.", 403)
            template = session.get(EmailTemplate, row.template_id) if row.template_id else None
            from app.email.inbound import receipt_candidate
            from app.workers.reminders import is_reminder, reminder_html

            # Intake receipts use a CV's UUID as their record UUID. Human drafts
            # always have independent UUIDs and still require the T23 send action.
            intake_receipt = session.get(CvFile, row.id) is not None
            task_reminder = is_reminder(row)
            application = None
            candidate_id = None
            job_id = None
            if task_reminder:
                if row.to_email != actor.email:
                    raise AppError("FORBIDDEN", "Người nhận đã thay đổi.", 403)
                row.body_html = reminder_html(session, actor, now)
            elif intake_receipt:
                candidate, cv_file = receipt_candidate(session, row, settings)
                candidate_id, job_id = candidate.id, cv_file.job_id
            else:
                if row.application_id is None:
                    raise AppError("NOT_FOUND", "Không tìm thấy dữ liệu.", 404)
                application = accessible_application(session, actor, row.application_id)
                candidate_id, job_id = application.candidate_id, application.job_id
            calendar = None
            if application and template and template.key == "interview_invite":
                calendar = calendar_file(
                    session, actor, latest_interview(session, application.id).id
                )
        except AppError:
            row.status = EmailStatus.failed
            row.error = "Không thể gửi email. Kiểm tra quyền truy cập và thông tin hồ sơ."
            row.scheduled_for = None
            session.commit()
            return
        recent = select(EmailMessage.sent_at).where(
            EmailMessage.sent_at >= now - timedelta(hours=1)
        )
        count = session.scalar(select(func.count()).select_from(recent.subquery())) or 0
        if row.scheduled_for > now:
            delay = max(1, int((row.scheduled_for - now).total_seconds()) + 1)
        elif count >= settings.email_rate_limit_per_hour:
            first = session.scalar(recent.order_by(EmailMessage.sent_at).limit(1))
            assert first is not None
            delay = max(1, int((first + timedelta(hours=1) - now).total_seconds()) + 1)
            row.status = EmailStatus.queued
            row.scheduled_for = now + timedelta(seconds=delay)
        else:
            message = MIMEMessage()
            message["From"] = settings.smtp_from
            message["To"] = row.to_email
            message["Subject"] = row.subject
            message["Message-ID"] = delivery_id
            message["Date"] = format_datetime(now)
            message.set_content(plain_text(row.body_html))
            message.add_alternative(row.body_html, subtype="html")
            if calendar:
                message.add_attachment(
                    calendar, maintype="text", subtype="calendar", filename="phong-van.ics"
                )
            try:
                deliver(settings, message, row.to_email)
            except Exception:
                # SMTP server responses may echo credentials, recipients or content.
                row.status = EmailStatus.failed
                row.error = DELIVERY_FAILED
                if attempt < len(RETRY_DELAYS):
                    delay = RETRY_DELAYS[attempt]
                    next_attempt = attempt + 1
                    row.scheduled_for = now + timedelta(seconds=delay)
                else:
                    row.scheduled_for = None
            else:
                row.status = EmailStatus.sent
                row.sent_at = datetime.now(UTC)
                row.scheduled_for = None
                row.error = None
                log_activity(
                    session,
                    type=ActivityType.email_sent,
                    actor_id=None if intake_receipt or task_reminder else actor.id,
                    job_id=job_id,
                    application_id=application.id if application else row.application_id,
                    candidate_id=candidate_id,
                    payload={"email_message_id": str(row.id)},
                )
        checkpoint = row.scheduled_for.isoformat() if row.scheduled_for else ""
        session.commit()
    if delay is not None and not self.request.is_eager:
        # The retry carries no original SMTP exception or message content.
        raise self.retry(
            countdown=delay,
            kwargs={
                "message_id": message_id,
                "delivery_id": delivery_id,
                "scheduled_for": checkpoint,
                "attempt": next_attempt,
            },
            args=(),
        )

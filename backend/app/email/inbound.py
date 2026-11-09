"""Bounded IMAP intake. Message bodies, credentials and exceptions are never logged."""

import hashlib
import imaplib
import re
import ssl
import unicodedata
from datetime import UTC, datetime
from email import policy
from email.parser import BytesParser
from email.utils import make_msgid, parseaddr, parsedate_to_datetime
from pathlib import PurePosixPath
from uuid import UUID

from pydantic import ValidationError
from redis import Redis
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.email.render import render_email
from app.models import (
    Application,
    Candidate,
    CvFile,
    EmailMessage,
    EmailTemplate,
    HiringUnit,
    InboundEmail,
    Job,
    User,
)
from app.models.enums import ActivityType, CandidateSource, EmailStatus, JobStatus, ProcessingStatus
from app.models.users import UserRole
from app.schemas.users import EmailInput
from app.services.activity import log_activity
from app.services.applications import eligible_candidate
from app.services.cv_validation import MAX_FILES, validate_file
from app.storage import build_storage
from app.workers.celery_app import celery_app
from app.workers.tasks import process_cv_file, worker_session

STATUS_KEY = "hr-ats:imap:status"
MAX_MESSAGE_BYTES = 50 * 1024 * 1024
MAX_MESSAGES_PER_POLL = 100


def job_code(job_id: UUID) -> str:
    return f"[JOB-{job_id.hex[:8].upper()}]"


def _normalized(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).casefold().split())


def match_job(session: Session, subject: str) -> Job | None:
    jobs = session.scalars(select(Job).where(Job.status == JobStatus.open)).all()
    codes = re.findall(r"\[JOB-([0-9a-f]{8})\]", subject, flags=re.IGNORECASE)
    # Ambiguous/unknown explicit codes never silently fall back to a title.
    if codes:
        matches = [job for job in jobs if job.id.hex[:8] in {code.lower() for code in codes}]
        return (
            matches[0]
            if len(matches) == 1 and len(set(code.lower() for code in codes)) == 1
            else None
        )
    matches = [job for job in jobs if _normalized(job.title) == _normalized(subject)]
    return matches[0] if len(matches) == 1 else None


def _lock(session: Session, value: str) -> None:
    session.execute(
        select(
            func.pg_advisory_xact_lock(
                int.from_bytes(hashlib.sha256(value.encode()).digest()[:8], "big", signed=True)
            )
        )
    )


def ingest_message(session: Session, raw: bytes, settings: Settings) -> None:
    """Commit every attachment and its dedupe marker together, before dispatch."""
    message = BytesParser(policy=policy.default).parsebytes(raw)
    message_id = str(message.get("Message-ID", "")).strip()[:998]
    if not message_id:
        message_id = "sha256:" + hashlib.sha256(raw).hexdigest()
    _lock(session, "inbound:" + message_id)
    if session.scalar(select(InboundEmail.id).where(InboundEmail.message_id == message_id)):
        session.commit()
        return
    parts = [
        part
        for part in message.walk()
        if not part.is_multipart()
        and (part.get_content_disposition() == "attachment" or part.get_filename() is not None)
    ]
    attachments: dict[str, tuple[bytes, str, str]] = {}
    invalid = len(parts) > MAX_FILES
    for part in parts[:MAX_FILES]:
        filename = PurePosixPath(str(part.get_filename() or "cv").replace("\\", "/")).name
        filename = "".join(char for char in filename if char.isprintable()).strip()[:255] or "cv"
        data = part.get_payload(decode=True)
        if not isinstance(data, bytes):
            invalid = True
            continue
        try:
            mime, digest = validate_file(data, filename)
        except AppError:
            invalid = True
            continue
        attachments[digest] = data, filename, mime
    subject = str(message.get("Subject", ""))[:2000]
    sender = parseaddr(str(message.get("From", "")))[1][:254]
    try:
        received_at = parsedate_to_datetime(str(message.get("Date", "")))
        received_at = received_at.replace(tzinfo=UTC) if received_at.tzinfo is None else received_at
    except (ValueError, TypeError, OverflowError):
        received_at = datetime.now(UTC)
    job = match_job(session, subject)
    storage = build_storage(settings)
    stored: list[str] = []
    try:
        # Same lock as upload T07; sort hashes so overlapping batches cannot deadlock.
        for digest, (data, filename, mime) in sorted(attachments.items()):
            session.execute(
                select(
                    func.pg_advisory_xact_lock(
                        int.from_bytes(bytes.fromhex(digest)[:8], "big", signed=True)
                    )
                )
            )
            if session.scalar(select(CvFile.id).where(CvFile.sha256 == digest)):
                continue
            key = storage.put(data, mime)
            stored.append(key)
            cv_file = CvFile(
                storage_key=key,
                original_filename=filename,
                mime_type=mime,
                size_bytes=len(data),
                sha256=digest,
                source=CandidateSource.email,
                job_id=job.id if job else None,
                uploaded_by=None,
            )
            session.add(cv_file)
            session.flush()
            log_activity(
                session,
                type=ActivityType.cv_uploaded,
                job_id=cv_file.job_id,
                payload={"cv_file_id": str(cv_file.id)},
            )
        session.add(
            InboundEmail(
                message_id=message_id,
                from_email=sender,
                subject=subject,
                received_at=received_at,
                attachment_count=len(parts),
                processed_at=datetime.now(UTC),
                status="processed" if attachments else "ignored",
                error="Một số tệp đính kèm không hợp lệ hoặc vượt giới hạn." if invalid else None,
            )
        )
        session.commit()
    except Exception:
        session.rollback()
        for key in stored:
            try:
                storage.delete(key)
            except Exception:
                pass
        raise


def receipt_candidate(
    session: Session, row: EmailMessage, settings: Settings
) -> tuple[Candidate, CvFile]:
    """Only an intake file can authorize this exception to human confirmation."""
    template = session.get(EmailTemplate, row.template_id) if row.template_id else None
    cv_file = session.get(CvFile, row.id, populate_existing=True)
    if (
        not settings.imap_enabled
        or template is None
        or template.key != "cv_received"
        or not template.is_active
        or template.requires_confirmation
        or cv_file is None
        or cv_file.deleted_at is not None
        or cv_file.source != CandidateSource.email
        or cv_file.status != ProcessingStatus.done
        or cv_file.candidate_id is None
    ):
        raise AppError("EMAIL_RECEIPT_INELIGIBLE", "Không thể xác nhận nhận CV.", 422)
    candidate = eligible_candidate(session, cv_file.candidate_id)
    if not candidate.email or candidate.email != row.to_email:
        raise AppError("EMAIL_RECEIPT_INELIGIBLE", "Không thể xác nhận nhận CV.", 422)
    return candidate, cv_file


def queue_receipt(session: Session, file_id: UUID, settings: Settings) -> None:
    if not settings.imap_enabled:
        return
    cv_file = session.scalar(select(CvFile).where(CvFile.id == file_id).with_for_update())
    if (
        cv_file is None
        or cv_file.source != CandidateSource.email
        or cv_file.status != ProcessingStatus.done
        or cv_file.deleted_at is not None
        or cv_file.candidate_id is None
    ):
        session.commit()
        return
    # A receipt shares its CV UUID across tables. API-created drafts cannot choose an ID.
    row = session.get(EmailMessage, file_id)
    if row is None:
        template = session.scalar(
            select(EmailTemplate).where(
                EmailTemplate.key == "cv_received",
                EmailTemplate.is_active.is_(True),
                EmailTemplate.requires_confirmation.is_(False),
            )
        )
        job = session.get(Job, cv_file.job_id) if cv_file.job_id else None
        actor = (
            session.get(User, job.owner_id)
            if job
            else session.scalar(
                select(User)
                .where(User.role == UserRole.admin, User.is_active.is_(True))
                .order_by(User.id)
                .limit(1)
            )
        )
        try:
            candidate = eligible_candidate(session, cv_file.candidate_id)
            if template is None or actor is None or not actor.is_active or not candidate.email:
                session.commit()
                return
            recipient = EmailInput(email=candidate.email).email
            company, _ = parseaddr(settings.smtp_from)
            context = {
                "candidate_name": candidate.full_name,
                "company_name": company,
                "recruiter_name": actor.full_name,
                "recruiter_email": actor.email,
                "job_title": job.title if job else "cơ hội tuyển dụng",
            }
            if job:
                context["hiring_unit_name"] = session.get_one(HiringUnit, job.hiring_unit_id).name
            rendered = render_email(template.subject, template.body, context)
        except (AppError, ValidationError):
            session.commit()
            return
        application_id = (
            session.scalar(
                select(Application.id).where(
                    Application.candidate_id == candidate.id,
                    Application.job_id == cv_file.job_id,
                    Application.deleted_at.is_(None),
                )
            )
            if job
            else None
        )
        row = EmailMessage(
            id=file_id,
            application_id=application_id,
            template_id=template.id,
            to_email=recipient,
            subject=rendered.subject,
            body_html=rendered.body_html,
            created_by=actor.id,
            status=EmailStatus.queued,
            scheduled_for=datetime.now(UTC),
            message_id=make_msgid(domain="hr-ats.invalid"),
        )
        session.add(row)
    session.commit()
    if row.status != EmailStatus.queued or row.scheduled_for is None:
        return
    from app.workers.email import send_email_message

    try:
        send_email_message.apply_async(
            args=[str(row.id), row.message_id, row.scheduled_for.isoformat()]
        )
    except Exception:
        # Still queued; the next poll recovers the commit/publish gap.
        session.rollback()


def recover_intake(session: Session, settings: Settings) -> None:
    ids = list(
        session.scalars(
            select(CvFile.id)
            .where(
                CvFile.source == CandidateSource.email,
                CvFile.deleted_at.is_(None),
                CvFile.status == ProcessingStatus.pending,
            )
            .order_by(CvFile.created_at)
            .limit(100)
        )
    )
    session.commit()
    for file_id in ids:
        try:
            process_cv_file.delay(str(file_id))
        except Exception:
            session.rollback()
    done = list(
        session.scalars(
            select(CvFile.id).where(
                CvFile.source == CandidateSource.email,
                CvFile.deleted_at.is_(None),
                CvFile.status == ProcessingStatus.done,
                ~select(EmailMessage.id)
                .where(EmailMessage.id == CvFile.id, EmailMessage.status != EmailStatus.queued)
                .exists(),
            )
        )
    )
    session.commit()
    for file_id in done:
        try:
            queue_receipt(session, file_id, settings)
        except Exception:
            session.rollback()


def _status(settings: Settings, error: str) -> None:
    try:
        with Redis.from_url(
            settings.redis_url, decode_responses=True, socket_connect_timeout=3, socket_timeout=3
        ) as client:
            client.hset(
                STATUS_KEY,
                mapping={
                    "last_read_at": datetime.now(UTC).isoformat(),
                    "last_error": error,
                },
            )
    except Exception:
        pass


@celery_app.task(name="poll_inbox")
def poll_inbox() -> None:
    settings = get_settings()
    if not settings.imap_enabled:
        return
    if not all((settings.imap_host, settings.imap_user, settings.imap_password.get_secret_value())):
        _status(settings, "IMAP_NOT_CONFIGURED")
        return
    error = ""
    try:
        with imaplib.IMAP4_SSL(
            settings.imap_host, ssl_context=ssl.create_default_context(), timeout=15
        ) as mailbox:
            if (
                mailbox.login(settings.imap_user, settings.imap_password.get_secret_value())[0]
                != "OK"
            ):
                raise ValueError("IMAP login failed")
            folder = '"' + settings.imap_folder.replace("\\", "\\\\").replace('"', '\\"') + '"'
            if mailbox.select(folder)[0] != "OK":
                raise ValueError("IMAP folder unavailable")
            result, data = mailbox.uid("search", "UNSEEN")
            if result != "OK":
                raise ValueError("IMAP search failed")
            with worker_session() as session:
                for raw_uid in (data[0] or b"").split()[:MAX_MESSAGES_PER_POLL]:
                    try:
                        uid = raw_uid.decode("ascii")
                        result, size_data = mailbox.uid("fetch", uid, "(RFC822.SIZE)")
                        size_match = re.search(
                            rb"RFC822.SIZE (\d+)",
                            b" ".join(item for item in size_data if isinstance(item, bytes)),
                        )
                        if (
                            result != "OK"
                            or not size_match
                            or int(size_match[1]) > MAX_MESSAGE_BYTES
                        ):
                            error = "IMAP_MESSAGE_TOO_LARGE"
                            continue
                        result, payload = mailbox.uid("fetch", uid, "(BODY.PEEK[])")
                        raw = next((item[1] for item in payload if isinstance(item, tuple)), None)
                        if (
                            result != "OK"
                            or not isinstance(raw, bytes)
                            or len(raw) > MAX_MESSAGE_BYTES
                        ):
                            raise ValueError("IMAP fetch failed")
                        ingest_message(session, raw, settings)
                        if mailbox.uid("store", uid, "+FLAGS", "(\\Seen)")[0] != "OK":
                            raise ValueError("IMAP flags failed")
                    except Exception:
                        session.rollback()
                        error = "IMAP_READ_FAILED"
    except Exception:
        error = "IMAP_READ_FAILED"
    # Also recover an earlier crash/publish failure, including when the inbox is empty.
    try:
        with worker_session() as session:
            recover_intake(session, settings)
    except Exception:
        error = "IMAP_READ_FAILED"
    _status(settings, error)

"""Fixed per-file workflow. Exceptions and document content never enter logs."""

from calendar import monthrange
from contextlib import contextmanager
from datetime import UTC, date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.extract import ExtractionError, extract_text
from app.ai.llm import get_llm_client
from app.ai.parse import parse_cv
from app.ai.redact import redact_contacts
from app.ai.score import score_cv
from app.ai.scoring_rules import ScoringRules, compute_score
from app.core.config import get_settings
from app.core.db import get_engine
from app.core.errors import AppError
from app.models.applications import Application
from app.models.candidates import Candidate, CvFile
from app.models.enums import ActivityType, ProcessingStatus
from app.models.jobs import Job
from app.services.activity import log_activity
from app.services.applications import (
    application_for_update,
    dispatch_score,
    eligible_candidate,
    ensure_application,
    reset_score,
)
from app.services.dedupe import IdentityConflict, possible_duplicate, save_candidate
from app.services.embeddings import embed_candidate
from app.storage import build_storage
from app.workers.celery_app import celery_app


@contextmanager
def worker_session():
    with Session(get_engine(get_settings().database_url)) as session:
        yield session


def retention_date(today: date, months: int) -> date:
    """Add calendar months, clamping the day at the end of the target month."""
    year, month = divmod(today.year * 12 + today.month - 1 + months, 12)
    month += 1
    return date(year, month, min(today.day, monthrange(year, month)[1]))


def anonymize_and_embed(session: Session, candidate: Candidate, text: str) -> None:
    """Save only local anonymization output as the candidate vector's source."""
    embed_candidate(candidate, text)
    session.flush()


def create_and_score_application(
    session: Session, candidate: Candidate, cv_file: CvFile
) -> UUID | None:
    """Return an ID to dispatch only after the file/candidate/application commit."""
    if cv_file.job_id is None:
        return None
    job = session.get_one(Job, cv_file.job_id)
    application, created = ensure_application(session, candidate, job)
    if not created:
        reset_score(application)
    session.flush()
    return application.id


@celery_app.task(name="process_cv_file")
def process_cv_file(cv_file_id: str) -> None:
    application_id: UUID | None = None
    try:
        file_id = UUID(cv_file_id)
    except (ValueError, TypeError, AttributeError):
        return
    with worker_session() as session:
        # Keep the row lock through the entire transaction. Duplicate deliveries
        # wait, then see done/failed. A process crash rolls back to pending.
        cv_file = session.scalar(
            select(CvFile)
            .where(CvFile.id == file_id, CvFile.deleted_at.is_(None))
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if cv_file is None or cv_file.status not in {
            ProcessingStatus.pending,
            ProcessingStatus.running,
        }:
            return
        if cv_file.candidate_id is not None:
            # Match freeze/merge lock order before locking the known identity.
            session.execute(select(func.pg_advisory_xact_lock(0x4356, 10)))
            try:
                eligible_candidate(session, cv_file.candidate_id, lock=True)
            except AppError:
                # A delayed delivery must not rewrite even the erased error field.
                return
        error = "Không thể đọc tệp CV đã lưu. Vui lòng thử lại."
        try:
            # Roll back every partial candidate/file change on failure, while
            # retaining the outer lock so failed can still be saved atomically.
            with session.begin_nested():
                cv_file.status = ProcessingStatus.running
                cv_file.error = None
                session.flush()
                if cv_file.storage_key is None:
                    raise ValueError("File erased")
                settings = get_settings()
                data = build_storage(settings).get(cv_file.storage_key)
                error = "Không đọc được nội dung CV"
                extracted = extract_text(data, cv_file.mime_type)
                cv_file.extracted_text = extracted.text
                cv_file.extraction_method = extracted.method
                cv_file.page_count = extracted.page_count
                error = "Không thể che thông tin liên hệ trong CV."
                text, emails, phones = redact_contacts(extracted.text)
                error = "Không thể phân tích CV. Vui lòng thử lại."
                result = parse_cv(text, client=get_llm_client(settings))
                cv_file.parsed_json = result.parsed.model_dump(mode="json")
                cv_file.parse_model = result.model
                cv_file.parse_prompt_version = result.prompt_version
                error = "Không thể lưu thông tin ứng viên. Vui lòng kiểm tra CV."
                candidate = save_candidate(
                    session,
                    parsed=result.parsed,
                    emails=emails,
                    phones=phones,
                    retention_until=retention_date(
                        datetime.now(ZoneInfo(settings.tz)).date(), settings.data_retention_months
                    ),
                    source=cv_file.source,
                )
                cv_file.candidate_id = candidate.id
                error = "Không thể hoàn tất xử lý hồ sơ ứng viên. Vui lòng thử lại."
                anonymize_and_embed(session, candidate, text)
                if not emails and not phones:
                    duplicate_id = possible_duplicate(
                        session,
                        full_name=result.parsed.full_name,
                        embedding=candidate.embedding,
                        exclude_id=candidate.id,
                    )
                    if duplicate_id is not None:
                        cv_file.parsed_json = {
                            **cv_file.parsed_json,
                            "possible_duplicate_of": str(duplicate_id),
                        }
                application_id = create_and_score_application(session, candidate, cv_file)
                cv_file.status = ProcessingStatus.done
                cv_file.error = None
                session.flush()
        except ExtractionError as exc:
            # ExtractionError is produced locally with fixed Vietnamese messages.
            cv_file.status = ProcessingStatus.failed
            cv_file.error = exc.message
        except IdentityConflict as exc:
            cv_file.status = ProcessingStatus.failed
            cv_file.error = exc.message
        except Exception:
            # Never persist exception text: provider/DB errors can include PII.
            cv_file.status = ProcessingStatus.failed
            cv_file.error = error
        session.commit()
        if cv_file.status == ProcessingStatus.done and application_id is not None:
            dispatch_score(session, application_id)
        if cv_file.status == ProcessingStatus.done:
            from app.email.inbound import queue_receipt

            try:
                queue_receipt(session, cv_file.id, get_settings())
            except Exception:
                # Email failure must not undo a successfully parsed CV.
                session.rollback()


@celery_app.task(name="score_application")
def score_application(application_id: str) -> None:
    try:
        record_id = UUID(application_id)
    except (ValueError, TypeError, AttributeError):
        return
    with worker_session() as session:
        application = application_for_update(session, record_id)
        if application is None or application.ai_status not in {
            ProcessingStatus.pending,
            ProcessingStatus.running,
        }:
            return
        try:
            eligible_candidate(session, application.candidate_id)
        except AppError:
            candidate = session.get(Candidate, application.candidate_id)
            if candidate is None or candidate.purge_pending_at is None:
                # Keep T12's failed-state contract for ordinary expired/merged
                # records, while never rewriting erased fields on a purge.
                reset_score(application)
                application.ai_status = ProcessingStatus.failed
                session.commit()
            return
        try:
            with session.begin_nested():
                application.ai_status = ProcessingStatus.running
                candidate = eligible_candidate(session, application.candidate_id)
                job = session.get_one(Job, application.job_id)
                # Missing anonymized data must never trigger a raw CV fallback.
                if not candidate.anonymized_text:
                    raise ValueError("Missing anonymized text")
                settings = get_settings()
                result = score_cv(
                    candidate.anonymized_text,
                    job_title=job.title,
                    job_description=job.description,
                    must_have=job.must_have,
                    nice_to_have=job.nice_to_have,
                    client=get_llm_client(settings),
                )
                computed = compute_score(
                    result.judged.criteria,
                    candidate.anonymized_text,
                    rules=ScoringRules(
                        must_weight=settings.score_must_weight,
                        partial_value=settings.score_partial_value,
                        high_threshold=settings.score_high_threshold,
                        unknown_threshold=settings.score_unknown_threshold,
                        min_text_length=settings.score_min_text_length,
                    ),
                )
                application.ai_score = computed.score
                application.ai_level = computed.level
                application.ai_criteria = [c.model_dump() for c in result.judged.criteria]
                application.ai_reasons = result.judged.reasons
                application.ai_flags = list(result.judged.flags)
                application.ai_model = result.model
                application.ai_prompt_version = result.prompt_version
                application.ai_scored_at = datetime.now(UTC)
                application.ai_status = ProcessingStatus.done
                log_activity(
                    session,
                    type=ActivityType.ai_scored,
                    job_id=job.id,
                    application_id=application.id,
                    candidate_id=candidate.id,
                    payload={"ai_level": computed.level.value, "ai_score": computed.score},
                )
        except Exception:
            # Roll back partial score/activity; no provider/CV exception text is stored.
            reset_score(application)
            application.ai_status = ProcessingStatus.failed
        session.commit()


@celery_app.task(name="rescore_job")
def rescore_job(job_id: str) -> None:
    try:
        record_id = UUID(job_id)
    except (ValueError, TypeError, AttributeError):
        return
    with worker_session() as session:
        if session.get(Job, record_id) is None:
            return
        ids = list(
            session.scalars(
                select(Application.id)
                .where(Application.job_id == record_id, Application.deleted_at.is_(None))
                .order_by(Application.id)
            )
        )
    # One transaction per application: one failure cannot abort the other scores.
    for application_id in ids:
        with worker_session() as session:
            application = application_for_update(session, application_id)
            if application is None:
                continue
            try:
                eligible_candidate(session, application.candidate_id)
            except AppError:
                continue
            reset_score(application)
            session.commit()
            dispatch_score(session, application_id)

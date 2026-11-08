"""Fixed per-file workflow. Exceptions and document content never enter logs."""

from calendar import monthrange
from contextlib import contextmanager
from datetime import date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.extract import ExtractionError, extract_text
from app.ai.llm import get_llm_client
from app.ai.parse import parse_cv
from app.ai.redact import redact_contacts
from app.core.config import get_settings
from app.core.db import get_engine
from app.models.candidates import Candidate, CvFile
from app.models.enums import ProcessingStatus
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


def create_and_score_application(session: Session, candidate: Candidate, cv_file: CvFile) -> None:
    """T12 hook: create an application for cv_file.job_id and enqueue scoring."""


@celery_app.task(name="process_cv_file")
def process_cv_file(cv_file_id: str) -> None:
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
        error = "Không thể đọc tệp CV đã lưu. Vui lòng thử lại."
        try:
            # Roll back every partial candidate/file change on failure, while
            # retaining the outer lock so failed can still be saved atomically.
            with session.begin_nested():
                cv_file.status = ProcessingStatus.running
                cv_file.error = None
                session.flush()
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
                create_and_score_application(session, candidate, cv_file)
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

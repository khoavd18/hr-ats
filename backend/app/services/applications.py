"""Application creation and explicit rescoring; publish strictly after commit."""

from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.permissions import authorize
from app.models.applications import Application
from app.models.candidates import Candidate
from app.models.enums import ApplicationStage, ProcessingStatus
from app.models.jobs import Job
from app.models.users import User
from app.schemas.core import ApplicationRead


def eligible_candidate(session: Session, candidate_id: UUID, *, lock: bool = False) -> Candidate:
    query = select(Candidate).where(Candidate.id == candidate_id)
    if lock:
        query = query.with_for_update()
    candidate = session.scalar(query.execution_options(populate_existing=True))
    today = datetime.now(ZoneInfo(get_settings().tz)).date()
    if (
        candidate is None
        or candidate.deleted_at is not None
        or candidate.merged_into_id is not None
        or candidate.retention_until < today
    ):
        raise AppError("NOT_FOUND", "Không tìm thấy ứng viên.", 404)
    return candidate


def accessible_job(session: Session, actor: User, job_id: UUID) -> Job:
    job = session.get(Job, job_id)
    if job is None:
        raise AppError("NOT_FOUND", "Không tìm thấy vị trí tuyển dụng.", 404)
    authorize(actor, "jobs.view", job, session=session)
    return job


def ensure_application(
    session: Session, candidate: Candidate, job: Job
) -> tuple[Application, bool]:
    # Serialize bank creation with a human merge; recheck eligibility after waiting.
    session.scalar(
        select(Candidate)
        .where(Candidate.id == candidate.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    eligible_candidate(session, candidate.id)
    # PostgreSQL's partial unique index handles concurrent bank/pipeline inserts.
    application_id = session.scalar(
        insert(Application)
        .values(
            candidate_id=candidate.id,
            job_id=job.id,
            owner_id=job.owner_id,
            stage=ApplicationStage.new,
            ai_status=ProcessingStatus.pending,
        )
        .on_conflict_do_nothing(
            index_elements=[Application.candidate_id, Application.job_id],
            index_where=Application.deleted_at.is_(None),
        )
        .returning(Application.id)
    )
    if application_id is not None:
        return session.get_one(Application, application_id), True
    return session.scalars(
        select(Application)
        .where(
            Application.candidate_id == candidate.id,
            Application.job_id == job.id,
            Application.deleted_at.is_(None),
        )
        .with_for_update()
    ).one(), False


def reset_score(application: Application) -> None:
    application.ai_status = ProcessingStatus.pending
    application.ai_level = None
    application.ai_score = None
    application.ai_criteria = []
    application.ai_reasons = []
    application.ai_flags = []
    application.ai_model = None
    application.ai_prompt_version = None
    application.ai_scored_at = None


def dispatch_score(session: Session, application_id: UUID) -> bool:
    from app.workers.tasks import score_application

    try:
        score_application.delay(str(application_id))
    except Exception:
        # Do not overwrite success if an eager worker completed before dispatch raised.
        session.execute(
            update(Application)
            .where(
                Application.id == application_id, Application.ai_status == ProcessingStatus.pending
            )
            .values(ai_status=ProcessingStatus.failed)
        )
        session.commit()
        return False
    return True


def create_application(
    session: Session, actor: User, *, candidate_id: UUID, job_id: UUID
) -> ApplicationRead:
    job = accessible_job(session, actor, job_id)
    authorize(actor, "cv_bank.search")
    candidate = eligible_candidate(session, candidate_id)
    application, created = ensure_application(session, candidate, job)
    if not created:
        raise AppError("APPLICATION_EXISTS", "Ứng viên đã có trong vị trí tuyển dụng này.", 409)
    snapshot = ApplicationRead.model_validate(application)
    session.commit()
    if not dispatch_score(session, snapshot.id):
        session.refresh(application)
        return ApplicationRead.model_validate(application)
    return snapshot


def rescore_application(session: Session, actor: User, application_id: UUID) -> ApplicationRead:
    application = session.scalar(
        select(Application)
        .where(Application.id == application_id, Application.deleted_at.is_(None))
        .with_for_update()
    )
    if application is None:
        raise AppError("NOT_FOUND", "Không tìm thấy hồ sơ ứng tuyển.", 404)
    accessible_job(session, actor, application.job_id)
    eligible_candidate(session, application.candidate_id, lock=True)
    reset_score(application)
    session.flush()
    snapshot = ApplicationRead.model_validate(application)
    session.commit()
    if not dispatch_score(session, application.id):
        raise AppError(
            "AI_QUEUE_UNAVAILABLE", "Không thể xếp hàng chấm hồ sơ. Vui lòng thử lại.", 503
        )
    return snapshot


def rescore_job(session: Session, actor: User, job_id: UUID) -> None:
    from app.workers.tasks import rescore_job as task

    accessible_job(session, actor, job_id)
    session.commit()
    try:
        task.delay(str(job_id))
    except Exception:
        raise AppError(
            "AI_QUEUE_UNAVAILABLE", "Không thể xếp hàng chấm hồ sơ. Vui lòng thử lại.", 503
        ) from None

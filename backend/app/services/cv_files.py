import logging
from pathlib import PurePosixPath
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.permissions import authorize
from app.models.activity import AuditLog
from app.models.candidates import Candidate, CvFile
from app.models.enums import ActivityType, ProcessingStatus
from app.models.jobs import Job
from app.models.users import User
from app.schemas.core import CvFileRead
from app.schemas.cv_files import CvUploadResult
from app.services.activity import log_activity
from app.services.cv_validation import validate_file
from app.storage import Storage, StorageError
from app.workers.tasks import process_cv_file

logger = logging.getLogger(__name__)
QUEUE_ERROR = "Không thể xếp hàng xử lý. Vui lòng tải lại tệp."


def check_upload_scope(session: Session, actor: User, job_id: UUID | None) -> None:
    authorize(actor, "cv_files.upload")
    if job_id is not None:
        job = session.get(Job, job_id)
        if job is None:
            raise AppError("NOT_FOUND", "Không tìm thấy vị trí tuyển dụng.", 404)
        authorize(actor, "jobs.view", job, session=session)


def _readable_file(session: Session, actor: User, cv_file: CvFile) -> CvFile:
    if cv_file.deleted_at is not None or (
        cv_file.candidate_id is not None
        and session.scalar(
            select(Candidate.id).where(
                Candidate.id == cv_file.candidate_id, Candidate.deleted_at.is_(None)
            )
        )
        is None
    ):
        raise AppError("NOT_FOUND", "Không tìm thấy tệp CV.", 404)
    authorize(actor, "cv_files.view", cv_file, session=session)
    return cv_file


def upload_file(
    session: Session,
    actor: User,
    storage: Storage,
    *,
    data: bytes,
    filename: str,
    job_id: UUID | None,
    index: int,
) -> CvUploadResult:
    check_upload_scope(session, actor, job_id)
    filename = PurePosixPath(filename.replace("\\", "/")).name
    filename = "".join(character for character in filename if character.isprintable()).strip()
    mime, digest = validate_file(data, filename)
    # Serialize equal hashes across users/processes before writing to storage.
    lock_id = int.from_bytes(bytes.fromhex(digest)[:8], "big", signed=True)
    session.execute(select(func.pg_advisory_xact_lock(lock_id)))
    existing = session.scalar(select(CvFile).where(CvFile.sha256 == digest))
    duplicate = existing is not None
    key = None
    if existing is not None:
        cv_file = _readable_file(session, actor, existing)
        retry_publish = cv_file.status == ProcessingStatus.failed and cv_file.error == QUEUE_ERROR
        if not retry_publish:
            result = CvUploadResult(
                index=index, cv_file=CvFileRead.model_validate(cv_file), duplicate=True
            )
            session.commit()
            return result
        cv_file.status = ProcessingStatus.pending
        cv_file.error = None
    else:
        try:
            key = storage.put(data, mime)
        except StorageError:
            raise AppError(
                "STORAGE_UNAVAILABLE", "Không thể lưu tệp. Vui lòng thử lại.", 503
            ) from None
        cv_file = CvFile(
            storage_key=key,
            original_filename=filename[:255] or "cv",
            mime_type=mime,
            size_bytes=len(data),
            sha256=digest,
            uploaded_by=actor.id,
            job_id=job_id,
            status=ProcessingStatus.pending,
        )
        session.add(cv_file)
    try:
        session.flush()
        if not duplicate:
            log_activity(
                session,
                type=ActivityType.cv_uploaded,
                actor_id=actor.id,
                job_id=job_id,
                payload={"cv_file_id": str(cv_file.id)},
            )
        snapshot = CvFileRead.model_validate(cv_file)
        session.commit()
    except Exception:
        session.rollback()
        if key is not None:
            try:
                storage.delete(key)
            except StorageError:
                logger.error("Upload cleanup failed")
        raise
    # Publish only after commit: a worker on another connection must see the row.
    try:
        process_cv_file.delay(str(snapshot.id))
    except Exception:
        logger.error("CV queue dispatch failed", extra={"cv_file_id": str(snapshot.id)})
        session.execute(
            update(CvFile)
            .where(
                CvFile.id == snapshot.id,
                CvFile.status == ProcessingStatus.pending,
                CvFile.deleted_at.is_(None),
            )
            .values(status=ProcessingStatus.failed, error=QUEUE_ERROR)
        )
        session.commit()
        session.refresh(cv_file)
        snapshot = CvFileRead.model_validate(cv_file)
    return CvUploadResult(index=index, cv_file=snapshot, duplicate=duplicate)


def get_file(session: Session, actor: User, cv_file_id: UUID) -> CvFile:
    cv_file = session.get(CvFile, cv_file_id)
    if cv_file is None:
        raise AppError("NOT_FOUND", "Không tìm thấy tệp CV.", 404)
    return _readable_file(session, actor, cv_file)


def record_access(
    session: Session, actor: User, cv_file: CvFile, action: str, ip: str | None
) -> None:
    session.add(
        AuditLog(actor_id=actor.id, action=action, entity="cv_file", entity_id=cv_file.id, ip=ip)
    )
    session.commit()


def download_file(
    session: Session, actor: User, storage: Storage, cv_file_id: UUID, ip: str | None
) -> tuple[CvFileRead, bytes]:
    cv_file = get_file(session, actor, cv_file_id)
    try:
        data = storage.get(cv_file.storage_key)
    except StorageError:
        raise AppError("STORAGE_UNAVAILABLE", "Không thể tải tệp. Vui lòng thử lại.", 503) from None
    snapshot = CvFileRead.model_validate(cv_file)
    record_access(session, actor, cv_file, "download", ip)
    return snapshot, data

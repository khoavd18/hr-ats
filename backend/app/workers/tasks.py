from contextlib import contextmanager
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_engine
from app.models.candidates import CvFile
from app.models.enums import ProcessingStatus
from app.workers.celery_app import celery_app


@contextmanager
def worker_session():
    with Session(get_engine(get_settings().database_url)) as session:
        yield session


@celery_app.task(name="process_cv_file")
def process_cv_file(cv_file_id: str) -> None:
    """T07 placeholder; T10 replaces this with the fixed CV processing pipeline."""
    with worker_session() as session:
        cv_file = session.scalar(
            select(CvFile)
            .where(CvFile.id == UUID(cv_file_id), CvFile.deleted_at.is_(None))
            .with_for_update()
        )
        if cv_file is None or cv_file.status != ProcessingStatus.pending:
            return
        cv_file.status = ProcessingStatus.done
        cv_file.error = None
        session.commit()

"""Daily erasure on the default queue, with no candidate contents in messages."""

from app.core.config import get_settings
from app.services.privacy import enforce_retention as run_retention
from app.storage import build_storage
from app.workers.celery_app import celery_app
from app.workers.tasks import worker_session


@celery_app.task(name="enforce_retention")
def enforce_retention() -> None:
    with worker_session() as session:
        run_retention(session, build_storage(get_settings()))

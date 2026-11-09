"""Fixed schedules enqueue persisted report snapshots through the shared sender."""

from datetime import UTC, datetime

from app.core.config import get_settings
from app.reports.scheduled import ReportKind, queue_reports
from app.workers.celery_app import celery_app
from app.workers.email import send_email_message
from app.workers.tasks import worker_session


def generate_report(kind: ReportKind) -> int:
    with worker_session() as session:
        messages = queue_reports(session, kind, datetime.now(UTC), get_settings())
    published = 0
    for args in messages:
        try:
            send_email_message.apply_async(args=list(args))
            published += 1
        except Exception:
            # Never log broker exceptions, addresses or report bodies. Re-running
            # this period recovers committed queued rows with the same checkpoint.
            continue
    return published


@celery_app.task(name="generate_daily_report")
def generate_daily_report() -> None:
    generate_report("daily")


@celery_app.task(name="generate_weekly_report")
def generate_weekly_report() -> None:
    generate_report("weekly")

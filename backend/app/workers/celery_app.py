from celery import Celery
from celery.signals import setup_logging
from kombu import Queue

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging


def create_celery_app(settings: Settings) -> Celery:
    testing = settings.app_env == "test"
    application = Celery(
        "hr_ats",
        broker="memory://" if testing else settings.redis_url,
        backend="cache+memory://" if testing else settings.redis_url,
        include=["app.workers.tasks"],
    )
    application.conf.update(
        task_queues=tuple(
            Queue(name, exchange=name, routing_key=name) for name in ("ai", "email", "default")
        ),
        task_default_queue="default",
        task_create_missing_queues=False,
        task_routes={
            **{
                name: {"queue": "ai"}
                for name in ("process_cv_file", "score_application", "rescore_job")
            },
            **{name: {"queue": "email"} for name in ("send_email_message", "poll_inbox")},
        },
        task_always_eager=testing,
        task_eager_propagates=testing,
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        task_ignore_result=True,
        task_publish_retry=False,
        broker_connection_timeout=3,
        broker_transport_options={"socket_connect_timeout": 3, "socket_timeout": 3},
        worker_hijack_root_logger=False,
        timezone="UTC",
        enable_utc=True,
    )
    return application


@setup_logging.connect
def configure_worker_logging(**kwargs) -> None:
    configure_logging()


celery_app = create_celery_app(get_settings())

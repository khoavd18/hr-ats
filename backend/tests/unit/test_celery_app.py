from app.core.config import Settings
from app.workers.celery_app import celery_app, create_celery_app


def test_ai_message_is_delivered_only_to_ai_queue():
    application = create_celery_app(Settings(_env_file=None, app_env="dev"))
    application.conf.update(broker_url="memory://", result_backend="cache+memory://")
    try:
        with application.connection_for_write() as connection:
            queues = {queue.name: queue.bind(connection) for queue in application.conf.task_queues}
            for queue in queues.values():
                queue.declare()
            with application.amqp.Producer(connection) as producer:
                application.send_task("process_cv_file", args=["synthetic-id"], producer=producer)
            message = queues["ai"].get()
            assert message is not None and message.headers["task"] == "process_cv_file"
            message.ack()
            assert queues["email"].get() is None
            assert queues["default"].get() is None
    finally:
        application.close()
        celery_app.set_current()


def test_test_environment_is_eager_in_memory_and_json_only():
    application = create_celery_app(Settings(_env_file=None, app_env="test"))
    assert application.conf.task_always_eager and application.conf.task_eager_propagates
    assert application.conf.broker_url == "memory://"
    assert application.conf.result_backend == "cache+memory://"
    assert application.conf.accept_content == ["json"]
    application.close()
    celery_app.set_current()


def test_dev_routes_three_queues_and_uses_redis():
    settings = Settings(_env_file=None, app_env="dev", redis_url="redis://localhost:6379/15")
    application = create_celery_app(settings)
    assert not application.conf.task_always_eager
    assert application.conf.broker_url == settings.redis_url
    assert {queue.name for queue in application.conf.task_queues} == {"ai", "email", "default"}
    assert application.conf.task_default_queue == "default"
    assert application.conf.task_routes["process_cv_file"] == {"queue": "ai"}
    assert application.conf.task_routes["send_email_message"] == {"queue": "email"}
    assert not application.conf.task_create_missing_queues
    # Distinct bindings prevent AI messages from also arriving in email/default.
    for name, task in (
        ("ai", "process_cv_file"),
        ("email", "send_email_message"),
        ("default", "generate_daily_report"),
    ):
        queue = application.amqp.router.route({}, task)["queue"]
        assert (queue.name, queue.exchange.name, queue.routing_key) == (name, name, name)
    application.close()
    celery_app.set_current()

"""Independent PostgreSQL connections prove commit-before-publish and duplicate guards."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from threading import Barrier
from uuid import UUID

from alembic import command
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Activity, EmailMessage, User
from app.models.enums import ActivityType
from app.models.users import UserRole
from app.schemas.email import MessageCreate
from app.services import email_messages
from app.workers import email
from tests.api.test_pipeline import seed_records
from tests.conftest import migration_config


def test_concurrent_confirmation_publishes_once_after_commit_and_duplicate_workers_send_once(
    empty_engine, monkeypatch, email_outbox
):
    with empty_engine.begin() as connection:
        config = migration_config()
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    with Session(empty_engine) as session:
        actor = User(
            email="concurrent-t23@example.invalid",
            full_name="HR giả T23",
            role=UserRole.admin,
            password_hash="unused-synthetic-hash",
        )
        session.add(actor)
        session.flush()
        records = seed_records(session, actor)
        row = email_messages.create(
            session,
            actor,
            MessageCreate(
                application_id=records.application.id,
                to_email="synthetic-t23@example.invalid",
                subject="Thư giả cạnh tranh",
                body="Nội dung giả",
            ),
        )
        actor_id, message_id = actor.id, row.id
    published = []

    def publish(*, args):
        with Session(empty_engine) as observer:
            row = observer.get_one(EmailMessage, UUID(args[0]))
            assert row.status == "queued" and row.message_id == args[1]
        published.append(args)

    monkeypatch.setattr(email.send_email_message, "apply_async", publish)
    barrier = Barrier(2)

    def confirm(_):
        with Session(empty_engine) as session:
            actor = session.get_one(User, actor_id)
            assert session.get_one(EmailMessage, message_id).status == "draft"
            barrier.wait(timeout=10)
            return email_messages.send(session, actor, message_id).status

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(confirm, range(2))) == ["queued", "queued"]
    assert len(published) == 1

    @contextmanager
    def worker_session():
        with Session(empty_engine) as session:
            yield session

    monkeypatch.setattr(email, "worker_session", worker_session)
    barrier = Barrier(2)

    def deliver(_):
        barrier.wait(timeout=10)
        email.send_email_message.run(*published[0])

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(deliver, range(2)))
    assert len(email_outbox) == 1
    with Session(empty_engine) as session:
        assert session.get_one(EmailMessage, message_id).status == "sent"
        assert (
            session.scalar(
                select(func.count())
                .select_from(Activity)
                .where(Activity.type == ActivityType.email_sent)
            )
            == 1
        )

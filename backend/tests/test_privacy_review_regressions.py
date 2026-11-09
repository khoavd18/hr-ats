"""T29 review: synthetic identities and overlapping real PostgreSQL transactions."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, date, datetime
from queue import Queue
from threading import Event
from time import monotonic, sleep
from types import SimpleNamespace

import pytest
from alembic import command
from sqlalchemy import event, func, select, text
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import (
    Application,
    AuditLog,
    Candidate,
    DataRequest,
    EmailMessage,
    HiringUnit,
    Job,
    Task,
    User,
)
from app.models.enums import ApplicationStage, ProcessingStatus
from app.schemas.privacy import DataRequestInput
from app.services import applications, cv_bank, pipeline, privacy
from app.storage import LocalStorage
from app.workers import reminders, tasks
from tests.conftest import migration_config


@pytest.fixture
def records(empty_engine):
    with empty_engine.begin() as connection:
        config = migration_config()
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    with Session(empty_engine) as session:
        actor = User(
            email="privacy-review@example.invalid",
            full_name="HR giả T29",
            role="admin",
            password_hash="unused-synthetic-hash",
        )
        unit = HiringUnit(name="Đơn vị giả T29", kind="department")
        source = Candidate(full_name="Nguồn giả T29", retention_until=date(2099, 1, 1))
        target = Candidate(full_name="Đích giả T29", retention_until=date(2099, 1, 1))
        for candidate in (source, target):
            candidate.anonymized_text = "Kỹ năng Python và kiểm thử phần mềm. " * 20
        session.add_all([actor, unit, source, target])
        session.flush()
        job = Job(
            title="Vị trí giả T29", description="Python", hiring_unit_id=unit.id, owner_id=actor.id
        )
        session.add(job)
        session.flush()
        application = Application(candidate_id=source.id, job_id=job.id, owner_id=actor.id)
        session.add(application)
        session.flush()
        session.add(
            Task(
                title="Nhắc việc cho Nguồn giả T29",
                application_id=application.id,
                job_id=job.id,
                assignee_id=actor.id,
                created_by=actor.id,
                due_at=datetime.now(UTC),
            )
        )
        session.commit()
        return SimpleNamespace(
            engine=empty_engine,
            actor=actor.id,
            source=source.id,
            target=target.id,
            application=application.id,
            job=job.id,
        )


def wait_for_block_or_completion(engine, pid, future):
    """Wait for an observed database dependency, never infer ordering from a sleep."""
    deadline = monotonic() + 10
    with engine.connect() as connection:
        while monotonic() < deadline:
            if future.done():
                future.result()
                return
            if connection.scalar(select(func.cardinality(func.pg_blocking_pids(pid)))):
                return
            sleep(0.01)
    raise AssertionError("Transaction neither blocked nor completed")


def test_reminder_snapshot_cannot_survive_concurrent_purge(records, tmp_path, monkeypatch):
    r = records
    storage = LocalStorage(tmp_path)
    with Session(r.engine) as session:
        request_id = privacy.create_request(
            session,
            session.get_one(User, r.actor),
            DataRequestInput(candidate_id=r.source, requested_by_note="Bằng chứng giả"),
        ).id
    rendered, release = Event(), Event()
    original = reminders.reminder_html

    def pause_after_render(session, actor, now):
        body = original(session, actor, now)
        assert "Nguồn giả T29" in body
        rendered.set()
        assert release.wait(15)
        return body

    monkeypatch.setattr(reminders, "reminder_html", pause_after_render)
    pids = Queue()

    def produce():
        with Session(r.engine) as session:
            return reminders.queue_reminders(session, datetime.now(UTC))

    def purge():
        with Session(r.engine) as session:
            pids.put(session.scalar(select(func.pg_backend_pid())))
            return privacy.execute_request(
                session, session.get_one(User, r.actor), request_id, storage
            ).status

    with ThreadPoolExecutor(max_workers=2) as pool:
        producer = pool.submit(produce)
        try:
            assert rendered.wait(10)
            executor = pool.submit(purge)
            wait_for_block_or_completion(r.engine, pids.get(timeout=10), executor)
        finally:
            release.set()
        producer.result(10)
        assert executor.result(10) == "done"
    with Session(r.engine) as session:
        assert session.get_one(Candidate, r.source).purged_at is not None
        messages = session.scalars(select(EmailMessage)).all()
        assert messages
        assert all(row.body_html is None and row.deleted_at is not None for row in messages)
        assert (
            privacy.execute_request(
                session, session.get_one(User, r.actor), request_id, storage
            ).status
            == "done"
        )
        assert reminders.queue_reminders(session, datetime.now(UTC)) == []


@pytest.mark.parametrize("operation", ["rescore", "stage", "score_worker", "job_worker"])
def test_merge_overlaps_application_writers_without_deadlock(records, monkeypatch, operation):
    r = records
    locked, release = Event(), Event()
    pids = Queue()

    def pause_first_lock(connection, cursor, statement, parameters, context, executemany):
        if connection.info.get("pause_writer") and "FOR UPDATE" in statement:
            connection.info["pause_writer"] = False
            locked.set()
            assert release.wait(15)

    @contextmanager
    def writer_session():
        with Session(r.engine) as session:
            connection = session.connection()
            info = connection.info
            info["pause_writer"] = True
            session.execute(text("SET LOCAL statement_timeout = '12s'"))
            try:
                yield session
            finally:
                info.pop("pause_writer", None)

    monkeypatch.setattr(tasks, "worker_session", writer_session)
    monkeypatch.setattr(tasks.score_application, "delay", lambda *args: None)
    event.listen(r.engine, "after_cursor_execute", pause_first_lock)

    def write():
        if operation == "score_worker":
            tasks.score_application.run(str(r.application))
        elif operation == "job_worker":
            tasks.rescore_job.run(str(r.job))
        else:
            with writer_session() as session:
                actor = session.get_one(User, r.actor)
                if operation == "rescore":
                    applications.rescore_application(session, actor, r.application)
                else:
                    pipeline.move(session, actor, r.application, ApplicationStage.screening)

    def merge():
        with Session(r.engine) as session:
            pids.put(session.scalar(select(func.pg_backend_pid())))
            session.execute(text("SET LOCAL statement_timeout = '12s'"))
            return cv_bank.merge(session, session.get_one(User, r.actor), r.source, r.target)

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            writer = pool.submit(write)
            try:
                assert locked.wait(10)
                merger = pool.submit(merge)
                wait_for_block_or_completion(r.engine, pids.get(timeout=10), merger)
            finally:
                release.set()
            writer.result(15)
            assert merger.result(15).id == r.target
    finally:
        event.remove(r.engine, "after_cursor_execute", pause_first_lock)
    with Session(r.engine) as session:
        application = session.get_one(Application, r.application)
        assert application.candidate_id == r.target
        if operation == "stage":
            assert application.stage == ApplicationStage.screening
        else:
            expected = (
                ProcessingStatus.done if operation == "score_worker" else ProcessingStatus.pending
            )
            assert application.ai_status == expected


@pytest.mark.parametrize("request_side", ["source", "target"])
def test_open_deletion_request_prevents_merge_and_can_still_execute(
    records, tmp_path, request_side
):
    r = records
    requested_id = getattr(r, request_side)
    with Session(r.engine) as session:
        actor = session.get_one(User, r.actor)
        request = privacy.create_request(
            session,
            actor,
            DataRequestInput(candidate_id=requested_id, requested_by_note="Bằng chứng giả"),
        )
        with pytest.raises(AppError) as caught:
            cv_bank.merge(session, actor, r.source, r.target)
        assert caught.value.code == "DATA_REQUEST_OPEN"
        assert caught.value.status == 409
        session.rollback()
        assert session.get_one(Candidate, r.source).merged_into_id is None
        assert session.get_one(Application, r.application).candidate_id == r.source
        row = session.get_one(DataRequest, request.id)
        assert row.candidate_id == requested_id and row.status == "open"
        result = privacy.execute_request(session, actor, request.id, LocalStorage(tmp_path))
        assert result.status == "done" and result.candidate_id == requested_id
        assert session.get_one(Candidate, requested_id).full_name is None
        other_id = r.target if request_side == "source" else r.source
        assert session.get_one(Candidate, other_id).full_name is not None
        assert (
            session.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.action == "candidate.purge")
            )
            == 1
        )


@pytest.mark.parametrize("duplicate", [False, True])
def test_rescore_rereads_identity_when_merge_wins_before_candidate_lock(
    records, monkeypatch, duplicate
):
    r = records
    if duplicate:
        with Session(r.engine) as session:
            session.add(Application(candidate_id=r.target, job_id=r.job, owner_id=r.actor))
            session.commit()
    selected, release = Event(), Event()

    def pause_before_candidate_lock(connection, cursor, statement, parameters, context, many):
        if (
            connection.info.get("pause_before_candidate")
            and "FROM candidates" in statement
            and "FOR UPDATE" in statement
        ):
            connection.info["pause_before_candidate"] = False
            selected.set()
            assert release.wait(15)

    monkeypatch.setattr(tasks.score_application, "delay", lambda *args: None)
    event.listen(r.engine, "before_cursor_execute", pause_before_candidate_lock)

    def rescore():
        with Session(r.engine) as session:
            # Stale identity-map entries must also be refreshed after merge.
            stale_application = session.get_one(Application, r.application)
            stale_candidate = session.get_one(Candidate, r.source)
            assert stale_application.candidate_id == stale_candidate.id
            info = session.connection().info
            info["pause_before_candidate"] = True
            try:
                return applications.rescore_application(
                    session, session.get_one(User, r.actor), r.application
                )
            finally:
                info.pop("pause_before_candidate", None)

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            writer = pool.submit(rescore)
            try:
                assert selected.wait(10)
                with Session(r.engine) as session:
                    cv_bank.merge(session, session.get_one(User, r.actor), r.source, r.target)
            finally:
                release.set()
            if duplicate:
                with pytest.raises(AppError, match="Không tìm thấy hồ sơ"):
                    writer.result(10)
            else:
                assert writer.result(10).candidate_id == r.target
    finally:
        event.remove(r.engine, "before_cursor_execute", pause_before_candidate_lock)


@pytest.mark.parametrize("request_side", ["source", "target"])
def test_merge_waits_for_concurrent_request_before_checking_open_requests(records, request_side):
    r = records
    inserted, release = Event(), Event()
    pids = Queue()

    def pause_request(connection, cursor, statement, parameters, context, many):
        if statement.startswith("INSERT INTO data_requests"):
            inserted.set()
            assert release.wait(15)

    def create():
        with Session(r.engine) as session:
            return privacy.create_request(
                session,
                session.get_one(User, r.actor),
                DataRequestInput(candidate_id=getattr(r, request_side), requested_by_note="Giả"),
            )

    def merge():
        with Session(r.engine) as session:
            pids.put(session.scalar(select(func.pg_backend_pid())))
            try:
                cv_bank.merge(session, session.get_one(User, r.actor), r.source, r.target)
            except AppError as error:
                return error.code
            raise AssertionError("Merge ignored an accepted deletion request")

    event.listen(r.engine, "after_cursor_execute", pause_request)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            creator = pool.submit(create)
            try:
                assert inserted.wait(10)
                merger = pool.submit(merge)
                wait_for_block_or_completion(r.engine, pids.get(timeout=10), merger)
            finally:
                release.set()
            assert creator.result(10).status == "open"
            assert merger.result(10) == "DATA_REQUEST_OPEN"
    finally:
        event.remove(r.engine, "after_cursor_execute", pause_request)


def test_frozen_writer_exits_before_waiting_on_purge_child_locks(records, tmp_path, monkeypatch):
    r = records
    with Session(r.engine) as session:
        request_id = privacy.create_request(
            session,
            session.get_one(User, r.actor),
            DataRequestInput(candidate_id=r.source, requested_by_note="Bằng chứng giả"),
        ).id
    erased_child, release = Event(), Event()
    pids = Queue()

    def pause_purge(connection, cursor, statement, parameters, context, many):
        if statement.startswith("UPDATE applications SET"):
            erased_child.set()
            assert release.wait(15)

    def purge():
        with Session(r.engine) as session:
            return privacy.execute_request(
                session, session.get_one(User, r.actor), request_id, LocalStorage(tmp_path)
            ).status

    def rescore():
        with Session(r.engine) as session:
            pids.put(session.scalar(select(func.pg_backend_pid())))
            try:
                applications.rescore_application(
                    session, session.get_one(User, r.actor), r.application
                )
            except AppError as error:
                return error.code
            raise AssertionError("Frozen candidate accepted rescore")

    event.listen(r.engine, "after_cursor_execute", pause_purge)
    monkeypatch.setattr(tasks.score_application, "delay", lambda *args: None)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            executor = pool.submit(purge)
            try:
                assert erased_child.wait(10)
                writer = pool.submit(rescore)
                wait_for_block_or_completion(r.engine, pids.get(timeout=10), writer)
            finally:
                release.set()
            assert executor.result(10) == "done"
            assert writer.result(10) == "NOT_FOUND"
    finally:
        event.remove(r.engine, "after_cursor_execute", pause_purge)
    with Session(r.engine) as session:
        assert session.get_one(Application, r.application).ai_criteria is None
        assert session.get_one(Candidate, r.source).full_name is None

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

from app.core.config import get_settings
from app.core.errors import AppError
from app.email import inbound
from app.models import (
    Application,
    AuditLog,
    Candidate,
    CvFile,
    DataRequest,
    EmailMessage,
    HiringUnit,
    Job,
    Task,
    User,
)
from app.models.enums import ApplicationStage, CandidateSource, ProcessingStatus
from app.schemas.privacy import DataRequestInput
from app.services import applications, cv_bank, pipeline, privacy
from app.storage import LocalStorage
from app.workers import email, reminders, tasks
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


@pytest.fixture
def receipt_records(records, tmp_path, monkeypatch):
    r = records
    r.storage = LocalStorage(tmp_path)
    r.settings = get_settings().model_copy(update={"imap_enabled": True})
    with Session(r.engine) as session:
        session.get_one(Candidate, r.source).email = "receipt-source@example.invalid"
        session.get_one(Candidate, r.target).email = "receipt-target@example.invalid"
        file = CvFile(
            candidate_id=r.source,
            job_id=r.job,
            source=CandidateSource.email,
            status=ProcessingStatus.done,
            storage_key=r.storage.put(b"synthetic receipt CV", "application/pdf"),
            original_filename="synthetic.pdf",
            mime_type="application/pdf",
            size_bytes=20,
            sha256="b" * 64,
        )
        session.add(file)
        session.commit()
        r.file = file.id
    r.published = []
    monkeypatch.setattr(
        email.send_email_message, "apply_async", lambda **kw: r.published.append(kw)
    )
    return r


def test_receipt_overlaps_merge_without_deadlock(receipt_records):
    r = receipt_records
    locked, release = Event(), Event()
    pids = Queue()

    def pause_file_lock(connection, cursor, statement, parameters, context, many):
        if (
            connection.info.get("pause_receipt")
            and "FROM cv_files" in statement
            and "FOR UPDATE" in statement
        ):
            connection.info["pause_receipt"] = False
            locked.set()
            assert release.wait(15)

    def receipt():
        with Session(r.engine) as session:
            info = session.connection().info
            info["pause_receipt"] = True
            session.execute(text("SET LOCAL statement_timeout = '12s'"))
            try:
                inbound.queue_receipt(session, r.file, r.settings)
            finally:
                info.pop("pause_receipt", None)

    def merge():
        with Session(r.engine) as session:
            pids.put(session.scalar(select(func.pg_backend_pid())))
            session.execute(text("SET LOCAL statement_timeout = '12s'"))
            cv_bank.merge(session, session.get_one(User, r.actor), r.source, r.target)

    event.listen(r.engine, "after_cursor_execute", pause_file_lock)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            writer = pool.submit(receipt)
            try:
                assert locked.wait(10)
                merger = pool.submit(merge)
                wait_for_block_or_completion(r.engine, pids.get(timeout=10), merger)
            finally:
                release.set()
            writer.result(10)
            merger.result(10)
    finally:
        event.remove(r.engine, "after_cursor_execute", pause_file_lock)
    with Session(r.engine) as session:
        assert session.get_one(CvFile, r.file).candidate_id == r.target
        assert session.get_one(Candidate, r.source).merged_into_id == r.target
        row = session.get_one(EmailMessage, r.file)
        assert row.to_email == "receipt-source@example.invalid"
        assert row.application_id == r.application and row.status == "queued"
    assert len(r.published) == 1


def test_receipt_rereads_identity_after_waiting_for_merge(receipt_records):
    r = receipt_records
    locked, release = Event(), Event()
    pids = Queue()

    def pause_merge(connection, cursor, statement, parameters, context, many):
        if "FROM candidates" in statement and "FOR UPDATE" in statement:
            locked.set()
            assert release.wait(15)

    def merge():
        with Session(r.engine) as session:
            cv_bank.merge(session, session.get_one(User, r.actor), r.source, r.target)

    # Keep stale objects alive in the receipt session before merge starts.
    with Session(r.engine) as session:
        stale_file = session.get_one(CvFile, r.file)
        stale_source = session.get_one(Candidate, r.source)
        stale_target = session.get_one(Candidate, r.target)
        assert stale_file.candidate_id == stale_source.id != stale_target.id
        session.commit()
        # Commit expires the map; explicitly load it again before the merge.
        assert stale_file.candidate_id == r.source
        assert stale_source.email == "receipt-source@example.invalid"
        assert stale_target.email == "receipt-target@example.invalid"

        def receipt():
            pids.put(session.scalar(select(func.pg_backend_pid())))
            session.execute(text("SET LOCAL statement_timeout = '12s'"))
            inbound.queue_receipt(session, r.file, r.settings)

        event.listen(r.engine, "after_cursor_execute", pause_merge)
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                merger = pool.submit(merge)
                try:
                    assert locked.wait(10)
                    writer = pool.submit(receipt)
                    wait_for_block_or_completion(r.engine, pids.get(timeout=10), writer)
                finally:
                    release.set()
                merger.result(10)
                writer.result(10)
        finally:
            event.remove(r.engine, "after_cursor_execute", pause_merge)
        row = session.get_one(EmailMessage, r.file)
        assert row.to_email == "receipt-target@example.invalid"
        assert "Đích giả T29" in row.body_html
        assert "Nguồn giả T29" not in row.body_html
        assert row.application_id == r.application
        inbound.queue_receipt(session, r.file, r.settings)
        assert session.scalar(select(func.count()).select_from(EmailMessage)) == 1


def test_frozen_receipt_exits_before_purge_file_lock(receipt_records):
    r = receipt_records
    with Session(r.engine) as session:
        request_id = privacy.create_request(
            session,
            session.get_one(User, r.actor),
            DataRequestInput(candidate_id=r.source, requested_by_note="Bằng chứng giả"),
        ).id
    locked, release = Event(), Event()

    def pause_purge(connection, cursor, statement, parameters, context, many):
        if "FROM cv_files" in statement and "FOR UPDATE" in statement:
            locked.set()
            assert release.wait(15)

    def purge():
        with Session(r.engine) as session:
            return privacy.execute_request(
                session, session.get_one(User, r.actor), request_id, r.storage
            ).status

    def receipt():
        with Session(r.engine) as session:
            session.execute(text("SET LOCAL statement_timeout = '5s'"))
            inbound.queue_receipt(session, r.file, r.settings)

    event.listen(r.engine, "after_cursor_execute", pause_purge)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            executor = pool.submit(purge)
            try:
                assert locked.wait(10)
                # A frozen identity must finish while purge still holds the file.
                pool.submit(receipt).result(7)
            finally:
                release.set()
            assert executor.result(10) == "done"
    finally:
        event.remove(r.engine, "after_cursor_execute", pause_purge)
    with Session(r.engine) as session:
        assert session.get_one(Candidate, r.source).purged_at is not None
        assert session.get(EmailMessage, r.file) is None
    assert r.published == []


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


def test_concurrent_authenticated_executions_both_succeed(records, tmp_path, monkeypatch):
    """Same admin, same session, two overlapping execute requests (double click)."""
    from fastapi.testclient import TestClient

    from app.core import security
    from app.core.db import get_session
    from app.main import create_app
    from tests.auth_helpers import PASSWORD, csrf_headers, sign_in

    r = records
    storage = LocalStorage(tmp_path)
    with Session(r.engine) as session:
        actor = session.get_one(User, r.actor)
        actor.password_hash = security.hash_password(PASSWORD)
        session.add(
            CvFile(
                candidate_id=r.source,
                source=CandidateSource.upload,
                status=ProcessingStatus.done,
                storage_key=storage.put(b"synthetic CV only", "application/pdf"),
                original_filename="gia.pdf",
                mime_type="application/pdf",
                size_bytes=17,
                sha256="c" * 64,
            )
        )
        session.commit()
        request_id = privacy.create_request(
            session, actor, DataRequestInput(candidate_id=r.source, requested_by_note="Giả")
        ).id

    entered, release = Event(), Event()

    class PausingStorage(LocalStorage):
        def delete(self, key):
            # Inside the second (purge) phase, after the freeze committed.
            if not entered.is_set():
                entered.set()
                assert release.wait(15)
            super().delete(key)

    monkeypatch.setattr(
        "app.api.privacy.build_storage", lambda settings: PausingStorage(storage.root)
    )
    app = create_app()

    def fresh_session():
        with Session(r.engine) as session:
            yield session

    app.dependency_overrides[get_session] = fresh_session
    with TestClient(app, raise_server_exceptions=False) as first:
        assert sign_in(first, email="privacy-review@example.invalid").status_code == 200
        headers = csrf_headers(first)
        url = f"/api/v1/data-requests/{request_id}/execute"
        with TestClient(app, raise_server_exceptions=False) as second:
            second.cookies.update(first.cookies)
            with ThreadPoolExecutor(max_workers=2) as pool:
                one = pool.submit(first.post, url, headers=headers)
                try:
                    assert entered.wait(10)
                    two = pool.submit(second.post, url, headers=headers)
                    deadline, overlapped = monotonic() + 10, False
                    with r.engine.connect() as probe:
                        while monotonic() < deadline and not two.done():
                            if probe.scalar(
                                text("SELECT count(*) FROM pg_locks WHERE NOT granted")
                            ):
                                overlapped = True
                                break
                            sleep(0.01)
                    # The second request must really wait on the first one.
                    assert overlapped
                finally:
                    release.set()
                statuses = sorted([one.result(20).status_code, two.result(20).status_code])
    assert statuses == [200, 200]
    with Session(r.engine) as session:
        audits = session.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.action == "candidate.purge", AuditLog.entity_id == r.source)
        )
        assert audits == 1
        assert session.get_one(DataRequest, request_id).status == "done"


def test_deletion_waits_for_a_parse_that_is_saving_and_then_erases_it(
    records, tmp_path, monkeypatch
):
    """Worker saves first (identity lock held): the file links, then is purged."""
    from contextlib import contextmanager as _cm

    from app.ai.extract import ExtractResult
    from app.models.enums import ExtractionMethod

    r = records
    storage = LocalStorage(tmp_path)
    contact = "t29-saving@example.invalid"
    text_value = f"Nguồn giả T29\nEmail: {contact}\n" + "Kỹ năng Python giả. " * 30
    with Session(r.engine) as session:
        session.get_one(Candidate, r.source).email = contact
        pending = CvFile(
            candidate_id=None,
            source=CandidateSource.upload,
            status=ProcessingStatus.pending,
            storage_key=storage.put(text_value.encode(), "application/pdf"),
            original_filename="ban-sua.pdf",
            mime_type="application/pdf",
            size_bytes=len(text_value),
            sha256="d" * 64,
        )
        session.add(pending)
        session.commit()
        file_id = pending.id
        request_id = privacy.create_request(
            session,
            session.get_one(User, r.actor),
            DataRequestInput(candidate_id=r.source, requested_by_note="Giả"),
        ).id

    saved, release = Event(), Event()
    original_save = tasks.save_candidate

    def pause_after_save(*args, **kwargs):
        candidate = original_save(*args, **kwargs)
        saved.set()
        assert release.wait(15)
        return candidate

    @_cm
    def worker_session():
        with Session(r.engine) as session:
            yield session

    monkeypatch.setattr(tasks, "save_candidate", pause_after_save)
    monkeypatch.setattr(tasks, "worker_session", worker_session)
    monkeypatch.setattr(tasks, "build_storage", lambda settings: storage)
    monkeypatch.setattr(
        tasks,
        "extract_text",
        lambda data, mime: ExtractResult(text_value, ExtractionMethod.pdf_text, 1),
    )
    monkeypatch.setattr(tasks, "dispatch_score", lambda *args: None)
    pids = Queue()

    def purge():
        with Session(r.engine) as session:
            pids.put(session.scalar(select(func.pg_backend_pid())))
            return privacy.execute_request(
                session, session.get_one(User, r.actor), request_id, storage
            ).status

    with ThreadPoolExecutor(max_workers=2) as pool:
        worker = pool.submit(tasks.process_cv_file, str(file_id))
        try:
            assert saved.wait(10)
            executor = pool.submit(purge)
            wait_for_block_or_completion(r.engine, pids.get(timeout=10), executor)
            assert not executor.done()
        finally:
            release.set()
        worker.result(10)
        assert executor.result(10) == "done"
    with Session(r.engine) as session:
        file = session.get_one(CvFile, file_id)
        assert file.candidate_id == r.source
        assert file.storage_key is None and file.extracted_text is None
        active = session.scalars(
            select(Candidate).where(Candidate.deleted_at.is_(None), Candidate.email == contact)
        ).all()
        assert active == []
        assert not any(path.is_file() for path in storage.root.rglob("*"))

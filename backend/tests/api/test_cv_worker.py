from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import date
from threading import Barrier, Event, Lock
from types import SimpleNamespace

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import REPO_ROOT, get_settings
from app.core.errors import AppError
from app.models import Activity, Application, Candidate, CvFile, HiringUnit, Job, User, UserRole
from app.models.enums import ActivityType, HiringUnitKind, ProcessingStatus
from app.services.applications import create_application
from app.services.cv_bank import merge
from app.services.cv_files import upload_file
from app.storage import LocalStorage
from app.workers import tasks


@pytest.fixture
def committed_runtime(empty_engine, tmp_path, monkeypatch):
    # A dedicated migrated DB allows real commits and an independent worker connection.
    with empty_engine.begin() as connection:
        config = Config(str(REPO_ROOT / "backend/alembic.ini"))
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    settings = get_settings().model_copy(
        update={
            "database_url": empty_engine.url.render_as_string(hide_password=False),
            "storage_local_dir": tmp_path,
        }
    )
    monkeypatch.setattr(tasks, "get_settings", lambda: settings)
    # Reuse the fixture engine so its pool closes before its private DB is removed.
    monkeypatch.setattr(tasks, "get_engine", lambda url: empty_engine)
    with Session(empty_engine) as session:
        actor = User(
            email="worker@example.invalid",
            full_name="Tài khoản worker giả",
            role=UserRole.admin,
            password_hash="unused-synthetic-hash",
        )
        session.add(actor)
        session.commit()
        actor_id = actor.id
    return SimpleNamespace(
        engine=empty_engine, storage=LocalStorage(tmp_path), actor_id=actor_id, root=tmp_path
    )


def test_concurrent_upload_publishes_after_commit_and_worker_uses_own_connection(committed_runtime):
    empty_engine = committed_runtime.engine
    storage = committed_runtime.storage
    actor_id = committed_runtime.actor_id
    barrier = Barrier(2)

    def upload_once(index):
        with Session(empty_engine) as session:
            actor = session.get(User, actor_id)
            barrier.wait(timeout=10)
            return upload_file(
                session,
                actor,
                storage,
                data=(REPO_ROOT / "data/sample_cvs/cv_0001.pdf").read_bytes(),
                filename="synthetic.pdf",
                job_id=None,
                index=index,
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(upload_once, range(2)))
    assert sorted(result.duplicate for result in results) == [False, True]
    assert results[0].cv_file.id == results[1].cv_file.id
    with Session(empty_engine) as session:
        cv_file = session.scalar(select(CvFile))
        assert cv_file.status == ProcessingStatus.done
        cv_file_id = cv_file.id
        assert session.scalar(select(func.count()).select_from(CvFile)) == 1
        assert session.scalar(select(func.count()).select_from(Activity)) == 1
    assert len(list(committed_runtime.root.iterdir())) == 1
    tasks.process_cv_file.delay(str(cv_file_id))


def test_concurrent_distinct_files_with_same_contacts_create_one_candidate(
    committed_runtime, monkeypatch
):
    runtime = committed_runtime
    parse_barrier = Barrier(2)
    original_parse = tasks.parse_cv

    def synchronized_parse(*args, **kwargs):
        parse_barrier.wait(timeout=10)
        return original_parse(*args, **kwargs)

    monkeypatch.setattr(tasks, "parse_cv", synchronized_parse)
    source = (REPO_ROOT / "data/sample_cvs/cv_0001.pdf").read_bytes()

    def upload_once(index):
        with Session(runtime.engine) as session:
            actor = session.get(User, runtime.actor_id)
            return upload_file(
                session,
                actor,
                runtime.storage,
                data=source + f"\n% revision {index}".encode(),
                filename="synthetic.pdf",
                job_id=None,
                index=index,
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(upload_once, range(2)))
    assert all(not result.duplicate for result in results)
    with Session(runtime.engine) as session:
        rows = session.scalars(select(CvFile)).all()
        assert len(rows) == 2 and all(row.status == ProcessingStatus.done for row in rows)
        assert rows[0].candidate_id == rows[1].candidate_id
        assert session.scalar(select(func.count()).select_from(Candidate)) == 1


def test_concurrent_delivery_of_same_pending_file_parses_once(committed_runtime, monkeypatch):
    runtime = committed_runtime
    monkeypatch.setattr(tasks.process_cv_file, "delay", lambda *args: None)
    with Session(runtime.engine) as session:
        result = upload_file(
            session,
            session.get(User, runtime.actor_id),
            runtime.storage,
            data=(REPO_ROOT / "data/sample_cvs/cv_0001.pdf").read_bytes(),
            filename="synthetic.pdf",
            job_id=None,
            index=0,
        )
        file_id = str(result.cv_file.id)
    barrier = Barrier(2)
    original_parse = tasks.parse_cv
    lock = Lock()
    calls = 0

    @contextmanager
    def session():
        with Session(runtime.engine) as db:
            barrier.wait(timeout=10)
            yield db

    def counted_parse(*args, **kwargs):
        nonlocal calls
        with lock:
            calls += 1
        return original_parse(*args, **kwargs)

    monkeypatch.setattr(tasks, "worker_session", session)
    monkeypatch.setattr(tasks, "parse_cv", counted_parse)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(tasks.process_cv_file.run, [file_id, file_id]))
    assert calls == 1
    with Session(runtime.engine) as db:
        assert db.scalar(select(CvFile)).status == ProcessingStatus.done
        assert db.scalar(select(func.count()).select_from(Candidate)) == 1


def test_worker_crash_rolls_back_to_pending_and_redelivery_completes(
    committed_runtime, monkeypatch
):
    runtime = committed_runtime
    monkeypatch.setattr(tasks.process_cv_file, "delay", lambda *args: None)
    with Session(runtime.engine) as session:
        result = upload_file(
            session,
            session.get(User, runtime.actor_id),
            runtime.storage,
            data=(REPO_ROOT / "data/sample_cvs/cv_0001.pdf").read_bytes(),
            filename="synthetic.pdf",
            job_id=None,
            index=0,
        )
        file_id = str(result.cv_file.id)

    class SimulatedCrash(BaseException):
        pass

    def crash(*args):
        raise SimulatedCrash()

    original = tasks.anonymize_and_embed
    monkeypatch.setattr(tasks, "anonymize_and_embed", crash)
    with pytest.raises(SimulatedCrash):
        tasks.process_cv_file.run(file_id)
    with Session(runtime.engine) as session:
        row = session.scalar(select(CvFile))
        assert row.status == ProcessingStatus.pending and row.candidate_id is None
        assert session.scalar(select(func.count()).select_from(Candidate)) == 0
    monkeypatch.setattr(tasks, "anonymize_and_embed", original)
    tasks.process_cv_file.run(file_id)
    with Session(runtime.engine) as session:
        assert session.scalar(select(CvFile)).status == ProcessingStatus.done
        assert session.scalar(select(func.count()).select_from(Candidate)) == 1


def test_t12_concurrent_bank_add_commits_before_independent_score_worker(
    committed_runtime, monkeypatch
):
    runtime = committed_runtime
    with Session(runtime.engine) as session:
        unit = HiringUnit(name="Đơn vị giả T12", kind=HiringUnitKind.department)
        candidate = Candidate(
            full_name="Nhân Vật Giả T12",
            retention_until=date(2099, 1, 1),
            anonymized_text="Kỹ năng: Python\n" + "Kinh nghiệm giả. " * 30,
        )
        session.add_all([unit, candidate])
        session.flush()
        job = Job(
            hiring_unit_id=unit.id,
            owner_id=runtime.actor_id,
            title="Python",
            description="Yêu cầu giả",
            must_have=["Python"],
        )
        session.add(job)
        session.commit()
        candidate_id, job_id = candidate.id, job.id
    barrier = Barrier(2)
    observed = []
    original = tasks.score_application.delay

    def independent_worker(application_id):
        # A new DB connection must see the committed row before the worker starts.
        with Session(runtime.engine) as session:
            assert session.get(Application, application_id) is not None
        original(application_id)
        observed.append(application_id)

    monkeypatch.setattr(tasks.score_application, "delay", independent_worker)

    def add_once(_):
        with Session(runtime.engine) as session:
            actor = session.get(User, runtime.actor_id)
            barrier.wait(timeout=10)
            try:
                return create_application(
                    session, actor, candidate_id=candidate_id, job_id=job_id
                ).id
            except AppError as exc:
                assert exc.code == "APPLICATION_EXISTS"
                return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(add_once, range(2)))
    assert sum(result is not None for result in results) == 1
    assert len(observed) == 1
    with Session(runtime.engine) as session:
        application = session.scalar(select(Application))
        assert application.ai_status == "done" and application.ai_score == 100
        assert application.stage == "new"
        assert session.scalar(select(func.count()).select_from(Application)) == 1
        assert (
            session.scalar(
                select(func.count())
                .select_from(Activity)
                .where(Activity.type == ActivityType.ai_scored)
            )
            == 1
        )


def test_t12_parallel_score_delivery_is_idempotent_and_crash_can_resume(
    committed_runtime, monkeypatch
):
    runtime = committed_runtime
    with Session(runtime.engine) as session:
        unit = HiringUnit(name="Đơn vị giả T12", kind=HiringUnitKind.department)
        candidate = Candidate(
            full_name="Nhân Vật Giả T12",
            retention_until=date(2099, 1, 1),
            anonymized_text="Kỹ năng: Python\n" + "Kinh nghiệm giả. " * 30,
        )
        session.add_all([unit, candidate])
        session.flush()
        job = Job(
            hiring_unit_id=unit.id,
            owner_id=runtime.actor_id,
            title="Python",
            description="Yêu cầu giả",
            must_have=["Python"],
        )
        session.add(job)
        session.flush()
        application = Application(candidate_id=candidate.id, job_id=job.id, owner_id=job.owner_id)
        session.add(application)
        session.commit()
        application_id = str(application.id)

    class SimulatedCrash(BaseException):
        pass

    original = tasks.score_cv

    def crash(*args, **kwargs):
        raise SimulatedCrash()

    monkeypatch.setattr(tasks, "score_cv", crash)
    with pytest.raises(SimulatedCrash):
        tasks.score_application.run(application_id)
    with Session(runtime.engine) as session:
        assert session.get(Application, application_id).ai_status == "pending"
        assert session.scalar(select(func.count()).select_from(Activity)) == 0
    barrier = Barrier(2)
    lock = Lock()
    calls = 0

    def counted(*args, **kwargs):
        nonlocal calls
        with lock:
            calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(tasks, "score_cv", counted)

    def deliver(_):
        barrier.wait(timeout=10)
        tasks.score_application.run(application_id)

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(deliver, range(2)))
    assert calls == 1
    with Session(runtime.engine) as session:
        assert session.get(Application, application_id).ai_status == "done"
        assert session.scalar(select(func.count()).select_from(Activity)) == 1


def test_t16_creation_waiting_on_merge_cannot_recreate_source_application(
    committed_runtime, monkeypatch
):
    """Preload source on connection B, merge on A, then resume B's creation."""
    from app.services import applications, cv_bank

    runtime = committed_runtime
    with Session(runtime.engine) as session:
        unit = HiringUnit(name="Đơn vị giả T16", kind=HiringUnitKind.department)
        source = Candidate(full_name="Nguồn giả", retention_until=date(2099, 1, 1))
        target = Candidate(full_name="Đích giả", retention_until=date(2099, 1, 1))
        session.add_all([unit, source, target])
        session.flush()
        job = Job(
            title="Vị trí giả T16",
            description="Yêu cầu giả",
            owner_id=runtime.actor_id,
            hiring_unit_id=unit.id,
        )
        session.add(job)
        session.commit()
        source_id, target_id, job_id = source.id, target.id, job.id
    loaded = Event()
    merging = Event()
    original_eligible = applications.eligible_candidate
    original_log = cv_bank.log_activity

    def paused_eligible(session, candidate_id):
        candidate = original_eligible(session, candidate_id)
        # Only pause the first read, before ensure_application takes the row lock.
        if not loaded.is_set():
            loaded.set()
            assert merging.wait(10)
        return candidate

    def pause_merge(session, **kwargs):
        # Candidate locks and mutations already held. Creation must wait and
        # re-read the merged candidate instead of trusting its identity map.
        merging.set()
        return original_log(session, **kwargs)

    monkeypatch.setattr(applications, "eligible_candidate", paused_eligible)
    monkeypatch.setattr(cv_bank, "log_activity", pause_merge)

    def create():
        with Session(runtime.engine) as session:
            with pytest.raises(AppError) as error:
                create_application(
                    session,
                    session.get(User, runtime.actor_id),
                    candidate_id=source_id,
                    job_id=job_id,
                )
            assert error.value.code == "NOT_FOUND"

    def merge_once():
        assert loaded.wait(10)
        with Session(runtime.engine) as session:
            merge(session, session.get(User, runtime.actor_id), source_id, target_id)

    with ThreadPoolExecutor(max_workers=2) as pool:
        create_future = pool.submit(create)
        merge_future = pool.submit(merge_once)
        create_future.result(timeout=20)
        merge_future.result(timeout=20)
    with Session(runtime.engine) as session:
        assert session.get(Candidate, source_id).merged_into_id == target_id
        assert session.scalar(select(func.count()).select_from(Application)) == 0

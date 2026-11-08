from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from threading import Barrier, Lock
from types import SimpleNamespace

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import REPO_ROOT, get_settings
from app.models import Activity, Candidate, CvFile, User, UserRole
from app.models.enums import ProcessingStatus
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

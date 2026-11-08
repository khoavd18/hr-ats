from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from alembic import command
from alembic.config import Config
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import REPO_ROOT, get_settings
from app.models import Activity, CvFile, User, UserRole
from app.models.enums import ProcessingStatus
from app.services.cv_files import upload_file
from app.storage import LocalStorage
from app.workers import tasks
from tests.cv_helpers import PDF


def test_concurrent_upload_publishes_after_commit_and_worker_uses_own_connection(
    empty_engine, tmp_path, monkeypatch
):
    # A dedicated migrated DB allows real commits and an independent worker connection.
    with empty_engine.begin() as connection:
        config = Config(str(REPO_ROOT / "backend/alembic.ini"))
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    settings = get_settings().model_copy(
        update={"database_url": empty_engine.url.render_as_string(hide_password=False)}
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
    storage = LocalStorage(tmp_path)
    barrier = Barrier(2)

    def upload_once(index):
        with Session(empty_engine) as session:
            actor = session.get(User, actor_id)
            barrier.wait(timeout=10)
            return upload_file(
                session,
                actor,
                storage,
                data=PDF,
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
    assert len(list(tmp_path.iterdir())) == 1
    tasks.process_cv_file.delay(str(cv_file_id))

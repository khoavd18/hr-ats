import os
import subprocess
import sys
from contextlib import contextmanager

import pytest
from alembic import command
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import verify_password
from app.models import Activity, Application, Candidate, CvFile, HiringUnit, Job, User
from app.models.applications import StageEvent
from app.models.enums import ApplicationStage, ProcessingStatus
from app.scripts import seed
from app.workers import tasks
from tests.conftest import migration_config


def test_seed_cli_on_empty_migrated_db_is_repeatable_and_preserves_hr_changes(
    empty_engine, tmp_path
):
    with empty_engine.begin() as connection:
        config = migration_config()
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    env = {
        **os.environ,
        "DATABASE_URL": empty_engine.url.render_as_string(hide_password=False),
        "APP_ENV": "dev",
        "LLM_PROVIDER": "fake",
        "EMBEDDING_PROVIDER": "fake",
        "STORAGE_BACKEND": "local",
        "STORAGE_LOCAL_DIR": str(tmp_path),
        "PYTHONIOENCODING": "cp1252",
    }

    def run():
        result = subprocess.run(
            [sys.executable, "-m", "app.scripts.seed"],
            env=env,
            capture_output=True,
            encoding="utf-8",
            timeout=120,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert '"sample_cvs": 40' in result.stdout
        for login, _role in seed.DEV_USERS:
            assert f"dev-{login}@example.invalid / {seed.DEV_PASSWORD}" in result.stdout

    run()
    models = (User, HiringUnit, Job, Candidate, CvFile, Application, StageEvent, Activity)
    with Session(empty_engine) as session:
        counts = [session.scalar(select(func.count()).select_from(model)) for model in models]
        assert counts[:7] == [4, 3, 5, 40, 40, 40, 40]
        for user in session.scalars(select(User)):
            assert verify_password(seed.DEV_PASSWORD, user.password_hash)
        applications = session.scalars(select(Application)).all()
        assert {row.stage for row in applications} == {
            ApplicationStage.new,
            ApplicationStage.screening,
            ApplicationStage.submitted,
            ApplicationStage.interview,
            ApplicationStage.offer,
        }
        assert all(
            row.ai_status == ProcessingStatus.done and row.ai_model == "fake-v1" and row.ai_criteria
            for row in applications
        )
        files = session.scalars(select(CvFile)).all()
        assert all(row.status == ProcessingStatus.done and row.extracted_text for row in files)
        assert not (
            {row.original_filename.removesuffix(".pdf").removesuffix(".docx") for row in files}
            & seed.SMOKE_IDS
        )
        candidates = session.scalars(select(Candidate)).all()
        assert all(row.embedding is not None and row.anonymized_text for row in candidates)
        assert all(row.consent_at is None for row in candidates)
        assert any(row.skills for row in candidates)
        snapshot = [(row.id, row.ai_scored_at, row.ai_score) for row in applications]
        changed = applications[0]
        changed.stage = ApplicationStage.withdrawn
        changed_id = changed.id
        session.commit()
    keys = sorted(path.name for path in tmp_path.rglob("*") if path.is_file())
    run()
    with Session(empty_engine) as session:
        assert counts == [
            session.scalar(select(func.count()).select_from(model)) for model in models
        ]
        assert session.get_one(Application, changed_id).stage == ApplicationStage.withdrawn
        assert snapshot == [
            (
                session.get_one(Application, record_id).id,
                session.get_one(Application, record_id).ai_scored_at,
                session.get_one(Application, record_id).ai_score,
            )
            for record_id, _time, _score in snapshot
        ]
    assert sorted(path.name for path in tmp_path.rglob("*") if path.is_file()) == keys


def test_seed_does_not_overwrite_existing_dev_account(db_session):
    users, _jobs = seed.seed_catalog(db_session)
    user = users["recruiter"]
    user.password_hash = "synthetic-changed-password-hash"
    db_session.commit()
    with pytest.raises(seed.SeedError, match="không ghi đè"):
        seed.seed_catalog(db_session)
    assert user.password_hash == "synthetic-changed-password-hash"


def test_interrupted_pipeline_seed_can_resume_without_duplicate_rows(
    db_session, tmp_path, monkeypatch
):
    settings = get_settings().model_copy(update={"storage_local_dir": tmp_path})
    monkeypatch.setattr(seed, "get_settings", lambda: settings)
    monkeypatch.setattr(tasks, "get_settings", lambda: settings)

    @contextmanager
    def worker_session():
        yield db_session

    monkeypatch.setattr(tasks, "worker_session", worker_session)
    original_parse = tasks.parse_cv

    def fail(*args, **kwargs):
        raise RuntimeError("SYNTHETIC_PRIVATE_SENTINEL")

    monkeypatch.setattr(tasks, "parse_cv", fail)
    with pytest.raises(seed.SeedError, match="Pipeline CV"):
        seed.seed_demo(db_session)
    assert db_session.scalar(select(func.count()).select_from(CvFile)) == 1
    monkeypatch.setattr(tasks, "parse_cv", original_parse)
    assert seed.seed_demo(db_session)["sample_cvs"] == 40
    assert db_session.scalar(select(func.count()).select_from(CvFile)) == 40
    assert db_session.scalar(select(func.count()).select_from(Candidate)) == 40
    assert db_session.scalar(select(func.count()).select_from(Application)) == 40

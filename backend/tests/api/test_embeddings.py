"""T11 hooks and atomic maintenance on real PostgreSQL, using only synthetic data."""

import json
import os
import subprocess
import sys
from contextlib import contextmanager
from datetime import UTC, date, datetime
from uuid import UUID

import pytest
from alembic import command
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.embed import EmbeddingError, FakeEmbedder
from app.core.config import get_settings
from app.models import Candidate, HiringUnit, Job, User, UserRole
from app.models.enums import HiringUnitKind
from app.scripts import reembed
from app.services.embeddings import embed_candidate, embed_job
from tests.conftest import migration_config


@pytest.fixture
def records(db_session, account):
    candidate = Candidate(
        id=UUID(int=1),
        full_name="Nhân Vật Giả",
        retention_until=date(2099, 1, 1),
        anonymized_text="[TÊN]\nKỹ năng: Python SQL",
        embedding=[1.0] + [0.0] * (get_settings().embedding_dim - 1),
    )
    unit = HiringUnit(name="Đơn vị mô phỏng", kind=HiringUnitKind.department)
    db_session.add_all([candidate, unit])
    db_session.flush()
    job = Job(
        hiring_unit_id=unit.id,
        owner_id=account.id,
        title="Python",
        description="SQL",
        must_have=["FastAPI"],
        nice_to_have=["Redis"],
    )
    db_session.add(job)
    db_session.commit()
    return candidate, job


def test_job_create_update_hook_uses_all_four_fields_and_shares_transaction(db_session, records):
    candidate, job = records
    adapter = FakeEmbedder(get_settings().embedding_dim)
    embed_job(job)
    db_session.flush()
    assert list(db_session.scalar(select(Job.embedding).where(Job.id == job.id))) == pytest.approx(
        adapter.embed(["Python\nSQL\nFastAPI\nRedis"])[0]
    )
    before = list(job.embedding)
    with pytest.raises(RuntimeError), db_session.begin_nested():
        job.title = "React"
        job.description = "CSS"
        job.must_have = ["Typescript"]
        job.nice_to_have = []
        embed_job(job)
        db_session.flush()
        assert list(job.embedding) == pytest.approx(adapter.embed(["React\nCSS\nTypescript"])[0])
        raise RuntimeError("synthetic rollback")
    db_session.refresh(job)
    assert job.title == "Python" and job.embedding == pytest.approx(before)
    job.must_have = ["Docker"]
    embed_job(job)
    db_session.commit()
    assert job.embedding == pytest.approx(adapter.embed(["Python\nSQL\nDocker\nRedis"])[0])


def test_reembed_all_changes_both_spaces_is_repeatable_and_clears_ineligible(db_session, records):
    candidate, job = records
    vector = list(candidate.embedding)
    hidden = [
        Candidate(
            full_name="Đã xoá giả",
            retention_until=date(2099, 1, 1),
            deleted_at=datetime.now(UTC),
            embedding=vector,
        ),
        Candidate(
            full_name="Đã gộp giả",
            retention_until=date(2099, 1, 1),
            merged_into_id=candidate.id,
            embedding=vector,
        ),
        Candidate(full_name="Hết hạn giả", retention_until=date(2000, 1, 1), embedding=vector),
    ]
    db_session.add_all(hidden)
    db_session.commit()
    assert reembed.reembed_all(db_session, settings=get_settings()) == {"candidates": 1, "jobs": 1}
    db_session.commit()
    assert list(candidate.embedding) != vector
    assert candidate.embedding == pytest.approx(
        FakeEmbedder(get_settings().embedding_dim).embed([candidate.anonymized_text])[0]
    )
    assert job.embedding is not None and all(row.embedding is None for row in hidden)
    vectors = list(candidate.embedding), list(job.embedding)
    assert reembed.reembed_all(db_session, settings=get_settings()) == {"candidates": 1, "jobs": 1}
    db_session.commit()
    assert candidate.embedding == pytest.approx(vectors[0])
    assert job.embedding == pytest.approx(vectors[1])


@pytest.mark.parametrize("failure", ["encoder", "missing_text", "wrong_dimension"])
def test_reembed_failure_never_leaves_mixed_spaces(db_session, records, failure):
    candidate, job = records
    second = Candidate(
        id=UUID(int=2),
        full_name="Người Giả Khác",
        retention_until=date(2099, 1, 1),
        anonymized_text=None if failure == "missing_text" else "[TÊN] React",
    )
    expired = Candidate(
        full_name="Hết hạn giả",
        retention_until=date(2000, 1, 1),
        embedding=list(candidate.embedding),
    )
    db_session.add_all([second, expired])
    db_session.commit()
    before = list(candidate.embedding)

    class FailSecond(FakeEmbedder):
        calls = 0

        def embed(self, texts):
            self.calls += 1
            if self.calls == 2:
                if failure == "wrong_dimension":
                    return [[1.0]]
                raise RuntimeError("synthetic-private-error")
            return super().embed(texts)

    with pytest.raises((EmbeddingError, RuntimeError)):
        reembed.reembed_all(
            db_session, settings=get_settings(), embedder=FailSecond(get_settings().embedding_dim)
        )
    db_session.refresh(candidate)
    db_session.refresh(expired)
    assert candidate.embedding == pytest.approx(before)
    assert expired.embedding == pytest.approx(before)
    assert job.embedding is None and second.embedding is None


def test_cli_commits_counts_and_sanitizes_unexpected_failures(
    db_session, records, monkeypatch, capsys
):
    @contextmanager
    def session(settings):
        yield db_session

    monkeypatch.setattr(reembed, "reembed_session", session)
    assert reembed.main(["--all"]) == 0
    assert json.loads(capsys.readouterr().out) == {"status": "ok", "candidates": 1, "jobs": 1}

    def broken(*args, **kwargs):
        raise RuntimeError("private-sentinel sentinel@example.invalid")

    monkeypatch.setattr(reembed, "reembed_all", broken)
    assert reembed.main(["--all"]) == 1
    assert json.loads(capsys.readouterr().out) == {"status": "error", "code": "REEMBED_FAILED"}


def test_candidate_hook_rejects_empty_anonymization_without_mutating(records):
    candidate, job = records
    before = candidate.anonymized_text, list(candidate.embedding)
    with pytest.raises(EmbeddingError):
        embed_candidate(candidate, "Giới tính: Nam\nTuổi: 25")
    assert candidate.anonymized_text == before[0] and candidate.embedding == before[1]


def test_cli_real_module_commits_on_isolated_migrated_database(empty_engine):
    with empty_engine.begin() as connection:
        config = migration_config()
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    with Session(empty_engine) as session:
        user = User(
            email="reembed-cli@example.invalid",
            full_name="Quản trị giả",
            role=UserRole.admin,
            password_hash="synthetic-unused-hash",
        )
        unit = HiringUnit(name="Đơn vị giả", kind=HiringUnitKind.department)
        candidate = Candidate(
            full_name="Nhân Vật Giả",
            retention_until=date(2099, 1, 1),
            anonymized_text="[TÊN]\nKỹ năng: Python SQL",
        )
        session.add_all([user, unit, candidate])
        session.flush()
        job = Job(hiring_unit_id=unit.id, owner_id=user.id, title="Python", description="SQL")
        session.add(job)
        session.commit()
        candidate_id, job_id = candidate.id, job.id
    result = subprocess.run(
        [sys.executable, "-m", "app.scripts.reembed", "--all"],
        env={
            **os.environ,
            "DATABASE_URL": empty_engine.url.render_as_string(hide_password=False),
            "APP_ENV": "test",
            "EMBEDDING_PROVIDER": "fake",
        },
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout) == {"status": "ok", "candidates": 1, "jobs": 1}
    with Session(empty_engine) as session:
        adapter = FakeEmbedder(get_settings().embedding_dim)
        assert session.get(Candidate, candidate_id).embedding == pytest.approx(
            adapter.embed(["[TÊN]\nKỹ năng: Python SQL"])[0]
        )
        assert session.get(Job, job_id).embedding == pytest.approx(
            adapter.embed(["Python\nSQL"])[0]
        )

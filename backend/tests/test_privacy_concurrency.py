"""Real independent transactions: freeze commits before I/O, writers cannot revive PII."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Event

import pytest
from alembic import command
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import AuditLog, Candidate, CvFile, User
from app.models.users import UserRole
from app.schemas.privacy import DataRequestInput
from app.schemas.profile import CandidatePatch
from app.services import privacy, profile
from app.storage import LocalStorage
from tests.conftest import migration_config


def test_two_executors_one_audit_and_late_writer_cannot_restore_name(empty_engine, tmp_path):
    with empty_engine.begin() as connection:
        config = migration_config()
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    storage = LocalStorage(tmp_path)
    key = storage.put(b"synthetic bytes only", "application/pdf")
    with Session(empty_engine) as session:
        actor = User(
            email="privacy-concurrent@example.invalid",
            full_name="HR giả",
            role=UserRole.admin,
            password_hash="unused-synthetic-hash",
        )
        candidate = Candidate(full_name="Ứng viên giả", retention_until=date(2099, 1, 1))
        session.add_all([actor, candidate])
        session.flush()
        session.add(
            CvFile(
                candidate_id=candidate.id,
                storage_key=key,
                original_filename="synthetic.pdf",
                mime_type="application/pdf",
                size_bytes=20,
                sha256="a" * 64,
            )
        )
        session.commit()
        request = privacy.create_request(
            session,
            actor,
            DataRequestInput(candidate_id=candidate.id, requested_by_note="Bằng chứng giả"),
        )
        actor_id, candidate_id, request_id = actor.id, candidate.id, request.id
    entered, release = Event(), Event()

    class PausingStorage:
        def delete(self, key):
            entered.set()
            assert release.wait(10)
            storage.delete(key)

    def execute(selected_storage):
        with Session(empty_engine) as session:
            return privacy.execute_request(
                session, session.get_one(User, actor_id), request_id, selected_storage
            ).status

    with Session(empty_engine) as late_writer, ThreadPoolExecutor(max_workers=2) as pool:
        # Populate a stale identity map before the freeze.
        assert late_writer.get_one(Candidate, candidate_id).full_name is not None
        first = pool.submit(execute, PausingStorage())
        try:
            assert entered.wait(10)
            with Session(empty_engine) as observer:
                row = observer.get_one(Candidate, candidate_id)
                assert row.deleted_at is not None and row.purge_pending_at is not None
                assert row.purged_at is None and (tmp_path / key).exists()
            second = pool.submit(execute, storage)
            try:
                profile.patch_candidate(
                    late_writer,
                    late_writer.get_one(User, actor_id),
                    candidate_id,
                    CandidatePatch(full_name="Tên giả ghi muộn"),
                )
                raise AssertionError("Frozen candidate accepted a late writer")
            except AppError as error:
                assert error.code == "NOT_FOUND"
            finally:
                late_writer.rollback()
        finally:
            release.set()
        assert first.result(10) == second.result(10) == "done"
    with Session(empty_engine) as observer:
        assert observer.get_one(Candidate, candidate_id).full_name is None
        assert (
            observer.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.action == "candidate.purge")
            )
            == 1
        )
    assert not (tmp_path / key).exists()


def test_downgrade_refuses_to_discard_privacy_history(empty_engine):
    with empty_engine.begin() as connection:
        config = migration_config()
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    with Session(empty_engine) as session:
        candidate = Candidate(full_name="Ứng viên giả", retention_until=date(2099, 1, 1))
        session.add(candidate)
        session.commit()
        from datetime import UTC, datetime

        privacy.freeze_candidate(session, candidate.id, datetime.now(UTC))
    with pytest.raises(DBAPIError):
        with empty_engine.begin() as connection:
            config = migration_config()
            config.attributes["connection"] = connection
            command.downgrade(config, "0008_tasks")
    with Session(empty_engine) as session:
        assert session.scalars(select(Candidate)).one().purge_pending_at is not None

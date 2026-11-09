import io

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import Column, Engine, Index, Integer, MetaData, Table, inspect, text
from sqlalchemy.orm import Session

from app.core.config import REPO_ROOT
from app.models import Base


def test_migration_upgrades_empty_database_and_preserves_extensions_on_rollback(
    empty_engine: Engine,
) -> None:
    with empty_engine.begin() as connection:
        extensions_query = text(
            "SELECT extname FROM pg_extension WHERE extname IN ('vector', 'unaccent')"
        )
        assert list(connection.execute(extensions_query).scalars()) == []
        config = Config(str(REPO_ROOT / "backend/alembic.ini"))
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        assert set(connection.execute(extensions_query).scalars()) == {"vector", "unaccent"}
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == (
            "0008_tasks"
        )
        assert set(inspect(connection).get_table_names()) == set(Base.metadata.tables) | {
            "alembic_version"
        }
        command.downgrade(config, "base")
        assert set(connection.execute(extensions_query).scalars()) == {"vector", "unaccent"}
        assert connection.execute(text("SELECT count(*) FROM alembic_version")).scalar_one() == 0
        assert inspect(connection).get_table_names() == ["alembic_version"]
        assert (
            connection.execute(
                text(
                    "SELECT count(*) FROM pg_type WHERE typname IN "
                    "('user_role', 'application_stage', 'processing_status', 'candidate_source', "
                    "'hiring_unit_kind', 'job_status', 'ai_level', "
                    "'extraction_method', 'activity_type', 'task_status')"
                )
            ).scalar_one()
            == 0
        )
        assert (
            connection.execute(
                text("SELECT to_regprocedure('public.candidates_update_search_tsv()')")
            ).scalar_one()
            is None
        )
        command.upgrade(config, "head")
        assert connection.execute(text("SELECT count(*) FROM alembic_version")).scalar_one() == 1


def test_offline_migration_generates_extension_sql() -> None:
    output = io.StringIO()
    config = Config(str(REPO_ROOT / "backend/alembic.ini"), output_buffer=output)
    command.upgrade(config, "head", sql=True)
    assert "CREATE EXTENSION IF NOT EXISTS vector" in output.getvalue()
    assert "CREATE EXTENSION IF NOT EXISTS unaccent" in output.getvalue()


def test_session_commit_stays_inside_the_per_test_transaction(
    db_session: Session, test_engine: Engine
) -> None:
    assert db_session.execute(text("SELECT current_database()")).scalar_one() == "hr_ats_test"
    db_session.execute(text("CREATE TABLE t02_transaction_probe (id integer PRIMARY KEY)"))
    db_session.execute(text("INSERT INTO t02_transaction_probe (id) VALUES (1)"))
    db_session.commit()
    assert db_session.execute(text("SELECT id FROM t02_transaction_probe")).scalar_one() == 1
    with test_engine.connect() as connection:
        assert (
            connection.execute(text("SELECT to_regclass('t02_transaction_probe')")).scalar_one()
            is None
        )


def test_models_match_the_migrated_schema(test_engine: Engine) -> None:
    with test_engine.connect() as connection:
        context = MigrationContext.configure(
            connection, opts={"compare_type": True, "compare_server_default": True}
        )
        assert compare_metadata(context, Base.metadata) == []


@pytest.mark.parametrize("missing", ["table", "column", "index"])
def test_schema_comparison_detects_missing_migrations(empty_engine: Engine, missing: str) -> None:
    metadata = MetaData()
    table = Table("t02_schema_probe", metadata, Column("id", Integer, primary_key=True))
    if missing == "column":
        table.append_column(Column("revision", Integer))
    if missing == "index":
        Index("ix_t02_schema_probe_id", table.c.id)
    with empty_engine.begin() as connection:
        if missing != "table":
            connection.execute(text("CREATE TABLE t02_schema_probe (id integer PRIMARY KEY)"))
        context = MigrationContext.configure(connection)
        changes = compare_metadata(context, metadata)
        expected = {"table": "add_table", "column": "add_column", "index": "add_index"}[missing]
        assert any(change[0] == expected for change in changes)

import io

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.core.config import REPO_ROOT


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
            "0001_enable_extensions"
        )
        command.downgrade(config, "base")
        assert set(connection.execute(extensions_query).scalars()) == {"vector", "unaccent"}
        assert connection.execute(text("SELECT count(*) FROM alembic_version")).scalar_one() == 0
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

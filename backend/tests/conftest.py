import ipaddress
import os
import smtplib
import socket
from collections.abc import Iterator
from uuid import uuid4

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from celery import current_app
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy import Engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import REPO_ROOT, Settings, get_settings

# Always derive the dedicated test DB from local settings, never use the application DB.
TEST_URL = make_url(Settings().database_url).set(database="hr_ats_test", query={})
if TEST_URL.host not in {"localhost", "127.0.0.1", "::1"}:
    raise RuntimeError("Tests require a localhost PostgreSQL server")
if TEST_URL.drivername != "postgresql+psycopg":
    raise RuntimeError("Tests require PostgreSQL with psycopg")
os.environ.update(
    APP_ENV="test",
    DATABASE_URL=TEST_URL.render_as_string(hide_password=False),
    REDIS_URL="redis://127.0.0.1:6379/15",
    SECRET_KEY="t04-synthetic-signing-key-for-tests-only",
    LLM_PROVIDER="fake",
    EMBEDDING_PROVIDER="fake",
    UV_OFFLINE="1",
)
get_settings.cache_clear()

from app.core import security  # noqa: E402
from app.core.db import build_engine, get_session  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models.users import User, UserRole  # noqa: E402
from tests.auth_helpers import PASSWORD  # noqa: E402


@pytest.fixture(autouse=True)
def local_network_only(monkeypatch: pytest.MonkeyPatch) -> None:
    original_lookup = socket.getaddrinfo
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    def check_host(host: object) -> None:
        if isinstance(host, bytes):
            host = host.decode("ascii")
        if host in {None, "localhost"}:
            return
        try:
            if ipaddress.ip_address(str(host)).is_loopback:
                return
        except ValueError:
            pass
        raise AssertionError("External network is forbidden in tests")

    def lookup(host, *args, **kwargs):
        check_host(host)
        return original_lookup(host, *args, **kwargs)

    def connect(sock, address):
        if sock.family in {socket.AF_INET, socket.AF_INET6}:
            check_host(address[0])
        return original_connect(sock, address)

    def connect_ex(sock, address):
        if sock.family in {socket.AF_INET, socket.AF_INET6}:
            check_host(address[0])
        return original_connect_ex(sock, address)

    monkeypatch.setattr(socket, "getaddrinfo", lookup)
    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)


@pytest.fixture(autouse=True)
def isolated_rate_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    # Real Redis/Lua, one expiring namespace per test; never flush a shared Redis database.
    monkeypatch.setattr("app.core.rate_limit.KEY_PREFIX", "hr-ats:test-rate:" + uuid4().hex + ":")


@pytest.fixture(autouse=True)
def eager_celery(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(current_app.conf, "task_always_eager", True)
    monkeypatch.setitem(current_app.conf, "task_eager_propagates", True)
    monkeypatch.setitem(current_app.conf, "broker_url", "memory://")
    monkeypatch.setitem(current_app.conf, "result_backend", "cache+memory://")


@pytest.fixture(autouse=True)
def email_outbox(monkeypatch: pytest.MonkeyPatch) -> list:
    outbox = []

    class MemorySMTP:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def send_message(self, message, *args, **kwargs):
            outbox.append(message)
            return {}

        def sendmail(self, sender, recipients, message, *args, **kwargs):
            outbox.append(message)
            return {}

        def starttls(self, *args, **kwargs):
            return 220, b"test"

        def login(self, *args, **kwargs):
            return 235, b"test"

        def quit(self):
            return 221, b"test"

    monkeypatch.setattr(smtplib, "SMTP", MemorySMTP)
    monkeypatch.setattr(smtplib, "SMTP_SSL", MemorySMTP)
    return outbox


@pytest.fixture(scope="session")
def admin_connection() -> Iterator[psycopg.Connection]:
    admin_url = TEST_URL.set(database="postgres")
    with psycopg.connect(
        **admin_url.translate_connect_args(database="dbname", username="user"),
        autocommit=True,
        connect_timeout=3,
    ) as connection:
        yield connection


def migration_config() -> Config:
    return Config(str(REPO_ROOT / "backend/alembic.ini"))


@pytest.fixture(scope="session")
def test_engine(admin_connection: psycopg.Connection) -> Iterator[Engine]:
    exists = admin_connection.execute(
        "SELECT 1 FROM pg_database WHERE datname = %s", ("hr_ats_test",)
    ).fetchone()
    if not exists:
        admin_connection.execute(
            sql.SQL("CREATE DATABASE {}").format(sql.Identifier("hr_ats_test"))
        )
    engine = build_engine(TEST_URL.render_as_string(hide_password=False))
    try:
        with engine.begin() as connection:
            config = migration_config()
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db_session(test_engine: Engine) -> Iterator[Session]:
    with test_engine.connect() as connection:
        transaction = connection.begin()
        try:
            with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
                yield session
        finally:
            transaction.rollback()


@pytest.fixture
def app(db_session: Session) -> FastAPI:
    application = create_app()

    def override_session() -> Iterator[Session]:
        yield db_session

    application.dependency_overrides[get_session] = override_session
    return application


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def empty_engine(admin_connection: psycopg.Connection) -> Iterator[Engine]:
    # Only this fixture's freshly created database is removed; hr_ats and hr_ats_test are kept.
    name = "hr_ats_test_t02_" + uuid4().hex
    admin_connection.execute(
        sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(name))
    )
    engine = build_engine(TEST_URL.set(database=name).render_as_string(hide_password=False))
    try:
        yield engine
    finally:
        engine.dispose()
        admin_connection.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


@pytest.fixture
def account(db_session: Session) -> User:
    user = User(
        email="auth-user@example.invalid",
        full_name="Tài khoản giả",
        role=UserRole.admin,
        password_hash=security.hash_password(PASSWORD),
    )
    db_session.add(user)
    db_session.commit()
    return user

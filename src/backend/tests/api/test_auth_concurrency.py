from concurrent.futures import ThreadPoolExecutor

from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.db import get_session
from app.core.errors import AppError
from app.core.security import hash_password
from app.main import create_app
from app.models.users import User, UserRole
from app.services.auth import login
from tests.auth_helpers import PASSWORD, sign_in
from tests.conftest import migration_config


def test_simultaneous_failed_logins_do_not_lose_attempts(empty_engine):
    with empty_engine.begin() as connection:
        config = migration_config()
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    with Session(empty_engine) as session:
        session.add(
            User(
                email="concurrent@example.invalid",
                full_name="Tài khoản giả đồng thời",
                role=UserRole.recruiter,
                password_hash=hash_password(PASSWORD),
            )
        )
        session.commit()

    def fail_login(_):
        with Session(empty_engine) as session:
            try:
                login(session, "concurrent@example.invalid", "wrong-synthetic")
            except AppError as error:
                return error.status
        raise AssertionError("Wrong password accepted")

    with ThreadPoolExecutor(max_workers=5) as pool:
        statuses = list(pool.map(fail_login, range(5)))
    assert sorted(statuses) == [401, 401, 401, 401, 423]
    with Session(empty_engine) as session:
        user = session.scalar(select(User))
        assert user.failed_login_attempts == 5 and user.locked_until is not None
        user.locked_until = None
        user.failed_login_attempts = 0
        session.commit()

    application = create_app(
        Settings(app_env="test", secret_key="synthetic-concurrency-signing-key-for-tests-only")
    )

    def session_dependency():
        with Session(empty_engine) as session:
            yield session

    application.dependency_overrides[get_session] = session_dependency
    with TestClient(application) as client:
        assert sign_in(client, "concurrent@example.invalid").status_code == 200
        copied = dict(client.cookies)

    def refresh_same_token(_):
        with TestClient(application) as client:
            client.cookies.update(copied)
            return client.post(
                "/api/v1/auth/refresh", headers={"X-CSRF-Token": copied["csrf_token"]}
            ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(refresh_same_token, range(2))) == [200, 401]

"""Local-only, disposable database for the T04 browser acceptance tests."""

from uuid import uuid4

import psycopg
import uvicorn
from alembic import command
from alembic.config import Config
from psycopg import sql
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import REPO_ROOT, Settings
from app.core.db import build_engine
from app.core.security import hash_password
from app.main import create_app
from app.models.users import User, UserRole


def main() -> None:
    settings = Settings()
    url = make_url(settings.database_url)
    if url.host not in {"localhost", "127.0.0.1", "::1"}:
        raise RuntimeError("Browser fixture requires localhost PostgreSQL")
    url = url.set(host="127.0.0.1")
    name = "hr_ats_test_t04_" + uuid4().hex
    with psycopg.connect(
        **url.set(database="postgres").translate_connect_args(database="dbname", username="user"),
        autocommit=True,
        connect_timeout=3,
    ) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(name)))
        engine = build_engine(url.set(database=name).render_as_string(hide_password=False))
        try:
            with engine.begin() as connection:
                config = Config(str(REPO_ROOT / "backend/alembic.ini"))
                config.attributes["connection"] = connection
                command.upgrade(config, "head")
            with Session(engine) as session:
                for role in (UserRole.admin, UserRole.recruiter):
                    session.add(
                        User(
                            email=f"browser-{role}@example.invalid",
                            full_name=f"Tài khoản giả {role}",
                            role=role,
                            password_hash=hash_password("synthetic-browser-password"),
                        )
                    )
                session.commit()
            app = create_app(
                Settings(
                    app_env="test",
                    secret_key="synthetic-browser-signing-key-for-tests-only",
                    database_url=url.set(database=name).render_as_string(hide_password=False),
                )
            )
            # Share this engine so it can be disposed before dropping our database.
            from app.core.db import get_session

            def session_dependency():
                with Session(engine) as session:
                    yield session

            app.dependency_overrides[get_session] = session_dependency
            uvicorn.run(app, host="127.0.0.1", port=8000, access_log=False)
        finally:
            engine.dispose()
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()

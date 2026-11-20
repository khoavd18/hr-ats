from typing import Annotated

from fastapi import Depends
from fastapi.testclient import TestClient
from redis import Redis
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.db import get_session
from app.core.redis import get_redis
from app.main import create_app


def test_custom_app_settings_reach_database_and_redis_dependencies() -> None:
    application = create_app(
        Settings(
            database_url="postgresql+psycopg://hr:hr@localhost:5432/hr_ats_test_custom_factory",
            redis_url="redis://localhost:6379/14",
        )
    )

    @application.get("/test/dependencies")
    def dependencies(
        session: Annotated[Session, Depends(get_session)],
        redis_client: Annotated[Redis, Depends(get_redis)],
    ) -> dict:
        # Inspect the configured clients without opening a connection to the synthetic DB name.
        return {
            "database": session.get_bind().url.database,
            "redis_database": redis_client.connection_pool.connection_kwargs["db"],
        }

    with TestClient(application) as client:
        response = client.get("/test/dependencies")
    assert response.status_code == 200
    assert response.json() == {
        "database": "hr_ats_test_custom_factory",
        "redis_database": 14,
    }

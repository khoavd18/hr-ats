from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings


def build_engine(database_url: str) -> Engine:
    return create_engine(
        database_url,
        pool_pre_ping=True,
        hide_parameters=True,
        connect_args={"connect_timeout": 3},
    )


@lru_cache
def get_engine(database_url: str) -> Engine:
    return build_engine(database_url)


def get_session(settings: Annotated[Settings, Depends(get_settings)]) -> Iterator[Session]:
    with Session(get_engine(settings.database_url)) as session:
        yield session

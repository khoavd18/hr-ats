"""Disposable local API with FakeLLM/eager workers for T14 browser acceptance.

Run with ``uv run python -m tests.ranking_browser_server``. Creating
``var/t14-browser.stop`` requests graceful shutdown and removes only this run's DB.
"""

import os
from datetime import date
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, Thread
from uuid import uuid4

import psycopg
import uvicorn
from alembic import command
from alembic.config import Config
from psycopg import sql
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import REPO_ROOT, Settings, get_settings
from app.core.db import build_engine, get_engine


def seed_bank(session: Session, directory: str) -> None:
    """Two contact-free, synthetic duplicate CVs for T16's real-browser flow."""
    from docx import Document

    from app.ai.embed import FakeEmbedder
    from app.models.candidates import Candidate, CvFile
    from app.models.enums import ProcessingStatus
    from app.storage.local import LocalStorage

    text = "Kế toán Excel báo cáo tài chính. " * 20
    vector = FakeEmbedder(get_settings().embedding_dim).embed([text])[0]
    candidates = [
        Candidate(
            full_name=f"Ứng viên giả kho {label}",
            current_title="Kế toán",
            skills=["Excel", "Kế toán"],
            years_experience=4,
            location="Địa điểm giả",
            retention_until=date(2099, 1, 1),
            anonymized_text=text,
            embedding=vector,
        )
        for label in ("A", "B")
    ]
    session.add_all(candidates)
    session.flush()
    storage = LocalStorage(Path(directory))
    mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    for candidate in candidates:
        document = Document()
        document.add_paragraph(candidate.full_name)
        document.add_paragraph(text)
        output = BytesIO()
        document.save(output)
        data = output.getvalue()
        session.add(
            CvFile(
                candidate_id=candidate.id,
                storage_key=storage.put(data, mime),
                original_filename="cv-gia-kho.docx",
                mime_type=mime,
                size_bytes=len(data),
                sha256=sha256(data).hexdigest(),
                status=ProcessingStatus.done,
                extracted_text=text,
                parsed_json={"possible_duplicate_of": str(candidates[1].id)}
                if candidate == candidates[0]
                else {},
            )
        )


def main() -> None:
    url = make_url(Settings().database_url)
    if url.host not in {"localhost", "127.0.0.1", "::1"}:
        raise RuntimeError("Browser fixture requires localhost PostgreSQL")
    name = "hr_ats_test_t14_" + uuid4().hex
    stop_file = REPO_ROOT / "var/t14-browser.stop"
    if stop_file.exists():
        raise RuntimeError("Remove the previous T14 stop file before starting")
    url = url.set(host="127.0.0.1", database=name)
    with (
        TemporaryDirectory(prefix="hr_ats_t14_") as directory,
        psycopg.connect(
            **url.set(database="postgres").translate_connect_args(
                database="dbname", username="user"
            ),
            autocommit=True,
            connect_timeout=3,
        ) as admin,
    ):
        admin.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(name)))
        os.environ.update(
            APP_ENV="test",
            DATABASE_URL=url.render_as_string(hide_password=False),
            SECRET_KEY="synthetic-browser-signing-key-for-tests-only",
            LLM_PROVIDER="fake",
            EMBEDDING_PROVIDER="fake",
            STORAGE_BACKEND="local",
            STORAGE_LOCAL_DIR=directory,
        )
        get_settings.cache_clear()
        # Import after selecting the isolated DB and eager Celery configuration.
        from app.core.security import hash_password
        from app.main import create_app
        from app.models.users import User, UserRole

        engine = build_engine(get_settings().database_url)
        done = Event()
        try:
            with engine.begin() as connection:
                config = Config(str(REPO_ROOT / "backend/alembic.ini"))
                config.attributes["connection"] = connection
                command.upgrade(config, "head")
            with Session(engine) as session:
                for login, role in (
                    ("admin", UserRole.admin),
                    ("recruiter", UserRole.recruiter),
                    ("ranking", UserRole.admin),
                    ("profile", UserRole.admin),
                    ("bank", UserRole.admin),
                ):
                    session.add(
                        User(
                            email=f"browser-{login}@example.invalid",
                            full_name=f"Tài khoản giả {role}",
                            role=role,
                            password_hash=hash_password("synthetic-browser-password"),
                        )
                    )
                seed_bank(session, directory)
                session.commit()
            server = uvicorn.Server(
                uvicorn.Config(create_app(), host="127.0.0.1", port=8000, access_log=False)
            )

            def watch_stop() -> None:
                while not done.wait(0.2):
                    if stop_file.exists():
                        server.should_exit = True
                        return

            watcher = Thread(target=watch_stop, daemon=True)
            watcher.start()
            server.run()
        finally:
            done.set()
            engine.dispose()
            get_engine(get_settings().database_url).dispose()
            # The identifier is created above in this process, never accepted from input.
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))
            stop_file.unlink(missing_ok=True)


if __name__ == "__main__":
    main()

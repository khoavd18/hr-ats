"""Offline/local maintenance: replace one complete vector space atomically."""

import argparse
import json
import sys
from collections.abc import Sequence
from contextlib import contextmanager
from datetime import datetime
from io import TextIOWrapper
from zoneinfo import ZoneInfo

from pydantic import ValidationError
from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.ai.embed import Embedder, EmbeddingError, get_embedder
from app.core.config import Settings
from app.core.db import get_engine
from app.core.errors import AppError
from app.models.candidates import Candidate
from app.models.jobs import Job
from app.services.embeddings import embed_candidate, embed_job


def reembed_all(
    session: Session, *, settings: Settings, embedder: Embedder | None = None
) -> dict[str, int]:
    """Caller stops writers and commits. Any failure rolls back the whole rebuild.

    Never re-read original CVs or invoke parsing. Missing anonymized source is an
    error rather than silently leaving a vector from a different model behind.
    """
    adapter = embedder or get_embedder(settings)
    today = datetime.now(ZoneInfo(settings.tz)).date()
    counts = {"candidates": 0, "jobs": 0}
    with session.begin_nested():
        # Removed/expired identities must not retain vectors from the old space.
        session.execute(
            update(Candidate)
            .where(
                or_(
                    Candidate.deleted_at.is_not(None),
                    Candidate.merged_into_id.is_not(None),
                    Candidate.retention_until < today,
                )
            )
            .values(embedding=None)
        )
        candidates = session.scalars(
            select(Candidate)
            .where(
                Candidate.deleted_at.is_(None),
                Candidate.merged_into_id.is_(None),
                Candidate.retention_until >= today,
            )
            .order_by(Candidate.id)
            .with_for_update()
        ).yield_per(32)
        for candidate in candidates:
            if not candidate.anonymized_text or not candidate.anonymized_text.strip():
                raise EmbeddingError()
            embed_candidate(
                candidate, candidate.anonymized_text, embedder=adapter, settings=settings
            )
            counts["candidates"] += 1
        for job in session.scalars(select(Job).order_by(Job.id).with_for_update()).yield_per(32):
            embed_job(job, embedder=adapter, settings=settings)
            counts["jobs"] += 1
        session.flush()
    return counts


@contextmanager
def reembed_session(settings: Settings):
    with Session(get_engine(settings.database_url)) as session:
        yield session


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Tính lại dữ liệu tìm kiếm từ nội dung đã ẩn danh."
    )
    parser.add_argument("--all", action="store_true", required=True)
    parser.parse_args(argv)
    try:
        settings = Settings()
        with reembed_session(settings) as session:
            counts = reembed_all(session, settings=settings)
            session.commit()
        print(json.dumps({"status": "ok", **counts}))
    except AppError as exc:
        print(json.dumps({"status": "error", "code": exc.code}))
        return 1
    except ValidationError:
        print('{"status": "error", "code": "INVALID_SETTINGS"}')
        return 1
    except Exception:
        print('{"status": "error", "code": "REEMBED_FAILED"}')
        return 1
    return 0


if __name__ == "__main__":
    if isinstance(sys.stdout, TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())

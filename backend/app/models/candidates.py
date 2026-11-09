from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    FetchedValue,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import get_settings
from app.models.base import Base
from app.models.enums import CandidateSource, ExtractionMethod, ProcessingStatus
from app.models.mixins import RecordMixin, SoftDeleteMixin


class Candidate(RecordMixin, SoftDeleteMixin, Base):
    __tablename__ = "candidates"
    __table_args__ = (
        CheckConstraint("email = lower(email)", name="ck_candidates_email_lowercase"),
        CheckConstraint("years_experience >= 0", name="ck_candidates_experience"),
        Index("ix_candidates_search_tsv", "search_tsv", postgresql_using="gin"),
        Index(
            "ix_candidates_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    full_name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(254), index=True)
    phone: Mapped[str | None] = mapped_column(String(50), index=True)
    location: Mapped[str | None] = mapped_column(String(200))
    current_title: Mapped[str | None] = mapped_column(String(200))
    years_experience: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    skills: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    languages: Mapped[list[Any]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    education: Mapped[list[Any]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    experiences: Mapped[list[Any]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    source: Mapped[CandidateSource] = mapped_column(
        Enum(
            CandidateSource,
            name="candidate_source",
            values_callable=lambda enum: [v.value for v in enum],
        ),
        server_default=text("'upload'"),
    )
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consent_note: Mapped[str | None] = mapped_column(Text)
    retention_until: Mapped[date]
    anonymized_text: Mapped[str | None] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(get_settings().embedding_dim))
    search_tsv: Mapped[str] = mapped_column(
        TSVECTOR, server_default=FetchedValue(), server_onupdate=FetchedValue()
    )
    merged_into_id: Mapped[UUID | None] = mapped_column(ForeignKey("candidates.id"), index=True)


class CvFile(RecordMixin, SoftDeleteMixin, Base):
    __tablename__ = "cv_files"
    __table_args__ = (
        CheckConstraint("size_bytes >= 0", name="ck_cv_files_size"),
        CheckConstraint("page_count > 0", name="ck_cv_files_page_count"),
    )

    candidate_id: Mapped[UUID | None] = mapped_column(ForeignKey("candidates.id"), index=True)
    storage_key: Mapped[str] = mapped_column(Text)
    original_filename: Mapped[str] = mapped_column(Text)
    mime_type: Mapped[str] = mapped_column(String(200))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64), unique=True)
    source: Mapped[CandidateSource] = mapped_column(
        Enum(
            CandidateSource,
            name="candidate_source",
            values_callable=lambda enum: [v.value for v in enum],
        ),
        server_default=text("'upload'"),
    )
    extracted_text: Mapped[str | None] = mapped_column(Text)
    extraction_method: Mapped[ExtractionMethod | None] = mapped_column(
        Enum(ExtractionMethod, name="extraction_method")
    )
    page_count: Mapped[int | None]
    parsed_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    status: Mapped[ProcessingStatus] = mapped_column(
        Enum(ProcessingStatus, name="processing_status"), server_default=text("'pending'")
    )
    error: Mapped[str | None] = mapped_column(Text)
    parse_model: Mapped[str | None] = mapped_column(String(200))
    parse_prompt_version: Mapped[str | None] = mapped_column(String(100))
    uploaded_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    job_id: Mapped[UUID | None] = mapped_column(ForeignKey("jobs.id"), index=True)

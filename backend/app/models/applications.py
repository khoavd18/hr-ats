from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import AiLevel, ApplicationStage, ProcessingStatus
from app.models.mixins import RecordMixin, SoftDeleteMixin


class Application(RecordMixin, SoftDeleteMixin, Base):
    __tablename__ = "applications"
    __table_args__ = (
        Index(
            "uq_applications_active_candidate_job",
            "candidate_id",
            "job_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        CheckConstraint("ai_score BETWEEN 0 AND 100", name="ck_applications_ai_score"),
    )

    candidate_id: Mapped[UUID] = mapped_column(ForeignKey("candidates.id"))
    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id"), index=True)
    stage: Mapped[ApplicationStage] = mapped_column(
        Enum(ApplicationStage, name="application_stage"), server_default=text("'new'")
    )
    stage_entered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    rejected_reason: Mapped[str | None] = mapped_column(Text)
    ai_status: Mapped[ProcessingStatus] = mapped_column(
        Enum(ProcessingStatus, name="processing_status"), server_default=text("'pending'")
    )
    ai_level: Mapped[AiLevel | None] = mapped_column(Enum(AiLevel, name="ai_level"))
    ai_score: Mapped[int | None]
    ai_criteria: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb")
    )
    ai_reasons: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    ai_flags: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    ai_model: Mapped[str | None] = mapped_column(String(200))
    ai_prompt_version: Mapped[str | None] = mapped_column(String(100))
    ai_scored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class StageEvent(RecordMixin, SoftDeleteMixin, Base):
    __tablename__ = "stage_events"

    application_id: Mapped[UUID] = mapped_column(ForeignKey("applications.id"), index=True)
    from_stage: Mapped[ApplicationStage | None] = mapped_column(
        Enum(ApplicationStage, name="application_stage")
    )
    to_stage: Mapped[ApplicationStage] = mapped_column(
        Enum(ApplicationStage, name="application_stage")
    )
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    note: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class AiFeedback(RecordMixin, SoftDeleteMixin, Base):
    __tablename__ = "ai_feedback"
    __table_args__ = (
        UniqueConstraint("application_id", "user_id", name="uq_ai_feedback_application_user"),
        CheckConstraint("verdict IN ('agree', 'disagree')", name="ck_ai_feedback_verdict"),
    )

    application_id: Mapped[UUID] = mapped_column(ForeignKey("applications.id"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    verdict: Mapped[str] = mapped_column(String(8))
    corrected_level: Mapped[AiLevel | None] = mapped_column(Enum(AiLevel, name="ai_level"))
    comment: Mapped[str | None] = mapped_column(Text)

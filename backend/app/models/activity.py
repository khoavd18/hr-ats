from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, String, func, text
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import ActivityType
from app.models.mixins import RecordMixin, SoftDeleteMixin


class Activity(RecordMixin, SoftDeleteMixin, Base):
    __tablename__ = "activities"

    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    type: Mapped[ActivityType] = mapped_column(Enum(ActivityType, name="activity_type"))
    job_id: Mapped[UUID | None] = mapped_column(ForeignKey("jobs.id"), index=True)
    application_id: Mapped[UUID | None] = mapped_column(ForeignKey("applications.id"), index=True)
    candidate_id: Mapped[UUID | None] = mapped_column(ForeignKey("candidates.id"), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class AuditLog(RecordMixin, Base):
    __tablename__ = "audit_log"

    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(100))
    entity: Mapped[str] = mapped_column(String(100))
    entity_id: Mapped[UUID] = mapped_column(index=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    ip: Mapped[str | None] = mapped_column(INET)

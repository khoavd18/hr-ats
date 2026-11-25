from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

WEBHOOK_PATH_PATTERN = r"^/webhook/hr-ats/[a-z0-9-]+(/[a-z0-9-]+)*$"


class IntegrationToken(Base):
    __tablename__ = "integration_tokens"
    __table_args__ = (
        CheckConstraint(
            "cardinality(scopes) BETWEEN 1 AND 3 AND "
            "scopes <@ ARRAY['tasks:create', 'reports:summary', 'cv:upload']::varchar[] "
            "AND array_position(scopes, NULL::varchar) IS NULL",
            name="ck_integration_token_scopes",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    sponsor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64))
    scopes: Mapped[list[str]] = mapped_column(ARRAY(String))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WebhookEndpoint(Base):
    __tablename__ = "webhook_endpoints"
    __table_args__ = (
        UniqueConstraint("path", name="uq_webhook_endpoint_path"),
        CheckConstraint(f"path ~ '{WEBHOOK_PATH_PATTERN}'", name="ck_webhook_endpoint_path"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    path: Mapped[str] = mapped_column(String(200))
    enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))


class IntegrationEvent(Base):
    __tablename__ = "integration_events"
    __table_args__ = (
        UniqueConstraint(
            "endpoint_id", "event_type", "dedupe_key", name="uq_integration_event_delivery"
        ),
        CheckConstraint("attempts BETWEEN 0 AND 4", name="ck_integration_event_attempts"),
        CheckConstraint(
            "delivered_at IS NULL OR failed_at IS NULL", name="ck_integration_event_outcome"
        ),
        CheckConstraint("jsonb_typeof(payload) = 'object'", name="ck_integration_event_payload"),
        Index(
            "ix_integration_event_pending",
            "next_attempt_at",
            "id",
            postgresql_where=text("delivered_at IS NULL AND failed_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    endpoint_id: Mapped[UUID] = mapped_column(ForeignKey("webhook_endpoints.id"))
    event_type: Mapped[str] = mapped_column(String(64))
    dedupe_key: Mapped[UUID]
    payload: Mapped[dict[str, int]] = mapped_column(JSONB)
    attempts: Mapped[int] = mapped_column(server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OverdueWebhookEvent(Base):
    __tablename__ = "overdue_webhook_events"
    __table_args__ = (
        UniqueConstraint("user_id", "reminder_day", name="uq_overdue_webhook_user_day"),
        CheckConstraint("overdue_count > 0", name="ck_overdue_webhook_positive_count"),
        CheckConstraint("attempts >= 0", name="ck_overdue_webhook_attempts"),
        Index(
            "ix_overdue_webhook_pending",
            "user_id",
            "next_attempt_at",
            postgresql_where=text("delivered_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    reminder_day: Mapped[date]
    overdue_count: Mapped[int]
    attempts: Mapped[int] = mapped_column(server_default=text("0"))
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

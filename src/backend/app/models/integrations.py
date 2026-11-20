from datetime import date, datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


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

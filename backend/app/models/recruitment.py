"""Human-maintained interview, offer and placement records."""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.mixins import RecordMixin, SoftDeleteMixin


class Interview(RecordMixin, SoftDeleteMixin, Base):
    __tablename__ = "interviews"
    __table_args__ = (
        CheckConstraint("round > 0", name="ck_interviews_round"),
        CheckConstraint("duration_minutes BETWEEN 1 AND 1440", name="ck_interviews_duration"),
        CheckConstraint(
            "result IN ('pending', 'pass', 'fail', 'no_show')", name="ck_interviews_result"
        ),
        CheckConstraint("jsonb_typeof(interviewers) = 'array'", name="ck_interviews_interviewers"),
    )

    application_id: Mapped[UUID] = mapped_column(ForeignKey("applications.id"), index=True)
    round: Mapped[int]
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    duration_minutes: Mapped[int]
    location_or_link: Mapped[str | None] = mapped_column(Text)
    interviewers: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    result: Mapped[str] = mapped_column(String(10), server_default=text("'pending'"))
    feedback: Mapped[str | None] = mapped_column(Text)


class Offer(RecordMixin, SoftDeleteMixin, Base):
    __tablename__ = "offers"
    __table_args__ = (
        CheckConstraint("salary >= 0", name="ck_offers_salary"),
        CheckConstraint(
            "status IN ('draft', 'sent', 'accepted', 'declined')", name="ck_offers_status"
        ),
        CheckConstraint(
            "(status = 'draft' AND sent_at IS NULL) OR (status <> 'draft' AND sent_at IS NOT NULL)",
            name="ck_offers_sent_at",
        ),
    )

    application_id: Mapped[UUID] = mapped_column(ForeignKey("applications.id"), index=True)
    salary: Mapped[int | None]
    start_date: Mapped[date | None]
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(8), server_default=text("'draft'"))
    notes: Mapped[str | None] = mapped_column(Text)


class Placement(RecordMixin, SoftDeleteMixin, Base):
    __tablename__ = "placements"
    __table_args__ = (
        UniqueConstraint("application_id", name="uq_placements_application"),
        CheckConstraint("fee_amount >= 0", name="ck_placements_fee"),
        CheckConstraint("guarantee_until >= start_date", name="ck_placements_guarantee"),
        CheckConstraint(
            "status IN ('active', 'left_in_guarantee', 'completed')", name="ck_placements_status"
        ),
    )

    application_id: Mapped[UUID] = mapped_column(ForeignKey("applications.id"))
    start_date: Mapped[date]
    fee_amount: Mapped[int | None]
    guarantee_until: Mapped[date | None]
    status: Mapped[str] = mapped_column(String(17), server_default=text("'active'"))

"""Email templates and future human-confirmed delivery records (T22)."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import ApplicationStage, EmailStatus
from app.models.mixins import RecordMixin, SoftDeleteMixin


class EmailTemplate(RecordMixin, Base):
    __tablename__ = "email_templates"
    __table_args__ = (
        CheckConstraint(
            "requires_confirmation OR key = 'cv_received'", name="ck_email_templates_confirmation"
        ),
    )

    key: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    stage: Mapped[ApplicationStage | None] = mapped_column(
        Enum(ApplicationStage, name="application_stage")
    )
    subject: Mapped[str] = mapped_column(String(500))
    body: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))
    requires_confirmation: Mapped[bool] = mapped_column(server_default=text("true"))


class EmailMessage(RecordMixin, SoftDeleteMixin, Base):
    __tablename__ = "email_messages"
    __table_args__ = (CheckConstraint("jsonb_typeof(cc) = 'array'", name="ck_email_messages_cc"),)

    application_id: Mapped[UUID | None] = mapped_column(ForeignKey("applications.id"), index=True)
    template_id: Mapped[UUID | None] = mapped_column(ForeignKey("email_templates.id"), index=True)
    to_email: Mapped[str] = mapped_column(String(254))
    cc: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    subject: Mapped[str] = mapped_column(String(500))
    body_html: Mapped[str] = mapped_column(Text)
    status: Mapped[EmailStatus] = mapped_column(
        Enum(EmailStatus, name="email_status"), server_default=text("'draft'::email_status")
    )
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    message_id: Mapped[str | None] = mapped_column(Text)

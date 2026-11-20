from datetime import date, datetime
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import get_settings
from app.models.base import Base
from app.models.enums import HiringUnitKind, JobStatus
from app.models.mixins import RecordMixin


class HiringUnit(RecordMixin, Base):
    __tablename__ = "hiring_units"

    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[HiringUnitKind] = mapped_column(Enum(HiringUnitKind, name="hiring_unit_kind"))
    contact_name: Mapped[str | None] = mapped_column(String(200))
    contact_email: Mapped[str | None] = mapped_column(String(254))
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))


class Job(RecordMixin, Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint("headcount > 0", name="ck_jobs_headcount"),
        CheckConstraint("salary_min >= 0 AND salary_max >= 0", name="ck_jobs_salary_nonnegative"),
        CheckConstraint("salary_min <= salary_max", name="ck_jobs_salary_range"),
    )

    hiring_unit_id: Mapped[UUID] = mapped_column(ForeignKey("hiring_units.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    must_have: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    nice_to_have: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    location: Mapped[str | None] = mapped_column(String(200))
    employment_type: Mapped[str | None] = mapped_column(String(100))
    salary_min: Mapped[int | None]
    salary_max: Mapped[int | None]
    headcount: Mapped[int] = mapped_column(server_default=text("1"))
    deadline: Mapped[date | None]
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status"), server_default=text("'draft'"), index=True
    )
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    embedding: Mapped[list[float] | None] = mapped_column(Vector(get_settings().embedding_dim))


class JobMember(RecordMixin, Base):
    __tablename__ = "job_members"
    __table_args__ = (UniqueConstraint("job_id", "user_id", name="uq_job_members_job_user"),)

    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)

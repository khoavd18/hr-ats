from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import TaskStatus
from app.models.mixins import RecordMixin, SoftDeleteMixin


class Task(RecordMixin, SoftDeleteMixin, Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint("length(trim(title)) > 0", name="ck_tasks_title"),
        CheckConstraint(
            "(status = 'done') = (completed_at IS NOT NULL)", name="ck_tasks_completed"
        ),
        CheckConstraint("application_id IS NULL OR job_id IS NOT NULL", name="ck_tasks_job"),
        Index("ix_tasks_assignee_status_due", "assignee_id", "status", "due_at"),
    )

    title: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    assignee_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    job_id: Mapped[UUID | None] = mapped_column(ForeignKey("jobs.id"), index=True)
    application_id: Mapped[UUID | None] = mapped_column(ForeignKey("applications.id"), index=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, name="task_status"), server_default=text("'todo'")
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, StringConstraints, field_validator

from app.models.enums import TaskStatus
from app.schemas.users import InputModel

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Description = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10000)
]


class TaskCreate(InputModel):
    title: Title
    description: Description | None = None
    assignee_id: UUID | None = None
    job_id: UUID | None = None
    application_id: UUID | None = None
    due_at: AwareDatetime | None = None


class TaskPatch(InputModel):
    title: Title | None = None
    description: Description | None = None
    due_at: AwareDatetime | None = None
    status: TaskStatus | None = None

    @field_validator("title", "status")
    @classmethod
    def not_null(cls, value):
        if value is None:
            raise ValueError("Required value")
        return value


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    title: str
    description: str | None
    assignee_id: UUID
    created_by: UUID
    job_id: UUID | None
    application_id: UUID | None
    due_at: datetime | None
    status: TaskStatus
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TaskList(BaseModel):
    items: list[TaskRead]
    total: int


class TaskApplicationChoice(BaseModel):
    id: UUID
    job_id: UUID
    name: str


class TaskApplicationOptions(BaseModel):
    items: list[TaskApplicationChoice]
    total: int


class OverviewInterview(BaseModel):
    id: UUID
    application_id: UUID
    job_id: UUID
    candidate_name: str
    job_title: str
    scheduled_at: datetime


class OverviewJob(BaseModel):
    id: UUID
    title: str
    deadline: str


class Overview(BaseModel):
    today_tasks: TaskList
    interviews: list[OverviewInterview]
    interview_total: int
    jobs: list[OverviewJob]
    job_total: int
    unseen_cv_count: int

"""T13 inputs and public Job contracts; vectors and user contacts stay internal."""

from datetime import date
from typing import Annotated, Self
from uuid import UUID

from pydantic import Field, StringConstraints, field_validator, model_validator

from app.models.enums import HiringUnitKind, JobStatus
from app.schemas.core import HiringUnitRead, JobRead
from app.schemas.ranking import AiCounts
from app.schemas.users import EmailInput, InputModel

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Requirement = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
Requirements = Annotated[list[Requirement], Field(max_length=100)]


class HiringUnitCreate(InputModel):
    name: Name
    kind: HiringUnitKind
    contact_name: Name | None = None
    contact_email: str | None = Field(default=None, max_length=254)
    notes: str | None = Field(default=None, max_length=10000)
    is_active: bool = True

    @field_validator("contact_email")
    @classmethod
    def valid_email(cls, value: str | None) -> str | None:
        return EmailInput(email=value).email if value is not None else None


class HiringUnitPatch(InputModel):
    name: Name | None = None
    kind: HiringUnitKind | None = None
    contact_name: Name | None = None
    contact_email: str | None = Field(default=None, max_length=254)
    notes: str | None = Field(default=None, max_length=10000)
    is_active: bool | None = None

    @field_validator("contact_email")
    @classmethod
    def valid_email(cls, value: str | None) -> str | None:
        return EmailInput(email=value).email if value is not None else None

    @field_validator("name", "kind", "is_active")
    @classmethod
    def not_null(cls, value):
        if value is None:
            raise ValueError("Null not permitted")
        return value


class HiringUnitList(InputModel):
    items: list[HiringUnitRead]
    total: int


class JobCreate(InputModel):
    hiring_unit_id: UUID
    title: Name
    description: str = Field(default="", max_length=50000)
    must_have: Requirements = Field(default_factory=list)
    nice_to_have: Requirements = Field(default_factory=list)
    location: str | None = Field(default=None, max_length=200)
    employment_type: str | None = Field(default=None, max_length=100)
    salary_min: int | None = Field(default=None, ge=0, le=2147483647)
    salary_max: int | None = Field(default=None, ge=0, le=2147483647)
    headcount: int = Field(default=1, ge=1, le=2147483647)
    deadline: date | None = None
    status: JobStatus = JobStatus.draft
    owner_id: UUID
    member_ids: list[UUID] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def business_rules(self) -> Self:
        if (
            self.salary_min is not None
            and self.salary_max is not None
            and self.salary_min > self.salary_max
        ):
            raise ValueError("Salary range invalid")
        if self.status == JobStatus.open and not self.must_have:
            raise ValueError("Open Job requires must_have")
        return self


class JobPatch(InputModel):
    hiring_unit_id: UUID | None = None
    title: Name | None = None
    description: str | None = Field(default=None, max_length=50000)
    must_have: Requirements | None = None
    nice_to_have: Requirements | None = None
    location: str | None = Field(default=None, max_length=200)
    employment_type: str | None = Field(default=None, max_length=100)
    salary_min: int | None = Field(default=None, ge=0, le=2147483647)
    salary_max: int | None = Field(default=None, ge=0, le=2147483647)
    headcount: int | None = Field(default=None, ge=1, le=2147483647)
    deadline: date | None = None
    status: JobStatus | None = None
    owner_id: UUID | None = None
    member_ids: list[UUID] | None = Field(default=None, max_length=100)

    @field_validator(
        "hiring_unit_id",
        "title",
        "description",
        "must_have",
        "nice_to_have",
        "headcount",
        "status",
        "owner_id",
        "member_ids",
    )
    @classmethod
    def not_null(cls, value):
        if value is None:
            raise ValueError("Null not permitted")
        return value


class JobMembersInput(InputModel):
    user_ids: list[UUID] = Field(max_length=100)


class JobResponse(JobRead):
    hiring_unit_name: str
    owner_name: str
    member_ids: list[UUID]
    needs_rescore: bool = False
    ai_counts: AiCounts = Field(default_factory=AiCounts)


class JobList(InputModel):
    items: list[JobResponse]
    total: int


class Choice(InputModel):
    id: UUID
    name: str


class JobOptions(InputModel):
    hiring_units: list[Choice]
    users: list[Choice]

from datetime import date, datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import (
    AwareDatetime,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.schemas.users import InputModel

NoteText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10000)]
PositiveInt = Annotated[int, Field(strict=True, ge=1, le=2147483647)]
Duration = Annotated[int, Field(strict=True, ge=1, le=1440)]
Money = Annotated[int, Field(strict=True, ge=0, le=2147483647)]
InterviewResult = Literal["pending", "pass", "fail", "no_show"]
OfferStatus = Literal["draft", "sent", "accepted", "declined"]
PlacementStatus = Literal["active", "left_in_guarantee", "completed"]


def trim_interviewers(values: list[str]) -> list[str]:
    if any(not v.strip() for v in values):
        raise ValueError("Empty interviewer")
    return [v.strip() for v in values]


class InterviewCreate(InputModel):
    round: PositiveInt = 1
    scheduled_at: AwareDatetime
    duration_minutes: Duration = 60
    location_or_link: NoteText | None = None
    interviewers: list[Annotated[str, Field(min_length=1, max_length=254)]] = Field(
        default_factory=list, max_length=50
    )

    _names = field_validator("interviewers")(trim_interviewers)


class InterviewPatch(InputModel):
    round: PositiveInt | None = None
    scheduled_at: AwareDatetime | None = None
    duration_minutes: Duration | None = None
    location_or_link: NoteText | None = None
    interviewers: list[Annotated[str, Field(min_length=1, max_length=254)]] | None = Field(
        default=None, max_length=50
    )
    result: InterviewResult | None = None
    feedback: NoteText | None = None

    @field_validator("round", "scheduled_at", "duration_minutes", "result", "interviewers")
    @classmethod
    def not_null(cls, value):
        if value is None:
            raise ValueError("Required value")
        return value

    _names = field_validator("interviewers")(trim_interviewers)


class OfferCreate(InputModel):
    salary: Money | None = None
    start_date: date | None = None
    status: Literal["draft", "sent"] = "draft"
    notes: NoteText | None = None


class OfferPatch(InputModel):
    salary: Money | None = None
    start_date: date | None = None
    status: OfferStatus | None = None
    notes: NoteText | None = None

    @field_validator("status")
    @classmethod
    def not_null(cls, value):
        if value is None:
            raise ValueError("Required value")
        return value


class PlacementCreate(InputModel):
    start_date: date
    fee_amount: Money | None = None
    guarantee_until: date | None = None

    @model_validator(mode="after")
    def valid_guarantee(self) -> Self:
        if self.guarantee_until is not None and self.guarantee_until < self.start_date:
            raise ValueError("Invalid guarantee")
        return self


class PlacementPatch(InputModel):
    start_date: date | None = None
    fee_amount: Money | None = None
    guarantee_until: date | None = None
    status: PlacementStatus | None = None

    @field_validator("start_date", "status")
    @classmethod
    def not_null(cls, value):
        if value is None:
            raise ValueError("Required value")
        return value


class RecordRead(InputModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)
    id: UUID
    application_id: UUID
    created_at: datetime
    updated_at: datetime


class InterviewRead(RecordRead):
    round: int
    scheduled_at: datetime
    duration_minutes: int
    location_or_link: str | None
    interviewers: list[str]
    result: InterviewResult
    feedback: str | None


class OfferRead(RecordRead):
    salary: int | None
    start_date: date | None
    sent_at: datetime | None
    status: OfferStatus
    notes: str | None


class PlacementRead(RecordRead):
    start_date: date
    fee_amount: int | None
    guarantee_until: date | None
    status: PlacementStatus


class RecruitmentRecords(InputModel):
    interviews: list[InterviewRead]
    offers: list[OfferRead]
    placement: PlacementRead | None


class InterviewList(InputModel):
    items: list[InterviewRead]
    total: int

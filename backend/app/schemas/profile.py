"""Authorized profile detail and validated human corrections."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, StringConstraints, field_validator, model_validator

from app.models.enums import AiLevel, ProcessingStatus
from app.schemas.core import ActivityRead, AiFeedbackRead, ApplicationRead, CandidateRead
from app.schemas.users import EmailInput, InputModel

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
NoteText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10000)]


class FeedbackInput(InputModel):
    verdict: Literal["agree", "disagree"]
    corrected_level: AiLevel | None = None
    comment: NoteText | None = None

    @model_validator(mode="after")
    def correction(self) -> Self:
        if self.verdict == "disagree" and self.corrected_level is None:
            raise ValueError("Correction required")
        if self.verdict == "agree" and self.corrected_level is not None:
            raise ValueError("Unexpected correction")
        return self


class NoteInput(InputModel):
    text: NoteText


class CandidatePatch(InputModel):
    full_name: ShortText | None = None
    email: str | None = Field(default=None, max_length=254)
    phone: Annotated[str, StringConstraints(strip_whitespace=True, max_length=50)] | None = None
    location: ShortText | None = None
    current_title: ShortText | None = None
    years_experience: Decimal | None = Field(
        default=None, ge=0, le=Decimal("9999.99"), decimal_places=2
    )
    skills: list[ShortText] = Field(default_factory=list, max_length=100)

    @field_validator("full_name")
    @classmethod
    def required_name(cls, value):
        if value is None:
            raise ValueError("Name required")
        return value

    @field_validator("email")
    @classmethod
    def email_format(cls, value: str | None) -> str | None:
        return EmailInput(email=value).email if value is not None else None


class ProfileFile(InputModel):
    id: UUID
    mime_type: str
    status: ProcessingStatus
    extracted_text: str | None


class ProfileActivity(ActivityRead):
    actor_name: str | None


class ApplicationDetail(InputModel):
    application: ApplicationRead
    candidate: CandidateRead
    cv_files: list[ProfileFile]
    feedback: AiFeedbackRead | None
    activities: list[ProfileActivity]
    loaded_at: datetime

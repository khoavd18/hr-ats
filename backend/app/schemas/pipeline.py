"""Human stage changes and the minimal cards needed by the Job pipeline."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, StringConstraints, model_validator

from app.models.enums import AiLevel, ApplicationStage, ProcessingStatus
from app.schemas.core import ApplicationRead
from app.schemas.users import InputModel


class RejectedReason(StrEnum):
    missing_skills = "thiếu kỹ năng"
    missing_experience = "thiếu kinh nghiệm"
    salary_mismatch = "lương không phù hợp"
    no_response = "ứng viên không phản hồi"
    hiring_unit_declined = "đơn vị tuyển từ chối"
    other = "khác"


class MoveInput(InputModel):
    to_stage: ApplicationStage
    note: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10000)]
        | None
    ) = None
    rejected_reason: RejectedReason | None = None

    @model_validator(mode="after")
    def rejection(self) -> Self:
        if (self.to_stage == ApplicationStage.rejected) != (self.rejected_reason is not None):
            raise ValueError("Rejection reason required only for rejected stage")
        return self


class MoveResponse(BaseModel):
    application: ApplicationRead
    suggested_email: Literal[None] = None


class StageLabel(BaseModel):
    code: ApplicationStage
    label: str


class PipelineCard(BaseModel):
    id: UUID
    candidate_id: UUID
    candidate_name: str
    stage: ApplicationStage
    stage_entered_at: datetime
    owner_id: UUID
    ai_status: ProcessingStatus
    ai_level: AiLevel | None


class PipelineColumn(BaseModel):
    stage: ApplicationStage
    items: list[PipelineCard]
    total: int


class JobPipeline(BaseModel):
    columns: list[PipelineColumn]
    total: int

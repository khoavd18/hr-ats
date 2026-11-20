"""Read contracts. Raw CV contents, storage paths, search vectors and embeddings stay internal."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, IPvAnyAddress

from app.models.enums import (
    ActivityType,
    AiLevel,
    ApplicationStage,
    CandidateSource,
    ExtractionMethod,
    HiringUnitKind,
    JobStatus,
    ProcessingStatus,
)


class RecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, hide_input_in_errors=True)

    id: UUID
    created_at: datetime
    updated_at: datetime


class SoftDeletedRead(RecordRead):
    deleted_at: datetime | None


class HiringUnitRead(RecordRead):
    name: str
    kind: HiringUnitKind
    contact_name: str | None
    contact_email: str | None
    notes: str | None
    is_active: bool


class JobRead(RecordRead):
    hiring_unit_id: UUID
    title: str
    description: str
    must_have: list[str]
    nice_to_have: list[str]
    location: str | None
    employment_type: str | None
    salary_min: int | None
    salary_max: int | None
    headcount: int
    deadline: date | None
    status: JobStatus
    owner_id: UUID
    opened_at: datetime | None
    closed_at: datetime | None


class JobMemberRead(RecordRead):
    job_id: UUID
    user_id: UUID


class CandidateRead(SoftDeletedRead):
    full_name: str
    email: str | None
    phone: str | None
    location: str | None
    current_title: str | None
    years_experience: Decimal | None
    skills: list[str]
    languages: list[Any]
    education: list[Any]
    experiences: list[Any]
    source: CandidateSource
    consent_at: datetime | None
    consent_note: str | None
    retention_until: date
    merged_into_id: UUID | None


class CvFileRead(SoftDeletedRead):
    candidate_id: UUID | None
    original_filename: str
    mime_type: str
    size_bytes: int
    sha256: str
    extraction_method: ExtractionMethod | None
    page_count: int | None
    status: ProcessingStatus
    parse_model: str | None
    parse_prompt_version: str | None
    uploaded_by: UUID | None
    job_id: UUID | None


class ApplicationRead(SoftDeletedRead):
    candidate_id: UUID
    job_id: UUID
    stage: ApplicationStage
    stage_entered_at: datetime
    owner_id: UUID
    rejected_reason: str | None
    ai_status: ProcessingStatus
    ai_level: AiLevel | None
    ai_score: int | None
    ai_criteria: list[dict[str, Any]]
    ai_reasons: list[str]
    ai_flags: list[str]
    ai_model: str | None
    ai_prompt_version: str | None
    ai_scored_at: datetime | None


class StageEventRead(SoftDeletedRead):
    application_id: UUID
    from_stage: ApplicationStage | None
    to_stage: ApplicationStage
    actor_id: UUID
    note: str | None
    occurred_at: datetime


class AiFeedbackRead(SoftDeletedRead):
    application_id: UUID
    user_id: UUID
    verdict: Literal["agree", "disagree"]
    corrected_level: AiLevel | None
    comment: str | None


class ActivityRead(SoftDeletedRead):
    actor_id: UUID | None
    type: ActivityType
    job_id: UUID | None
    application_id: UUID | None
    candidate_id: UUID | None
    payload: dict[str, Any]
    occurred_at: datetime


class AuditLogRead(RecordRead):
    actor_id: UUID
    action: str
    entity: str
    entity_id: UUID
    occurred_at: datetime
    ip: IPvAnyAddress | None

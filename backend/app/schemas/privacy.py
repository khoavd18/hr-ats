from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from app.schemas.users import InputModel


class ConsentInput(InputModel):
    consent_at: AwareDatetime
    note: str = Field(min_length=1, max_length=2000)
    extend_retention: bool = False

    @field_validator("note")
    @classmethod
    def evidence_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Evidence required")
        return value.strip()


class RetentionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    full_name: str | None
    consent_at: datetime | None
    retention_until: date
    expired_at: datetime | None
    purge_pending_at: datetime | None
    purged_at: datetime | None


class RetentionList(BaseModel):
    items: list[RetentionRead]
    total: int


class DataRequestInput(InputModel):
    candidate_id: UUID
    kind: Literal["delete"] = "delete"
    requested_by_note: str = Field(min_length=1, max_length=2000)

    @field_validator("requested_by_note")
    @classmethod
    def evidence_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Evidence required")
        return value.strip()


class DataRequestRead(BaseModel):
    candidate_name: str | None = None
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    candidate_id: UUID
    kind: str
    requested_by_note: str | None
    status: str
    handled_by: UUID | None
    handled_at: datetime | None
    created_at: datetime


class DataRequestList(BaseModel):
    items: list[DataRequestRead]
    total: int


class AuditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    actor_id: UUID | None
    action: str
    entity: str
    entity_id: UUID
    occurred_at: datetime


class AuditList(BaseModel):
    items: list[AuditRead]
    total: int

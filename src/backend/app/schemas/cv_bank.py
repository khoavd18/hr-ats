"""Shared-bank summaries deliberately exclude contacts, CV contents and Job membership."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import CandidateSource
from app.schemas.users import InputModel


class CandidateBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    current_title: str | None
    years_experience: Decimal | None
    skills: list[str]
    location: str | None
    source: CandidateSource
    created_at: datetime


class BankCandidate(CandidateBrief):
    possible_duplicate: CandidateBrief | None = None


class CandidateList(BaseModel):
    items: list[BankCandidate]
    total: int


class MergeInput(InputModel):
    into_id: UUID

"""Job ranking exposes only the candidate summary needed by the table."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from app.models.enums import AiLevel, ApplicationStage, ProcessingStatus


class AiCounts(BaseModel):
    high: int = 0
    medium: int = 0
    low: int = 0
    insufficient: int = 0
    pending: int = 0
    running: int = 0
    failed: int = 0


class RankedApplication(BaseModel):
    id: UUID
    candidate_id: UUID
    candidate_name: str
    skills: list[str]
    years_experience: Decimal | None
    stage: ApplicationStage
    created_at: datetime
    ai_status: ProcessingStatus
    ai_level: AiLevel | None


class ApplicationRanking(BaseModel):
    items: list[RankedApplication]
    total: int
    ai_counts: AiCounts

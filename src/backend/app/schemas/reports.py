"""Draft KPI contracts; ratios are fractions and undefined values remain null."""

import re
from datetime import date, datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import ActivityType, ApplicationStage


class ReportInput(BaseModel):
    model_config = {"extra": "forbid"}

    from_date: date = Field(alias="from")
    to_date: date = Field(alias="to")
    recruiter_id: UUID | None = None
    job_id: UUID | None = None
    hiring_unit_id: UUID | None = None

    @field_validator("from_date", "to_date", mode="before")
    @classmethod
    def calendar_date(cls, value):
        if isinstance(value, str) and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("Expected YYYY-MM-DD")
        return value

    @model_validator(mode="after")
    def ordered_dates(self) -> Self:
        if self.from_date == date.min or not 1 <= (self.to_date - self.from_date).days <= 366:
            raise ValueError("Expected a reporting period of 1 to 366 days")
        return self


class ReportPeriod(BaseModel):
    from_date: date
    to_date: date
    timezone: str = "Asia/Ho_Chi_Minh"
    as_of: datetime
    definition_status: Literal["draft"] = "draft"
    recruiter_id: UUID | None = None
    job_id: UUID | None = None
    hiring_unit_id: UUID | None = None


class InterviewMetric(BaseModel):
    total: int = 0
    elapsed: int = 0
    upcoming: int = 0


class MedianMetric(BaseModel):
    days: float | None = None
    sample_count: int = 0
    excluded_count: int = 0


class RevenueMetric(BaseModel):
    amount: int | None = None
    known_count: int = 0
    missing_count: int = 0


class AgreementMetric(BaseModel):
    agree: int = 0
    disagree: int = 0
    total: int = 0
    rate: float | None = None


class FunnelStage(BaseModel):
    stage: ApplicationStage
    count: int = 0
    next_stage: ApplicationStage | None = None
    next_count: int | None = None
    conversion_rate: float | None = None


class DailyCVs(BaseModel):
    date: date
    count: int


class Metrics(BaseModel):
    new_cvs: int = 0
    screened: int = 0
    submitted: int = 0
    interviews: InterviewMetric = Field(default_factory=InterviewMetric)
    offers: int = 0
    placements: int = 0
    funnel: list[FunnelStage] = Field(default_factory=list)
    time_to_fill: MedianMetric = Field(default_factory=MedianMetric)
    stage_duration: dict[ApplicationStage, MedianMetric] = Field(default_factory=dict)
    overdue_jobs: int = 0
    placement_revenue: RevenueMetric = Field(default_factory=RevenueMetric)
    ai_agreement: AgreementMetric = Field(default_factory=AgreementMetric)
    activities: dict[ActivityType, int] = Field(default_factory=dict)


class SummaryReport(BaseModel):
    period: ReportPeriod
    metrics: Metrics
    new_cvs_by_day: list[DailyCVs]


class FunnelReport(BaseModel):
    period: ReportPeriod
    stages: list[FunnelStage]


class AgreementReport(BaseModel):
    period: ReportPeriod
    agreement: AgreementMetric


class RecruiterMetrics(BaseModel):
    recruiter_id: UUID | None
    recruiter_name: str | None
    metrics: Metrics


class RecruitersReport(BaseModel):
    period: ReportPeriod
    items: list[RecruiterMetrics]

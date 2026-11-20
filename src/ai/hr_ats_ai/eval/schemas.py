"""Versioned contracts for synthetic fixtures; independent of production CV schemas."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Level = Literal["high", "medium", "low", "insufficient"]
Career = Literal["backend", "frontend", "accounting", "sales", "marketing", "hr"]
Layout = Literal["one_column", "two_column", "table", "avatar", "english", "scan"]
Month = Annotated[str, Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")]
Text = Annotated[str, Field(min_length=1)]


class FixtureModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Experience(FixtureModel):
    company: Text
    title: Text
    start: Month
    end: Month
    description: Text


class Education(FixtureModel):
    school: Text
    degree: Text
    major: Text
    start: Month
    end: Month


class CVLabel(FixtureModel):
    schema_version: Literal[1] = 1
    synthetic: Literal[True] = True
    id: Annotated[str, Field(pattern=r"^cv_\d{4,5}$")]
    file_name: Annotated[str, Field(pattern=r"^cv_\d{4,5}\.(pdf|docx)$")]
    layout: Layout
    language: Literal["vi", "en"]
    career: Career
    region: Literal["north", "central", "south"]
    gender: Literal["Nam", "Nữ"]
    full_name: Text
    email: Annotated[str, Field(pattern=r"^cv_\d{4,5}@example\.com$")]
    phone: Annotated[str, Field(pattern=r"^09\d{2} 000 \d{3}$")]
    date_of_birth: Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}$")]
    location: Text
    current_title: Text
    years_experience: Annotated[int, Field(ge=0)]
    skills: Annotated[list[Text], Field(min_length=1)]
    experience: Annotated[list[Experience], Field(min_length=1)]
    education: Annotated[list[Education], Field(min_length=1)]
    expected_level: Annotated[dict[str, Level], Field(min_length=5, max_length=5)]

    @model_validator(mode="after")
    def matching_file_id(self) -> "CVLabel":
        if self.file_name.rsplit(".", 1)[0] != self.id:
            raise ValueError("CV filename must match its label ID")
        return self


class Job(FixtureModel):
    id: Text
    title: Text
    description: Text
    must_have: Annotated[list[Text], Field(min_length=1)]
    nice_to_have: Annotated[list[Text], Field(min_length=1)]


class JobDataset(FixtureModel):
    schema_version: Literal[1] = 1
    synthetic: Literal[True] = True
    seed: int
    reference_date: Literal["2026-01-01"] = "2026-01-01"
    jobs: Annotated[list[Job], Field(min_length=5, max_length=5)]
    expected_level: Annotated[dict[str, dict[str, Level]], Field(min_length=1)]

    @model_validator(mode="after")
    def complete_job_matrix(self) -> "JobDataset":
        job_ids = {job.id for job in self.jobs}
        if len(job_ids) != 5 or any(set(row) != job_ids for row in self.expected_level.values()):
            raise ValueError("Expected levels must cover each unique Job")
        return self

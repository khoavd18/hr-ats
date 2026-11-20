"""Version-one LLM outputs. Contact details stay local; scores are computed in T12."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Month = Annotated[str, Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")]
Text = Annotated[str, Field(pattern=r"\S")]


class AIOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)


class ParseBasic(AIOutput):
    full_name: Text | None
    current_title: Text | None
    location: Text | None
    years_experience: Annotated[float, Field(ge=0, allow_inf_nan=False)] | None
    languages: list[Text]


class Experience(AIOutput):
    company: Text | None
    title: Text | None
    start: Month | None
    end: Month | None
    description: Text | None


class Education(AIOutput):
    school: Text | None
    degree: Text | None
    major: Text | None
    start: Month | None
    end: Month | None


class ParseExperience(AIOutput):
    experiences: list[Experience]
    education: list[Education]


class ParseSkills(AIOutput):
    skills: list[Text]

    @field_validator("skills")
    @classmethod
    def normalize_skills(cls, values: list[str]) -> list[str]:
        aliases = {
            "js": "javascript",
            "ts": "typescript",
            "nodejs": "node.js",
            "reactjs": "react",
            "postgres": "postgresql",
        }
        normalized = [
            aliases.get(value.strip().casefold(), value.strip().casefold()) for value in values
        ]
        if any(not value for value in normalized):
            raise ValueError("Empty skill")
        return list(dict.fromkeys(normalized))


class ParsedCV(ParseBasic, ParseExperience, ParseSkills):
    """Merged parse output; contact details never enter the LLM schema."""


class CriterionJudgment(AIOutput):
    criterion: Text
    kind: Literal["must", "nice"]
    result: Literal["met", "partial", "not_met", "unknown"]
    evidence: Text | None

    @field_validator("evidence")
    @classmethod
    def short_evidence(cls, value: str | None) -> str | None:
        if value is not None and len(value.split()) > 20:
            raise ValueError("Evidence exceeds 20 words")
        return value


class ScoreOutput(AIOutput):
    criteria: list[CriterionJudgment]
    reasons: Annotated[list[Text], Field(min_length=2, max_length=3)]
    flags: list[
        Literal["job_hopping", "employment_gap", "missing_must_have", "overqualified", "unclear_cv"]
    ]

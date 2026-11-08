import pytest
from pydantic import ValidationError

from app.ai.schemas import (
    CriterionJudgment,
    Experience,
    ParseBasic,
    ParseExperience,
    ParseSkills,
    ScoreOutput,
)


def test_missing_information_is_explicit_and_contacts_are_not_llm_output():
    basic = ParseBasic(
        full_name=None, current_title=None, location=None, years_experience=None, languages=[]
    )
    assert basic.full_name is None
    assert ParseExperience(experiences=[], education=[]).education == []
    with pytest.raises(ValidationError):
        ParseBasic.model_validate({**basic.model_dump(), "email": "synthetic@example.invalid"})
    with pytest.raises(ValidationError):
        ParseBasic.model_validate({"full_name": None})


@pytest.mark.parametrize("years", [-1, float("nan"), float("inf"), "3", True])
def test_years_experience_is_a_finite_nonnegative_number(years):
    with pytest.raises(ValidationError):
        ParseBasic(
            full_name=None, current_title=None, location=None, years_experience=years, languages=[]
        )


@pytest.mark.parametrize("month", ["2024", "2024-00", "2024-13", "01/2024", "present"])
def test_experience_dates_require_year_and_month(month):
    with pytest.raises(ValidationError):
        Experience(company=None, title=None, start=month, end=None, description=None)


def test_valid_dates_and_skill_normalization():
    assert (
        Experience(company=None, title=None, start="2024-01", end=None, description=None).start
        == "2024-01"
    )
    assert ParseSkills(skills=[" JS ", "javascript", "SQL", "ReactJS", "Postgres"]).skills == [
        "javascript",
        "sql",
        "react",
        "postgresql",
    ]
    with pytest.raises(ValidationError):
        ParseSkills(skills=[" "])


@pytest.mark.parametrize(
    "field,value", [("kind", "required"), ("result", "approved"), ("evidence", "x " * 21)]
)
def test_criterion_enums_and_evidence_word_limit(field, value):
    data = {"criterion": "Python", "kind": "must", "result": "unknown", "evidence": None}
    with pytest.raises(ValidationError):
        CriterionJudgment.model_validate({**data, field: value})


def test_score_reasons_flags_and_no_provider_generated_score():
    good = {"criteria": [], "reasons": ["Lý do giả một.", "Lý do giả hai."], "flags": []}
    assert ScoreOutput.model_validate(good).flags == []
    for changes in (
        {"reasons": ["Một câu."]},
        {"reasons": ["Giả"] * 4},
        {"flags": ["reject"]},
        {"ai_score": 100},
    ):
        with pytest.raises(ValidationError):
            ScoreOutput.model_validate({**good, **changes})


@pytest.mark.parametrize("schema", [ParseBasic, ParseExperience, ParseSkills, ScoreOutput])
def test_provider_schema_has_required_properties_and_closed_objects(schema):
    document = schema.model_json_schema()

    def check(value):
        if isinstance(value, dict):
            if value.get("type") == "object":
                assert value["additionalProperties"] is False
                assert set(value["required"]) == set(value["properties"])
            for child in value.values():
                check(child)
        elif isinstance(value, list):
            for child in value:
                check(child)

    check(document)

import pytest

from app.ai.schemas import CriterionJudgment
from app.ai.scoring_rules import ScoringRules, compute_score
from app.core.config import Settings


def judgments(must, nice=()):
    return [
        CriterionJudgment(
            criterion=f"Tiêu chí giả {index}", kind=kind, result=result, evidence=None
        )
        for kind, items in (("must", must), ("nice", nice))
        for index, result in enumerate(items)
    ]


@pytest.mark.parametrize(
    "must,nice,length,score,level",
    [
        (["met"], ["met"], 300, 100, "high"),
        (["met"], ["not_met"], 300, 75, "high"),
        (["partial"], ["met"], 300, 62, "medium"),
        (["partial"], [], 300, 50, "medium"),
        (["met"], ["partial"], 300, 88, "high"),
        (["met", "partial"], [], 300, 75, "high"),
        (["met", "not_met"], ["met"], 300, 62, "low"),
        (["not_met"], [], 300, 0, "low"),
        (["unknown", "met"], [], 300, 50, "insufficient"),
        (["met"], ["unknown"], 300, 75, "insufficient"),
        (["unknown", "met", "met"], [], 300, 67, "medium"),
        (["unknown", "not_met"], [], 300, 0, "insufficient"),
        (["unknown", "unknown"], [], 300, 0, "insufficient"),
        (["met"], [], 299, 100, "insufficient"),
        (["not_met"], [], 299, 0, "insufficient"),
        ([], [], 500, 0, "insufficient"),
        ([], ["met"], 300, 25, "medium"),
    ],
)
def test_formula_levels_thresholds_and_precedence(must, nice, length, score, level):
    result = compute_score(judgments(must, nice), "x" * length)
    assert (result.score, result.level) == (score, level)


def test_custom_rules_and_settings_environment(monkeypatch):
    monkeypatch.setenv("SCORE_MUST_WEIGHT", "0.5")
    monkeypatch.setenv("SCORE_PARTIAL_VALUE", "0.25")
    monkeypatch.setenv("SCORE_HIGH_THRESHOLD", "40")
    monkeypatch.setenv("SCORE_UNKNOWN_THRESHOLD", "0.75")
    monkeypatch.setenv("SCORE_MIN_TEXT_LENGTH", "1")
    settings = Settings(_env_file=None)
    rules = ScoringRules(
        **{
            key.removeprefix("score_"): value
            for key, value in settings.model_dump().items()
            if key.startswith("score_")
        }
    )
    result = compute_score(judgments(["partial"], ["met"]), "x", rules=rules)
    assert (result.score, result.level) == (62, "high")
    result = compute_score(judgments(["unknown", "met"]), "x", rules=rules)
    assert result.level == "high"


@pytest.mark.parametrize(
    "option,value",
    [
        ("must_weight", -0.1),
        ("must_weight", 1.1),
        ("partial_value", float("nan")),
        ("partial_value", -1),
        ("high_threshold", 101),
        ("unknown_threshold", 0),
        ("unknown_threshold", 1.1),
        ("min_text_length", -1),
    ],
)
def test_invalid_rules_are_rejected(option, value):
    with pytest.raises(ValueError):
        ScoringRules(**{option: value})


@pytest.mark.parametrize(
    "option,value",
    [
        ("score_must_weight", float("inf")),
        ("score_unknown_threshold", 0),
        ("score_partial_value", -1),
        ("score_high_threshold", 101),
        ("score_min_text_length", -1),
    ],
)
def test_invalid_environment_settings_are_rejected(option, value):
    with pytest.raises(ValueError):
        Settings(_env_file=None, **{option: value})

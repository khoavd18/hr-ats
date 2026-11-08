"""Local, deterministic scoring. The LLM never chooses a score or stage."""

from dataclasses import dataclass

from app.ai.schemas import CriterionJudgment
from app.models.enums import AiLevel

MUST_WEIGHT = 0.75
PARTIAL_VALUE = 0.5
HIGH_THRESHOLD = 75
UNKNOWN_THRESHOLD = 0.5
MIN_TEXT_LENGTH = 300


@dataclass(frozen=True)
class ScoringRules:
    must_weight: float = MUST_WEIGHT
    partial_value: float = PARTIAL_VALUE
    high_threshold: int = HIGH_THRESHOLD
    unknown_threshold: float = UNKNOWN_THRESHOLD
    min_text_length: int = MIN_TEXT_LENGTH

    def __post_init__(self) -> None:
        if not (
            0 <= self.must_weight <= 1
            and 0 <= self.partial_value <= 1
            and 0 <= self.high_threshold <= 100
            and 0 < self.unknown_threshold <= 1
            and self.min_text_length >= 0
        ):
            raise ValueError("Invalid scoring rules")


@dataclass(frozen=True)
class ComputedScore:
    score: int
    level: AiLevel


def compute_score(
    criteria: list[CriterionJudgment], anonymized_text: str, *, rules: ScoringRules | None = None
) -> ComputedScore:
    rules = rules if rules is not None else ScoringRules()
    values = {"met": 1.0, "partial": rules.partial_value, "not_met": 0.0, "unknown": 0.0}
    must = [values[c.result] for c in criteria if c.kind == "must"]
    nice = [values[c.result] for c in criteria if c.kind == "nice"]
    must_score = sum(must) / len(must) if must else 0.0
    nice_score = sum(nice) / len(nice) if nice else must_score
    score = round(100 * (rules.must_weight * must_score + (1 - rules.must_weight) * nice_score))
    if (
        not criteria
        or len(anonymized_text) < rules.min_text_length
        or sum(c.result == "unknown" for c in criteria) / len(criteria) >= rules.unknown_threshold
    ):
        level = AiLevel.insufficient
    elif any(c.kind == "must" and c.result == "not_met" for c in criteria):
        level = AiLevel.low
    elif score >= rules.high_threshold:
        level = AiLevel.high
    else:
        level = AiLevel.medium
    return ComputedScore(score, level)

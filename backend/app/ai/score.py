"""Judge only anonymized CV text, validate coverage and ground every judgment."""

import unicodedata
from dataclasses import dataclass, field

from app.ai.llm import LLMClient, LLMValidationError, get_llm_client
from app.ai.prompts import load_prompt
from app.ai.schemas import ScoreOutput


def normalize_evidence(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).split())


@dataclass(frozen=True)
class ScoreResult:
    judged: ScoreOutput = field(repr=False)
    model: str
    prompt_version: str


def score_cv(
    anonymized_text: str,
    *,
    job_title: str,
    job_description: str,
    must_have: list[str],
    nice_to_have: list[str],
    client: LLMClient | None = None,
    version: int = 1,
) -> ScoreResult:
    """Caller supplies anonymized_text only. Never read raw CV or parsed identity here."""
    client = client if client is not None else get_llm_client()
    prompt = load_prompt("score_cv", version).render(
        anonymized_text=anonymized_text,
        job_title=job_title,
        job_description=job_description,
        must_have=must_have,
        nice_to_have=nice_to_have,
    )
    output = client.complete_json(
        system=prompt.system, user=prompt.user, schema=ScoreOutput, temperature=0
    )
    expected = [
        (kind, value)
        for kind, items in (("must", must_have), ("nice", nice_to_have))
        for value in items
    ]
    if [(c.kind, c.criterion) for c in output.criteria] != expected:
        raise LLMValidationError()
    text = normalize_evidence(anonymized_text)
    criteria = []
    for criterion in output.criteria:
        evidence = normalize_evidence(criterion.evidence or "")
        if not evidence or evidence not in text:
            criterion = criterion.model_copy(update={"result": "unknown", "evidence": None})
        criteria.append(criterion)
    judged = output.model_copy(update={"criteria": criteria})
    return ScoreResult(judged, client.model, prompt.prompt_version)

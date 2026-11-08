"""Three independent parse calls, with the bounded retries owned by the adapter."""

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field

from pydantic import BaseModel

from app.ai.llm import LLMClient, get_llm_client
from app.ai.prompts import load_prompt
from app.ai.schemas import ParseBasic, ParsedCV, ParseExperience, ParseSkills


@dataclass(frozen=True)
class ParseResult:
    parsed: ParsedCV = field(repr=False)
    model: str
    prompt_version: str


def parse_cv(text: str, *, client: LLMClient | None = None, version: int = 1) -> ParseResult:
    """The caller must redact contacts before passing text here. Never log text."""
    client = client if client is not None else get_llm_client()
    parts: tuple[tuple[str, type[BaseModel]], ...] = (
        ("parse_cv_basic", ParseBasic),
        ("parse_cv_experience", ParseExperience),
        ("parse_cv_skills", ParseSkills),
    )
    prompts = [load_prompt(task, version).render(text=text) for task, _ in parts]
    with ThreadPoolExecutor(max_workers=3, thread_name_prefix="cv-parse") as pool:
        futures: list[Future[BaseModel]] = [
            pool.submit(
                client.complete_json,
                system=prompt.system,
                user=prompt.user,
                schema=schema,
                temperature=0,
            )
            for prompt, (_, schema) in zip(prompts, parts, strict=True)
        ]
        merged = {}
        for future in futures:
            merged.update(future.result().model_dump())
    return ParseResult(ParsedCV.model_validate(merged), client.model, prompts[0].prompt_version)

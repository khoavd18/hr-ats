"""Transaction-neutral hooks for CV ingestion and T13 Job create/update."""

from app.ai.anonymize import anonymize
from app.ai.embed import Embedder, EmbeddingError, get_embedder, validate_vectors
from app.core.config import Settings, get_settings
from app.models.candidates import Candidate
from app.models.jobs import Job


def embed_candidate(
    candidate: Candidate,
    text: str,
    *,
    embedder: Embedder | None = None,
    settings: Settings | None = None,
) -> None:
    settings = settings or get_settings()
    cleaned = anonymize(text, candidate.full_name)
    if not cleaned:
        raise EmbeddingError()
    vectors = (embedder or get_embedder(settings)).embed([cleaned])
    vector = validate_vectors(vectors, 1, settings.embedding_dim)[0]
    # Do not mutate persisted fields until the entire embedding has succeeded.
    candidate.anonymized_text = cleaned
    candidate.embedding = vector


def job_embedding_text(job: Job) -> str:
    return "\n".join(
        [job.title, job.description, *(job.must_have or []), *(job.nice_to_have or [])]
    )


def embed_job(
    job: Job, *, embedder: Embedder | None = None, settings: Settings | None = None
) -> None:
    """T13 calls after assigning title/description/requirements, before commit."""
    settings = settings or get_settings()
    vectors = (embedder or get_embedder(settings)).embed([job_embedding_text(job)])
    job.embedding = validate_vectors(vectors, 1, settings.embedding_dim)[0]

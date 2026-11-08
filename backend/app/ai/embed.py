"""Embedding adapters; only anonymized CV text may cross this boundary."""

import hashlib
import math
import re
import unicodedata
from collections.abc import Sequence
from functools import lru_cache
from typing import Any, Protocol

from app.core.config import REPO_ROOT, Settings, get_settings
from app.core.errors import AppError


class EmbeddingError(AppError):
    def __init__(self) -> None:
        super().__init__(
            "EMBEDDING_FAILED", "Không thể tạo dữ liệu tìm kiếm. Vui lòng kiểm tra cấu hình.", 503
        )


class Embedder(Protocol):
    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


def validate_vectors(vectors: Any, count: int, dimension: int) -> list[list[float]]:
    """Reject partial, non-finite, zero or dimension-mismatched output; L2 normalize."""
    try:
        if len(vectors) != count:
            raise ValueError
        output = []
        for vector in vectors:
            if len(vector) != dimension:
                raise ValueError
            values = [float(value) for value in vector]
            norm = math.hypot(*values)
            if not math.isfinite(norm) or norm == 0:
                raise ValueError
            output.append([value / norm for value in values])
        return output
    except Exception:
        raise EmbeddingError() from None


class FakeEmbedder:
    """Signed hash of normalized words. Deterministic test data, not semantic AI."""

    def __init__(self, dimension: int = 1024) -> None:
        if dimension < 1:
            raise EmbeddingError()
        self.dimension = dimension

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            text = unicodedata.normalize("NFC", text).casefold()
            vector = [0.0] * self.dimension
            for token in re.findall(r"\w+", text):
                digest = hashlib.sha256(token.encode("utf-8")).digest()
                index = int.from_bytes(digest[:8], "big") % self.dimension
                vector[index] += 1.0 if digest[8] & 1 else -1.0
            if not any(vector):
                vector[0] = 1.0
            vectors.append(vector)
        return validate_vectors(vectors, len(texts), self.dimension)


@lru_cache(maxsize=1)
def _load_local_model(model: str, local_files_only: bool) -> Any:
    # Optional heavy dependency: fake/CI never import torch or download weights.
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(
        model,
        cache_folder=str(REPO_ROOT / "var/models"),
        trust_remote_code=False,
        local_files_only=local_files_only,
        model_kwargs={"use_safetensors": True},
    )


class LocalEmbedder:
    def __init__(self, model: str, dimension: int, *, local_files_only: bool = False) -> None:
        if not model.strip() or dimension < 1:
            raise EmbeddingError()
        self.model = model
        self.dimension = dimension
        self.local_files_only = local_files_only

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            model = _load_local_model(self.model, self.local_files_only)
            if model.get_sentence_embedding_dimension() != self.dimension:
                raise EmbeddingError()
            vectors = model.encode(
                list(texts),
                batch_size=16,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
            return validate_vectors(vectors, len(texts), self.dimension)
        except Exception:
            # Dependency/model/encoder exceptions may include the original text.
            raise EmbeddingError() from None


def get_embedder(settings: Settings | None = None) -> Embedder:
    settings = settings or get_settings()
    if settings.embedding_provider == "fake":
        return FakeEmbedder(settings.embedding_dim)
    if settings.embedding_provider == "local":
        return LocalEmbedder(
            settings.embedding_model,
            settings.embedding_dim,
            local_files_only=settings.app_env == "test",
        )
    raise EmbeddingError()

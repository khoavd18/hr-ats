import math
import sys
from types import SimpleNamespace

import pytest

from app.ai import embed
from app.ai.embed import EmbeddingError, FakeEmbedder, LocalEmbedder, get_embedder, validate_vectors
from app.core.config import REPO_ROOT, Settings


@pytest.mark.parametrize("dimension", [1, 8, 1024])
def test_fake_is_deterministic_order_independent_and_l2_normalized(dimension):
    adapter = FakeEmbedder(dimension)
    texts = ["Python SQL", "Thiết kế giao diện", "", "Kỹ năng: React"]
    vectors = adapter.embed(texts)
    assert vectors == FakeEmbedder(dimension).embed(texts)
    assert vectors[::-1] == adapter.embed(texts[::-1])
    assert adapter.embed([]) == []
    assert adapter.embed(["PYTHON sql"]) == adapter.embed(["sql python"])
    for vector in vectors:
        assert len(vector) == dimension and all(math.isfinite(v) for v in vector)
        assert math.hypot(*vector) == pytest.approx(1)


def test_factory_uses_configuration_without_loading_local_model(monkeypatch):
    monkeypatch.setattr(embed, "_load_local_model", lambda *args: pytest.fail("unexpected load"))
    settings = Settings(embedding_dim=8, embedding_provider="fake")
    assert isinstance(get_embedder(settings), FakeEmbedder)
    adapter = get_embedder(settings.model_copy(update={"embedding_provider": "local"}))
    assert isinstance(adapter, LocalEmbedder) and adapter.local_files_only
    assert adapter.embed([]) == []
    with pytest.raises(EmbeddingError):
        get_embedder(settings.model_copy(update={"embedding_provider": "unsupported"}))


def test_local_loader_cache_flags_and_batch_contract_without_network(monkeypatch, caplog):
    loads, requests = [], []

    class Model:
        def __init__(self, *args, **kwargs):
            loads.append((args, kwargs))

        def get_sentence_embedding_dimension(self):
            return 3

        def encode(self, texts, **kwargs):
            requests.append((texts, kwargs))
            return [[3, 4, 0] for _ in texts]

    monkeypatch.setitem(
        sys.modules, "sentence_transformers", SimpleNamespace(SentenceTransformer=Model)
    )
    embed._load_local_model.cache_clear()
    try:
        adapter = LocalEmbedder("synthetic/model", 3, local_files_only=True)
        assert adapter.embed(["[TÊN] Python", "[TÊN] SQL"]) == [[0.6, 0.8, 0]] * 2
        assert adapter.embed(["private-sentinel"]) == [[0.6, 0.8, 0]]
        assert len(loads) == 1
        assert loads[0] == (
            ("synthetic/model",),
            {
                "cache_folder": str(REPO_ROOT / "var/models"),
                "trust_remote_code": False,
                "local_files_only": True,
                "model_kwargs": {"use_safetensors": True},
            },
        )
        assert requests[0] == (
            ["[TÊN] Python", "[TÊN] SQL"],
            {
                "batch_size": 16,
                "show_progress_bar": False,
                "convert_to_numpy": True,
                "normalize_embeddings": True,
            },
        )
        assert "private-sentinel" not in caplog.text
    finally:
        embed._load_local_model.cache_clear()


@pytest.mark.parametrize(
    "vectors,count,dimension",
    [
        ([], 1, 3),
        ([[1, 0]], 1, 3),
        ([[0, 0, 0]], 1, 3),
        ([[float("nan"), 1, 0]], 1, 3),
        ([[float("inf"), 0, 0]], 1, 3),
        ([["private-sentinel", 0, 0]], 1, 3),
        (None, 1, 3),
    ],
)
def test_invalid_vectors_fail_without_exposing_values(vectors, count, dimension):
    with pytest.raises(EmbeddingError) as caught:
        validate_vectors(vectors, count, dimension)
    assert "private-sentinel" not in str(caught.value)


@pytest.mark.parametrize("failure", ["load", "dimension", "encode", "output"])
def test_local_failures_are_safe_and_never_fall_back_to_fake(monkeypatch, caplog, failure):
    def fail(*args, **kwargs):
        raise RuntimeError("private-sentinel sentinel@example.invalid")

    model = SimpleNamespace(
        get_sentence_embedding_dimension=lambda: 2 if failure == "dimension" else 3,
        encode=fail if failure == "encode" else lambda *a, **kw: [[0, 0]],
    )
    monkeypatch.setattr(embed, "_load_local_model", fail if failure == "load" else lambda *a: model)
    with pytest.raises(EmbeddingError) as caught:
        LocalEmbedder("synthetic", 3).embed(["private-sentinel"])
    assert "private-sentinel" not in str(caught.value) + caplog.text


@pytest.mark.parametrize(
    "factory",
    [lambda: FakeEmbedder(0), lambda: LocalEmbedder("", 3), lambda: LocalEmbedder("x", 0)],
)
def test_invalid_adapter_configuration_is_rejected(factory):
    with pytest.raises(EmbeddingError):
        factory()

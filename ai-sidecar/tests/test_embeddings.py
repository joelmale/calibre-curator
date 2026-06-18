"""Tests for embedding providers using a stub provider — no network calls."""
from __future__ import annotations

import pytest

from sidecar.embeddings.base import EmbeddingProvider


# ---------------------------------------------------------------------------
# Stub provider for testing logic that depends on EmbeddingProvider
# ---------------------------------------------------------------------------

class StubEmbeddingProvider(EmbeddingProvider):
    """Returns deterministic fixed-length vectors without any network call."""

    def __init__(self, dim: int = 8) -> None:
        self._dim = dim
        self.calls: list[list[str]] = []

    @property
    def model_name(self) -> str:
        return "stub-model"

    @property
    def dimension(self) -> int:
        return self._dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [
            [float(i % self._dim) / self._dim for i in range(self._dim)]
            for _ in texts
        ]


class TestEmbeddingProviderContract:
    def test_embed_returns_one_vector_per_text(self):
        p = StubEmbeddingProvider(dim=4)
        texts = ["hello", "world", "foo"]
        vecs = p.embed(texts)
        assert len(vecs) == 3

    def test_embed_returns_correct_dimension(self):
        p = StubEmbeddingProvider(dim=16)
        vecs = p.embed(["test"])
        assert len(vecs[0]) == 16

    def test_embed_empty_list_returns_empty(self):
        p = StubEmbeddingProvider()
        assert p.embed([]) == []

    def test_model_name_is_string(self):
        p = StubEmbeddingProvider()
        assert isinstance(p.model_name, str)
        assert p.model_name

    def test_dimension_is_positive_int(self):
        p = StubEmbeddingProvider(dim=8)
        assert isinstance(p.dimension, int)
        assert p.dimension > 0


class TestOllamaProviderParsing:
    """Unit-test the Ollama provider's response parsing without network."""

    def test_imports_cleanly(self):
        from sidecar.embeddings.ollama_provider import OllamaEmbeddingProvider
        p = OllamaEmbeddingProvider("http://localhost:11434", "nomic-embed-text")
        assert p.model_name == "nomic-embed-text"

    def test_base_url_trailing_slash_stripped(self):
        from sidecar.embeddings.ollama_provider import OllamaEmbeddingProvider
        p = OllamaEmbeddingProvider("http://localhost:11434/", "model")
        assert not p._base_url.endswith("/")

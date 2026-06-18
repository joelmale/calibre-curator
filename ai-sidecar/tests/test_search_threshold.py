"""Tests for relevance threshold filtering in ChromaStore and the search APIs."""
from __future__ import annotations

import math
import unittest.mock as mock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_store(tmp_path, model_name="stub-model"):
    pytest.importorskip("chromadb")
    import chromadb
    from sidecar.vectors.chroma_store import ChromaStore

    with mock.patch("chromadb.PersistentClient") as mock_client:
        mock_client.return_value = chromadb.EphemeralClient()
        store = ChromaStore(tmp_path, model_name)
    return store


def _vec(seed: float, dim: int = 8) -> list[float]:
    raw = [math.sin(seed + i) for i in range(dim)]
    norm = math.sqrt(sum(x * x for x in raw))
    return [x / norm for x in raw]


# ---------------------------------------------------------------------------
# ChromaStore threshold tests
# ---------------------------------------------------------------------------

class TestSearchThreshold:
    def test_no_threshold_returns_all(self, tmp_path):
        """Without a threshold, all results are returned regardless of distance."""
        store = _make_store(tmp_path)
        # Insert a vector that is very different from our query (seed far apart)
        store.upsert(
            ids=["c1"],
            embeddings=[_vec(5.0)],
            metadatas=[{"calibre_book_id": 1, "heading": ""}],
            documents=["irrelevant text"],
        )
        results = store.search(_vec(0.0), n_results=5, max_distance=None)
        assert len(results) == 1

    def test_threshold_drops_far_results(self, tmp_path):
        """Results with distance > max_distance are dropped."""
        store = _make_store(tmp_path)
        store.upsert(
            ids=["near", "far"],
            embeddings=[_vec(0.1), _vec(5.0)],
            metadatas=[
                {"calibre_book_id": 10, "heading": ""},
                {"calibre_book_id": 20, "heading": ""},
            ],
            documents=["near text", "far text"],
        )
        # Only the near result should survive a tight threshold.
        # Distance 0.0 threshold keeps nothing; 1.0 should keep near but maybe not far.
        near_results = store.search(_vec(0.1), n_results=5, max_distance=0.1)
        ids_returned = {r.calibre_book_id for r in near_results}
        # The near vector (same seed) should have distance ~0; far should be filtered.
        assert 20 not in ids_returned

    def test_threshold_zero_keeps_only_identical(self, tmp_path):
        """max_distance=0.0 keeps only an exact (distance=0) match."""
        store = _make_store(tmp_path)
        v = _vec(1.0)
        store.upsert(
            ids=["exact"],
            embeddings=[v],
            metadatas=[{"calibre_book_id": 99, "heading": ""}],
            documents=["exact match"],
        )
        results = store.search(v, n_results=5, max_distance=0.0)
        # A vector queried against itself in cosine space has distance ~0.
        assert all(r.distance <= 0.01 for r in results)

    def test_threshold_passes_close_results(self, tmp_path):
        """Results within the threshold are kept."""
        store = _make_store(tmp_path)
        v = _vec(1.0)
        store.upsert(
            ids=["c1"],
            embeddings=[v],
            metadatas=[{"calibre_book_id": 42, "heading": ""}],
            documents=["close text"],
        )
        results = store.search(v, n_results=5, max_distance=0.75)
        assert len(results) == 1
        assert results[0].calibre_book_id == 42

    def test_threshold_empty_store_returns_empty(self, tmp_path):
        """Threshold on empty store returns empty list (no error)."""
        store = _make_store(tmp_path)
        results = store.search(_vec(1.0), n_results=5, max_distance=0.75)
        assert results == []

    def test_all_far_results_gives_empty_list(self, tmp_path):
        """When all candidates exceed max_distance, return empty list."""
        store = _make_store(tmp_path)
        # Insert a vector far from query (different seed)
        store.upsert(
            ids=["far1"],
            embeddings=[_vec(4.0)],
            metadatas=[{"calibre_book_id": 5, "heading": ""}],
            documents=["far text"],
        )
        results = store.search(_vec(0.0), n_results=5, max_distance=0.0)
        # At max_distance=0 nothing except a perfect match passes.
        assert results == []


# ---------------------------------------------------------------------------
# Config default test
# ---------------------------------------------------------------------------

class TestSearchMaxDistanceConfig:
    def test_default_value(self):
        """Default search_max_distance is 0.75."""
        import os
        with mock.patch.dict(os.environ, {}, clear=False):
            # Remove override if present
            os.environ.pop("SEARCH_MAX_DISTANCE", None)
            from sidecar.config import Config
            cfg = Config()
            assert cfg.search_max_distance == 0.75

    def test_env_override(self):
        """SEARCH_MAX_DISTANCE env var overrides the default."""
        import os
        with mock.patch.dict(os.environ, {"SEARCH_MAX_DISTANCE": "0.5"}):
            from sidecar.config import Config
            cfg = Config()
            assert cfg.search_max_distance == 0.5


# ---------------------------------------------------------------------------
# Embedding provider nomic prefix tests
# ---------------------------------------------------------------------------

class TestNomicPrefixes:
    def test_embed_documents_adds_prefix_for_nomic(self):
        """embed_documents prepends 'search_document: ' for nomic-embed-text."""
        from sidecar.embeddings.ollama_provider import OllamaEmbeddingProvider

        provider = OllamaEmbeddingProvider("http://localhost:11434", "nomic-embed-text")
        captured: list[list[str]] = []

        def fake_embed(self_inner, texts):
            captured.append(texts)
            return [[0.1] * 8 for _ in texts]

        with mock.patch.object(OllamaEmbeddingProvider, "embed", fake_embed):
            provider.embed_documents(["hello world"])

        assert len(captured) == 1
        assert captured[0][0].startswith("search_document: ")

    def test_embed_query_adds_prefix_for_nomic(self):
        """embed_query prepends 'search_query: ' for nomic-embed-text."""
        from sidecar.embeddings.ollama_provider import OllamaEmbeddingProvider

        provider = OllamaEmbeddingProvider("http://localhost:11434", "nomic-embed-text")
        captured: list[list[str]] = []

        def fake_embed(self_inner, texts):
            captured.append(texts)
            return [[0.1] * 8 for _ in texts]

        with mock.patch.object(OllamaEmbeddingProvider, "embed", fake_embed):
            provider.embed_query(["cozy murder mystery"])

        assert len(captured) == 1
        assert captured[0][0].startswith("search_query: ")

    def test_embed_documents_no_prefix_for_other_models(self):
        """embed_documents does NOT add prefix for non-nomic models."""
        from sidecar.embeddings.ollama_provider import OllamaEmbeddingProvider

        provider = OllamaEmbeddingProvider("http://localhost:11434", "mxbai-embed-large")
        captured: list[list[str]] = []

        def fake_embed(self_inner, texts):
            captured.append(texts)
            return [[0.1] * 8 for _ in texts]

        with mock.patch.object(OllamaEmbeddingProvider, "embed", fake_embed):
            provider.embed_documents(["hello world"])

        assert captured[0][0] == "hello world"

    def test_embed_query_no_prefix_for_other_models(self):
        """embed_query does NOT add prefix for non-nomic models."""
        from sidecar.embeddings.ollama_provider import OllamaEmbeddingProvider

        provider = OllamaEmbeddingProvider("http://localhost:11434", "mxbai-embed-large")
        captured: list[list[str]] = []

        def fake_embed(self_inner, texts):
            captured.append(texts)
            return [[0.1] * 8 for _ in texts]

        with mock.patch.object(OllamaEmbeddingProvider, "embed", fake_embed):
            provider.embed_query(["cozy murder mystery"])

        assert captured[0][0] == "cozy murder mystery"

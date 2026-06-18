"""Tests for ChromaStore using an in-memory Chroma client — no disk I/O."""
from __future__ import annotations

import pytest

from sidecar.vectors.base import SearchResult, VectorStore


# ---------------------------------------------------------------------------
# In-memory Chroma store for testing
# ---------------------------------------------------------------------------

def _make_store(tmp_path, model_name="stub-model"):
    chroma = pytest.importorskip("chromadb")
    from sidecar.vectors.chroma_store import ChromaStore, _collection_name

    # Patch PersistentClient to use EphemeralClient so tests run without disk
    import chromadb
    import unittest.mock as mock

    with mock.patch("chromadb.PersistentClient") as mock_client:
        client_instance = chromadb.EphemeralClient()
        mock_client.return_value = client_instance
        store = ChromaStore(tmp_path, model_name)

    return store


def _vec(seed: float, dim: int = 8) -> list[float]:
    import math
    raw = [math.sin(seed + i) for i in range(dim)]
    norm = math.sqrt(sum(x * x for x in raw))
    return [x / norm for x in raw]


class TestChromaStoreContract:
    def test_upsert_and_search(self, tmp_path):
        store = _make_store(tmp_path)
        v1 = _vec(0.1)
        store.upsert(
            ids=["chunk-1"],
            embeddings=[v1],
            metadatas=[{"calibre_book_id": 42, "heading": "Chapter 1"}],
            documents=["The story begins here."],
        )
        results = store.search(v1, n_results=1)
        assert len(results) == 1
        assert results[0].calibre_book_id == 42

    def test_search_returns_search_result_type(self, tmp_path):
        store = _make_store(tmp_path)
        store.upsert(
            ids=["c1"],
            embeddings=[_vec(1.0)],
            metadatas=[{"calibre_book_id": 1, "heading": ""}],
            documents=["text"],
        )
        results = store.search(_vec(1.0), n_results=1)
        assert isinstance(results[0], SearchResult)

    def test_exclude_book_id(self, tmp_path):
        store = _make_store(tmp_path)
        store.upsert(
            ids=["c1", "c2"],
            embeddings=[_vec(0.5), _vec(0.5)],
            metadatas=[
                {"calibre_book_id": 10, "heading": ""},
                {"calibre_book_id": 20, "heading": ""},
            ],
            documents=["book 10 text", "book 20 text"],
        )
        results = store.search(_vec(0.5), n_results=5, exclude_book_id=10)
        book_ids = {r.calibre_book_id for r in results}
        assert 10 not in book_ids

    def test_delete_by_book_id(self, tmp_path):
        store = _make_store(tmp_path)
        store.upsert(
            ids=["c1", "c2"],
            embeddings=[_vec(0.1), _vec(0.9)],
            metadatas=[
                {"calibre_book_id": 5, "heading": ""},
                {"calibre_book_id": 6, "heading": ""},
            ],
            documents=["text a", "text b"],
        )
        store.delete_by_book_id(5)
        results = store.search(_vec(0.1), n_results=5)
        book_ids = {r.calibre_book_id for r in results}
        assert 5 not in book_ids

    def test_upsert_empty_is_noop(self, tmp_path):
        store = _make_store(tmp_path)
        store.upsert([], [], [], [])  # should not raise

    def test_search_empty_store_returns_empty(self, tmp_path):
        store = _make_store(tmp_path)
        results = store.search(_vec(0.5), n_results=5)
        assert results == []


class TestCollectionNaming:
    def test_model_name_sanitised(self):
        from sidecar.vectors.chroma_store import _collection_name
        # Dots and slashes are replaced; hyphens are valid in Chroma names
        name = _collection_name("openai/text-embedding-3.small")
        assert "." not in name
        assert "/" not in name
        assert name.startswith("calibre_books_")

    def test_name_max_length(self):
        from sidecar.vectors.chroma_store import _collection_name
        long_model = "a" * 100
        assert len(_collection_name(long_model)) <= 63

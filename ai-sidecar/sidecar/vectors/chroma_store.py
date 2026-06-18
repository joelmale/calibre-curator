from __future__ import annotations

import logging
import re
from pathlib import Path

from .base import SearchResult, VectorStore

logger = logging.getLogger(__name__)


def _collection_name(model_name: str) -> str:
    """Sanitise model name into a valid Chroma collection name."""
    slug = re.sub(r"[^a-zA-Z0-9_-]", "_", model_name)
    return f"calibre_books_{slug}"[:63]


class ChromaStore(VectorStore):
    def __init__(self, persist_dir: Path, model_name: str) -> None:
        import chromadb  # type: ignore[import-untyped]

        self._client = chromadb.PersistentClient(path=str(persist_dir))
        self._collection = self._client.get_or_create_collection(
            name=_collection_name(model_name),
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            "Chroma collection '%s' ready (%d vectors)",
            self._collection.name,
            self._collection.count(),
        )

    def upsert(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict],
        documents: list[str],
    ) -> None:
        if not ids:
            return
        self._collection.upsert(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents,
        )

    def search(
        self,
        query_embedding: list[float],
        n_results: int,
        exclude_book_id: int | None = None,
        max_distance: float | None = None,
    ) -> list[SearchResult]:
        where = (
            {"calibre_book_id": {"$ne": exclude_book_id}}
            if exclude_book_id is not None
            else None
        )

        try:
            response = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where,
                include=["metadatas", "distances", "documents"],
            )
        except Exception as exc:
            logger.warning("Chroma query failed: %s", exc)
            return []

        results: list[SearchResult] = []
        ids_out = response.get("ids", [[]])[0]
        distances = response.get("distances", [[]])[0]
        metadatas_out = response.get("metadatas", [[]])[0]
        documents_out = response.get("documents", [[]])[0]

        for uid, dist, meta, doc in zip(ids_out, distances, metadatas_out, documents_out):
            dist_f = float(dist)
            if max_distance is not None and dist_f > max_distance:
                continue
            results.append(SearchResult(
                calibre_book_id=int(meta.get("calibre_book_id", 0)),
                chunk_uid=uid,
                distance=dist_f,
                text=doc or "",
                heading=meta.get("heading") or None,
            ))

        return results

    def delete_by_book_id(self, calibre_book_id: int) -> None:
        try:
            self._collection.delete(where={"calibre_book_id": calibre_book_id})
        except Exception as exc:
            logger.warning("Chroma delete for book %d failed: %s", calibre_book_id, exc)

    def get_book_embedding(self, calibre_book_id: int) -> list[float] | None:
        try:
            res = self._collection.get(
                where={"calibre_book_id": calibre_book_id},
                include=["embeddings"],
                limit=1,
            )
        except Exception as exc:
            logger.warning("Chroma get embedding for book %d failed: %s", calibre_book_id, exc)
            return None
        embeddings = res.get("embeddings")
        if embeddings is not None and len(embeddings) > 0:
            return list(embeddings[0])
        return None

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class SearchResult:
    calibre_book_id: int
    chunk_uid: str
    distance: float
    text: str
    heading: str | None


class VectorStore(ABC):
    @abstractmethod
    def upsert(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict],
        documents: list[str],
    ) -> None: ...

    @abstractmethod
    def search(
        self,
        query_embedding: list[float],
        n_results: int,
        exclude_book_id: int | None = None,
    ) -> list[SearchResult]: ...

    @abstractmethod
    def delete_by_book_id(self, calibre_book_id: int) -> None: ...

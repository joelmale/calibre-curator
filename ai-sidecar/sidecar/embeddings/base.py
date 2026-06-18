from __future__ import annotations

from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text (raw, no prefix applied).

        Prefer `embed_documents` / `embed_query` for ingestion and search
        respectively — subclasses may apply asymmetric prefixes there.
        """
        ...

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed document texts for storage/indexing.

        Default implementation delegates to `embed`.  Override to add
        model-specific document prefixes (e.g. nomic-embed-text's
        ``"search_document: "``).
        """
        return self.embed(texts)

    def embed_query(self, texts: list[str]) -> list[list[float]]:
        """Embed query texts for retrieval.

        Default implementation delegates to `embed`.  Override to add
        model-specific query prefixes (e.g. nomic-embed-text's
        ``"search_query: "``).
        """
        return self.embed(texts)

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Canonical name of the embedding model (used to name Chroma collections)."""
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Embedding vector length."""
        ...

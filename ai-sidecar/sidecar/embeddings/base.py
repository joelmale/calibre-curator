from __future__ import annotations

from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text."""
        ...

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

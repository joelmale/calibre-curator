from __future__ import annotations

import logging

from .base import EmbeddingProvider

logger = logging.getLogger(__name__)

_BATCH_SIZE = 512


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(self, api_key: str, model: str) -> None:
        try:
            from openai import OpenAI  # type: ignore[import-untyped]
        except ImportError as exc:
            raise RuntimeError(
                "openai package is required for OpenAI embeddings. "
                "Install with: pip install 'calibre-ai-sidecar[openai]'"
            ) from exc
        self._client = OpenAI(api_key=api_key)
        self._model = model
        self._dimension: int | None = None

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def dimension(self) -> int:
        if self._dimension is None:
            result = self.embed(["probe"])
            self._dimension = len(result[0])
        return self._dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        results: list[list[float]] = []
        for i in range(0, len(texts), _BATCH_SIZE):
            batch = texts[i : i + _BATCH_SIZE]
            response = self._client.embeddings.create(input=batch, model=self._model)
            results.extend(item.embedding for item in response.data)
        return results

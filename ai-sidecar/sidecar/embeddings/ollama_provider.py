from __future__ import annotations

import logging

import requests

from .base import EmbeddingProvider

logger = logging.getLogger(__name__)

_BATCH_SIZE = 32


class OllamaEmbeddingProvider(EmbeddingProvider):
    """Calls the Ollama /api/embed endpoint (Ollama ≥ 0.1.26).

    Falls back to the legacy /api/embeddings endpoint (one request per text)
    if the batch endpoint returns a 404.
    """

    def __init__(self, base_url: str, model: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._dimension: int | None = None
        self._use_legacy: bool = False

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
        if self._use_legacy:
            return self._embed_legacy(texts)
        try:
            return self._embed_batch(texts)
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                logger.info("Ollama /api/embed not found, switching to legacy endpoint")
                self._use_legacy = True
                return self._embed_legacy(texts)
            raise

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        results: list[list[float]] = []
        for i in range(0, len(texts), _BATCH_SIZE):
            batch = texts[i : i + _BATCH_SIZE]
            resp = requests.post(
                f"{self._base_url}/api/embed",
                json={"model": self._model, "input": batch},
                timeout=120,
            )
            resp.raise_for_status()
            results.extend(resp.json()["embeddings"])
        return results

    def _embed_legacy(self, texts: list[str]) -> list[list[float]]:
        results: list[list[float]] = []
        for text in texts:
            resp = requests.post(
                f"{self._base_url}/api/embeddings",
                json={"model": self._model, "prompt": text},
                timeout=60,
            )
            resp.raise_for_status()
            results.append(resp.json()["embedding"])
        return results

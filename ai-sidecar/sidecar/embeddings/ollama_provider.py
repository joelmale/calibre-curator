from __future__ import annotations

import logging

import requests

from .base import EmbeddingProvider

logger = logging.getLogger(__name__)

_BATCH_SIZE = 32

# nomic-embed-text supports asymmetric retrieval via task-type prefixes.
# Using them substantially improves retrieval quality.
# NOTE: these prefixes change embedding semantics — all vectors in a collection
# MUST be embedded with the same prefix scheme.  The collection is currently
# rebuilding from scratch, so it is safe to introduce them now.
_NOMIC_DOC_PREFIX = "search_document: "
_NOMIC_QUERY_PREFIX = "search_query: "


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

    def _is_nomic(self) -> bool:
        return "nomic-embed-text" in self._model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed with document prefix for nomic-embed-text; otherwise plain embed."""
        if self._is_nomic():
            return self.embed([_NOMIC_DOC_PREFIX + t for t in texts])
        return self.embed(texts)

    def embed_query(self, texts: list[str]) -> list[list[float]]:
        """Embed with query prefix for nomic-embed-text; otherwise plain embed."""
        if self._is_nomic():
            return self.embed([_NOMIC_QUERY_PREFIX + t for t in texts])
        return self.embed(texts)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self._use_legacy:
            return self._embed_legacy(texts)
        try:
            return self._embed_batch(texts)
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                body = exc.response.text or ""
                # Model-not-found 404s contain "not found" or "try pulling"
                if "not found" in body or "try pulling" in body or "pull" in body.lower():
                    raise RuntimeError(
                        f"Embedding model '{self._model}' is not available in Ollama. "
                        f"Run: ollama pull {self._model}"
                    ) from exc
                # Endpoint-not-found 404 → fall back to legacy single-text endpoint
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
            if resp.status_code == 404:
                body = resp.text or ""
                if "not found" in body or "pull" in body.lower():
                    raise RuntimeError(
                        f"Embedding model '{self._model}' is not available in Ollama. "
                        f"Run: ollama pull {self._model}"
                    )
            resp.raise_for_status()
            results.append(resp.json()["embedding"])
        return results

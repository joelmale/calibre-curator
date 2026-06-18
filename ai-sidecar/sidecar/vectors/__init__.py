from __future__ import annotations

from pathlib import Path

from .base import VectorStore
from ..config import Config


def get_vector_store(config: Config, model_name: str) -> VectorStore:
    if config.vector_backend == "chroma":
        from .chroma_store import ChromaStore
        return ChromaStore(config.chroma_persist_dir, model_name)
    raise ValueError(f"Unknown vector backend: {config.vector_backend!r}")

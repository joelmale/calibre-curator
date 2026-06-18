from __future__ import annotations

from ..config import Config
from .base import EmbeddingProvider


def get_embedding_provider(config: Config) -> EmbeddingProvider:
    if config.embedding_provider == "openai":
        if not config.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when EMBEDDING_PROVIDER=openai")
        from .openai_provider import OpenAIEmbeddingProvider
        return OpenAIEmbeddingProvider(config.openai_api_key, config.openai_embed_model)

    from .ollama_provider import OllamaEmbeddingProvider
    return OllamaEmbeddingProvider(config.ollama_base_url, config.ollama_embed_model)

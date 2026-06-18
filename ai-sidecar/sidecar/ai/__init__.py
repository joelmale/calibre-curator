from __future__ import annotations

from ..config import Config
from .chat import ChatError, OllamaChatClient


def get_chat_client(config: Config) -> OllamaChatClient:
    return OllamaChatClient(config.ollama_base_url, config.ollama_chat_model)


__all__ = ["ChatError", "OllamaChatClient", "get_chat_client"]

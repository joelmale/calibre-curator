from __future__ import annotations

import logging

from ..config import Config
from .chat import ChatClient, ChatError, OllamaChatClient
from .providers import (
    AnthropicChatClient,
    FallbackChatClient,
    GeminiChatClient,
    OpenAICompatChatClient,
)

logger = logging.getLogger(__name__)


def _build_provider(name: str, config: Config) -> ChatClient | None:
    """Construct one provider client if its credentials are present, else None.

    Ollama needs no key and is always constructable (local fallback).
    """
    if name == "anthropic":
        if config.anthropic_api_key:
            return AnthropicChatClient(config.anthropic_api_key, config.anthropic_chat_model)
    elif name == "openai":
        if config.openai_api_key:
            return OpenAICompatChatClient(config.openai_api_key, config.openai_chat_model)
    elif name == "gemini":
        if config.gemini_api_key:
            return GeminiChatClient(config.gemini_api_key, config.gemini_chat_model)
    elif name == "meta":
        if config.meta_api_key:
            return OpenAICompatChatClient(
                config.meta_api_key, config.meta_chat_model,
                base_url=config.meta_base_url, provider_label="meta",
            )
    elif name == "ollama":
        return OllamaChatClient(config.ollama_base_url, config.ollama_chat_model)
    else:
        logger.warning("Unknown chat provider in priority list: %r", name)
    return None


def get_chat_client(config: Config) -> ChatClient:
    """Build the chat client from the configured provider priority.

    Each provider is included only if its API key is set; local Ollama is always
    appended as the final fallback so generation degrades to local inference
    rather than failing when cloud keys are absent or a cloud call errors.
    """
    chain: list[ChatClient] = []
    for name in config.chat_provider_priority:
        client = _build_provider(name.strip().lower(), config)
        if client is not None:
            chain.append(client)

    if not any(isinstance(c, OllamaChatClient) for c in chain):
        chain.append(OllamaChatClient(config.ollama_base_url, config.ollama_chat_model))

    if len(chain) == 1:
        return chain[0]
    logger.info(
        "Chat fallback chain: %s",
        " -> ".join(c.model_name for c in chain),
    )
    return FallbackChatClient(chain)


__all__ = ["ChatClient", "ChatError", "OllamaChatClient", "get_chat_client"]

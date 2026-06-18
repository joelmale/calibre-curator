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
from .rate_limiter import get_rate_limiter

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
    elif name == "grok":
        if config.xai_api_key:
            return OpenAICompatChatClient(
                config.xai_api_key, config.xai_chat_model,
                base_url=config.xai_base_url, provider_label="grok",
            )
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
    appended as the final fallback. The shared rate limiter is wired in so
    over-limit / disabled providers are skipped to the next in the chain.
    """
    chain: list[ChatClient] = []
    seen: set[str] = set()
    for name in config.chat_provider_priority:
        key = name.strip().lower()
        client = _build_provider(key, config)
        if client is not None:
            client.provider_key = key
            chain.append(client)
            seen.add(key)

    if "ollama" not in seen:
        floor = OllamaChatClient(config.ollama_base_url, config.ollama_chat_model)
        floor.provider_key = "ollama"
        chain.append(floor)

    if len(chain) == 1:
        return chain[0]
    logger.info("Chat fallback chain: %s", " -> ".join(c.model_name for c in chain))
    return FallbackChatClient(chain, limiter=get_rate_limiter())


def configured_providers(config: Config) -> list[dict]:
    """Describe every provider in the priority list — name, model, and whether a
    credential is present — for the Provider Limits panel. Ollama is always
    available (local)."""
    specs = {
        "anthropic": (config.anthropic_chat_model, bool(config.anthropic_api_key)),
        "openai":    (config.openai_chat_model, bool(config.openai_api_key)),
        "gemini":    (config.gemini_chat_model, bool(config.gemini_api_key)),
        "grok":      (config.xai_chat_model, bool(config.xai_api_key)),
        "meta":      (config.meta_chat_model, bool(config.meta_api_key)),
        "ollama":    (config.ollama_chat_model, True),
    }
    out: list[dict] = []
    seen: set[str] = set()
    for name in config.chat_provider_priority:
        key = name.strip().lower()
        if key in specs and key not in seen:
            model, available = specs[key]
            out.append({"provider": key, "model": model, "available": available})
            seen.add(key)
    if "ollama" not in seen:
        out.append({"provider": "ollama", "model": config.ollama_chat_model, "available": True})
    return out


__all__ = [
    "ChatClient",
    "ChatError",
    "OllamaChatClient",
    "get_chat_client",
    "configured_providers",
]

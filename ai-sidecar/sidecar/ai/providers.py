from __future__ import annotations

import logging
from typing import Any

import requests

from .chat import ChatClient, ChatError, ChatResponse, parse_json_object, _DEFAULT_TIMEOUT

logger = logging.getLogger(__name__)

# Appended to system prompts for providers whose JSON mode wants an explicit
# "JSON" mention (OpenAI's json_object mode requires it).
_JSON_NUDGE = "\n\nRespond with a single valid JSON object and nothing else."


class OpenAICompatChatClient(ChatClient):
    """OpenAI-compatible /chat/completions client.

    Works for OpenAI itself and any OpenAI-compatible endpoint — Meta's Llama
    API, Groq, Together, OpenRouter — by overriding base_url.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        provider_label: str = "openai",
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._label = provider_label

    @property
    def model_name(self) -> str:
        return self._model

    def chat_json(
        self,
        system: str,
        user: str,
        *,
        schema: dict[str, Any] | None = None,
        temperature: float = 0.2,
        timeout: int = _DEFAULT_TIMEOUT,
    ) -> ChatResponse:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system + _JSON_NUDGE},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        try:
            resp = requests.post(
                f"{self._base_url}/chat/completions",
                headers=headers, json=payload, timeout=timeout,
            )
        except requests.RequestException as exc:
            raise ChatError(f"{self._label}: cannot reach endpoint: {exc}") from exc

        try:
            resp.raise_for_status()
        except requests.HTTPError as exc:
            raise ChatError(f"{self._label}: request failed ({resp.status_code}): {exc}") from exc

        try:
            resp_json = resp.json()
            content = resp_json["choices"][0]["message"]["content"]
            usage = resp_json.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens")
            completion_tokens = usage.get("completion_tokens")
        except (KeyError, IndexError, ValueError) as exc:
            raise ChatError(f"{self._label}: unexpected response shape: {exc}") from exc

        return ChatResponse(
            data=parse_json_object(content),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )


class AnthropicChatClient(ChatClient):
    """Anthropic Messages API via raw HTTP (consistent with the rest of the
    sidecar's request-based provider clients)."""

    _ENDPOINT = "https://api.anthropic.com/v1/messages"
    _VERSION = "2023-06-01"

    def __init__(self, api_key: str, model: str = "claude-haiku-4-5") -> None:
        self._api_key = api_key
        self._model = model

    @property
    def model_name(self) -> str:
        return self._model

    def chat_json(
        self,
        system: str,
        user: str,
        *,
        schema: dict[str, Any] | None = None,
        temperature: float = 0.2,  # accepted for interface parity; not sent
        timeout: int = _DEFAULT_TIMEOUT,
    ) -> ChatResponse:
        payload = {
            "model": self._model,
            "max_tokens": 2048,
            "system": system + _JSON_NUDGE,
            "messages": [{"role": "user", "content": user}],
        }
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": self._VERSION,
            "content-type": "application/json",
        }
        try:
            resp = requests.post(
                self._ENDPOINT, headers=headers, json=payload, timeout=timeout
            )
        except requests.RequestException as exc:
            raise ChatError(f"anthropic: cannot reach endpoint: {exc}") from exc

        try:
            resp.raise_for_status()
        except requests.HTTPError as exc:
            raise ChatError(f"anthropic: request failed ({resp.status_code}): {exc}") from exc

        try:
            data = resp.json()
        except ValueError as exc:
            raise ChatError(f"anthropic: invalid JSON response: {exc}") from exc

        if data.get("stop_reason") == "refusal":
            raise ChatError("anthropic: request was refused by safety classifiers")

        text = "".join(
            block.get("text", "")
            for block in data.get("content", [])
            if block.get("type") == "text"
        )
        usage = data.get("usage", {})
        
        return ChatResponse(
            data=parse_json_object(text),
            prompt_tokens=usage.get("input_tokens"),
            completion_tokens=usage.get("output_tokens"),
        )


class GeminiChatClient(ChatClient):
    """Google Gemini generateContent via raw HTTP, JSON output mode."""

    _BASE = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash") -> None:
        self._api_key = api_key
        self._model = model

    @property
    def model_name(self) -> str:
        return self._model

    def chat_json(
        self,
        system: str,
        user: str,
        *,
        schema: dict[str, Any] | None = None,
        temperature: float = 0.2,
        timeout: int = _DEFAULT_TIMEOUT,
    ) -> ChatResponse:
        url = f"{self._BASE}/models/{self._model}:generateContent?key={self._api_key}"
        gen_config: dict[str, Any] = {
            "responseMimeType": "application/json",
            "temperature": temperature,
        }
        if schema is not None:
            gen_config["responseSchema"] = schema
        payload = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": gen_config,
        }
        try:
            resp = requests.post(url, json=payload, timeout=timeout)
        except requests.RequestException as exc:
            raise ChatError(f"gemini: cannot reach endpoint: {exc}") from exc

        if resp.status_code == 400 and schema is not None:
            # Some models reject responseSchema — retry with plain JSON mode.
            logger.info("Gemini rejected responseSchema, retrying without it")
            return self.chat_json(
                system, user, schema=None, temperature=temperature, timeout=timeout
            )

        try:
            resp.raise_for_status()
        except requests.HTTPError as exc:
            raise ChatError(f"gemini: request failed ({resp.status_code}): {exc}") from exc

        try:
            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            usage = data.get("usageMetadata", {})
        except (KeyError, IndexError, ValueError) as exc:
            raise ChatError(f"gemini: unexpected response shape: {exc}") from exc

        return ChatResponse(
            data=parse_json_object(text),
            prompt_tokens=usage.get("promptTokenCount"),
            completion_tokens=usage.get("candidatesTokenCount"),
        )


class FallbackChatClient(ChatClient):
    """Tries each client in order, falling through to the next on ChatError or
    when a provider is over its configured rate limit / disabled.

    Records which provider actually answered so callers can log it.
    """

    def __init__(self, clients: list[ChatClient], limiter: Any | None = None) -> None:
        if not clients:
            raise ValueError("FallbackChatClient requires at least one client")
        self._clients = clients
        self._limiter = limiter
        self._last_model: str | None = None

    @property
    def model_name(self) -> str:
        if self._last_model is not None:
            return self._last_model
        return "+".join(c.model_name for c in self._clients)

    def chat_json(
        self,
        system: str,
        user: str,
        *,
        schema: dict[str, Any] | None = None,
        temperature: float = 0.2,
        timeout: int = _DEFAULT_TIMEOUT,
    ) -> ChatResponse:
        last_error: ChatError | None = None
        attempted = False
        for client in self._clients:
            if self._limiter is not None and not self._limiter.allow(client.provider_key):
                logger.info(
                    "Chat provider '%s' rate-limited or disabled — skipping",
                    client.provider_key,
                )
                continue
            attempted = True
            try:
                result = client.chat_json(
                    system, user, schema=schema,
                    temperature=temperature, timeout=timeout,
                )
                self._last_model = client.model_name
                self.provider_key = client.provider_key
                return result
            except ChatError as exc:
                logger.warning(
                    "Chat provider '%s' failed (%s) — falling back to next",
                    client.model_name, exc,
                )
                last_error = exc
        if last_error is not None:
            raise last_error
        if not attempted:
            raise ChatError(
                "All chat providers are rate-limited or disabled. Adjust limits "
                "on the Provider Limits panel or wait for the window to reset."
            )
        raise ChatError("no chat providers available")

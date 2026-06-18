from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any

import requests

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 180


class ChatError(RuntimeError):
    """Raised when a chat model is unavailable or returns unusable output."""


def parse_json_object(content: str) -> dict[str, Any]:
    """Parse a model response into a JSON object, recovering from prose wrapping.

    Raises ChatError on anything that isn't a usable JSON object.
    """
    content = (content or "").strip()
    if not content:
        raise ChatError("Chat model returned empty content")
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        # Models occasionally wrap JSON in prose or code fences — recover the
        # outermost {...} span and try once more before giving up.
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end > start:
            try:
                parsed = json.loads(content[start : end + 1])
            except json.JSONDecodeError as exc:
                raise ChatError(f"Chat model did not return valid JSON: {exc}") from exc
        else:
            raise ChatError("Chat model did not return a JSON object")

    if not isinstance(parsed, dict):
        raise ChatError("Chat model returned non-object JSON")
    return parsed


class ChatClient(ABC):
    """A provider-agnostic structured-JSON chat client.

    Implementations take a system + user prompt and return a parsed JSON object,
    or raise ChatError. They never leak provider-specific exceptions.
    """

    # Set by the factory; used by the rate limiter to key on the provider.
    provider_key: str = "unknown"

    @property
    @abstractmethod
    def model_name(self) -> str: ...

    @abstractmethod
    def chat_json(
        self,
        system: str,
        user: str,
        *,
        schema: dict[str, Any] | None = None,
        temperature: float = 0.2,
        timeout: int = _DEFAULT_TIMEOUT,
    ) -> dict[str, Any]: ...


class OllamaChatClient(ChatClient):
    """Local Ollama /api/chat with structured JSON output.

    Uses ``format: "json"`` (or a JSON schema when supported) so the model is
    constrained to emit a single parseable JSON object.
    """

    def __init__(self, base_url: str, model: str) -> None:
        self._base_url = base_url.rstrip("/")
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
    ) -> dict[str, Any]:
        fmt: Any = schema if schema is not None else "json"
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "format": fmt,
            "stream": False,
            "options": {"temperature": temperature},
        }

        try:
            resp = requests.post(
                f"{self._base_url}/api/chat", json=payload, timeout=timeout
            )
        except requests.RequestException as exc:
            raise ChatError(f"Cannot reach Ollama chat endpoint: {exc}") from exc

        if resp.status_code == 404:
            body = resp.text or ""
            if "not found" in body or "pull" in body.lower():
                raise ChatError(
                    f"Chat model '{self._model}' is not available in Ollama. "
                    f"Run: ollama pull {self._model}"
                )
            if schema is not None:
                logger.info("Ollama rejected schema format, retrying with format=json")
                return self.chat_json(
                    system, user, schema=None, temperature=temperature, timeout=timeout
                )

        try:
            resp.raise_for_status()
        except requests.HTTPError as exc:
            raise ChatError(f"Ollama chat request failed: {exc}") from exc

        try:
            content = resp.json()["message"]["content"]
        except (KeyError, ValueError) as exc:
            raise ChatError(f"Unexpected Ollama chat response shape: {exc}") from exc

        return parse_json_object(content)

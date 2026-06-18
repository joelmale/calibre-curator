from __future__ import annotations

import json
import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 180


class ChatError(RuntimeError):
    """Raised when the chat model is unavailable or returns unusable output."""


class OllamaChatClient:
    """Thin wrapper over Ollama's /api/chat with structured JSON output.

    Uses ``format: "json"`` (or a JSON schema when supported) so the model is
    constrained to emit a single parseable JSON object. Callers get a dict back
    or a ChatError — never a raw HTTP exception or a half-parsed string.
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
        """Send a system+user prompt and return the parsed JSON object.

        schema — optional JSON schema passed to Ollama's structured-output mode
                 (Ollama >= 0.5). Falls back to plain ``format: "json"`` for
                 older servers that reject a schema object.
        """
        # Ollama accepts either format="json" or format=<json schema>.
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
            # A schema-format request can 404 on older Ollama; retry plain JSON.
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

        return self._parse_json(content)

    @staticmethod
    def _parse_json(content: str) -> dict[str, Any]:
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
                    raise ChatError(
                        f"Chat model did not return valid JSON: {exc}"
                    ) from exc
            else:
                raise ChatError("Chat model did not return a JSON object")

        if not isinstance(parsed, dict):
            raise ChatError("Chat model returned non-object JSON")
        return parsed

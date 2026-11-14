"""Adapter for any OpenAI-style /chat/completions endpoint."""
from __future__ import annotations

import httpx

from .base import LLMError, post_json_with_retry

DEFAULT_BASE = "https://api.openai.com/v1"


class OpenAICompatClient:
    def __init__(self, api_key: str, model: str, base_url: str = "", timeout_s: float = 60.0,
                 temperature: float = 0.8):
        self.model = model
        self.name = f"openai_compat:{model}"
        self._base = (base_url or DEFAULT_BASE).rstrip("/")
        self._key = api_key
        self._temperature = temperature
        self._http = httpx.AsyncClient(timeout=timeout_s)

    async def complete_json(self, system: str, user: str) -> str:
        payload = {
            "model": self.model,
            "temperature": self._temperature,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        data = await post_json_with_retry(
            self._http,
            f"{self._base}/chat/completions",
            headers={"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"},
            payload=payload,
        )
        choices = data.get("choices") or []
        if not choices:
            raise LLMError("The model returned no answer.")
        text = ((choices[0].get("message") or {}).get("content")) or ""
        if not text.strip():
            raise LLMError("The model returned an empty answer.")
        return text

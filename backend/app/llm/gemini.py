"""Google Gemini adapter (Generative Language API, REST, JSON mode)."""
from __future__ import annotations

import httpx

from .base import LLMError, post_json_with_retry

DEFAULT_BASE = "https://generativelanguage.googleapis.com/v1beta"


class GeminiClient:
    def __init__(self, api_key: str, model: str, base_url: str = "", timeout_s: float = 60.0,
                 temperature: float = 0.8):
        self.model = model
        self.name = f"gemini:{model}"
        self._base = (base_url or DEFAULT_BASE).rstrip("/")
        self._key = api_key
        self._temperature = temperature
        self._http = httpx.AsyncClient(timeout=timeout_s)

    async def complete_json(self, system: str, user: str) -> str:
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "temperature": self._temperature,
                "responseMimeType": "application/json",
            },
        }
        data = await post_json_with_retry(
            self._http,
            f"{self._base}/models/{self.model}:generateContent",
            # Key goes in a header, not the URL, so it can't leak into logs.
            headers={"x-goog-api-key": self._key, "Content-Type": "application/json"},
            payload=payload,
        )

        block = (data.get("promptFeedback") or {}).get("blockReason")
        if block:
            raise LLMError(f"The model declined to read this passage (blocked: {block}).", retryable=False)

        candidates = data.get("candidates") or []
        if not candidates:
            raise LLMError("The model returned no answer.")
        cand = candidates[0]
        parts = (cand.get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
        if not text.strip():
            reason = cand.get("finishReason", "unknown")
            raise LLMError(
                f"The model returned an empty answer (finish reason: {reason}).",
                retryable=reason not in {"SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII"},
            )
        return text

"""Provider-agnostic LLM interface.

Everything above this layer (personas, engine) only knows `LLMClient`, so
swapping providers means adding one small adapter and a line in `factory.py`.
"""
from __future__ import annotations

import asyncio
from typing import Any, Protocol

import httpx


class LLMError(Exception):
    """A failed model call. `retryable` tells the engine whether trying again can help."""

    def __init__(self, message: str, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


class FatalLLMError(LLMError):
    """Misconfiguration (bad key, unknown model, bad request). Retrying every
    remaining segment would just repeat the failure, so the whole run aborts."""

    def __init__(self, message: str):
        super().__init__(message, retryable=False)


class LLMClient(Protocol):
    name: str  # e.g. "gemini:<model>" — shown in the UI

    async def complete_json(self, system: str, user: str) -> str:
        """Return the model's raw text, which should be a single JSON object."""
        ...


_TRANSIENT = {408, 409, 425, 429, 500, 502, 503, 504}
_FATAL = {400, 401, 403, 404}


def _error_detail(resp: httpx.Response) -> str:
    try:
        body = resp.json()
        err = body.get("error", body)
        if isinstance(err, dict):
            return str(err.get("message") or err)[:300]
        return str(err)[:300]
    except Exception:
        return resp.text[:300]


async def post_json_with_retry(
    http: httpx.AsyncClient,
    url: str,
    *,
    headers: dict[str, str],
    payload: dict[str, Any],
    retries: int = 2,
) -> dict[str, Any]:
    """POST JSON, retrying transient failures (429/5xx/timeouts) with backoff.

    Raises FatalLLMError for 400/401/403/404, LLMError otherwise. The API key is
    in headers and is never included in error messages.
    """
    last = "unknown error"
    for attempt in range(retries + 1):
        try:
            resp = await http.post(url, headers=headers, json=payload)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            last = f"network problem talking to the model ({type(exc).__name__})"
        else:
            if resp.status_code < 300:
                try:
                    return resp.json()
                except ValueError as exc:
                    raise LLMError("The model API returned a non-JSON response.") from exc
            detail = _error_detail(resp)
            if resp.status_code in _FATAL:
                raise FatalLLMError(f"Model API rejected the request ({resp.status_code}): {detail}")
            last = f"model API error {resp.status_code}: {detail}"
            if resp.status_code not in _TRANSIENT:
                raise LLMError(last, retryable=False)
        if attempt < retries:
            await asyncio.sleep(1.0 * (3**attempt))  # 1s, 3s
    raise LLMError(last)

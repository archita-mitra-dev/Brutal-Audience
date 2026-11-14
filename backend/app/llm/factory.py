from __future__ import annotations

from ..config import Settings
from .base import LLMClient
from .gemini import GeminiClient
from .openai_compat import OpenAICompatClient


def get_llm_client(s: Settings) -> LLMClient | None:
    """Return a configured client, or None when no key/model is set (demo mode)."""
    if not s.llm_configured:
        return None
    kwargs = dict(
        api_key=s.llm_api_key,
        model=s.llm_model,
        base_url=s.llm_base_url,
        timeout_s=s.llm_timeout_s,
        temperature=s.llm_temperature,
    )
    provider = s.llm_provider.lower()
    if provider == "gemini":
        return GeminiClient(**kwargs)
    if provider in {"openai_compat", "openai"}:
        return OpenAICompatClient(**kwargs)
    raise ValueError(f"Unknown LLM_PROVIDER '{s.llm_provider}'. Use 'gemini' or 'openai_compat'.")

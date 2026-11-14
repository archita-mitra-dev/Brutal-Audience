"""Application settings, loaded from environment variables / .env.

Secrets (the LLM key) live only here on the server and are never sent to the
frontend.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_path: str = "./brutal_audience.db"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    max_content_chars: int = 60_000
    max_segments: int = 80

    # --- LLM (Phase 2) -------------------------------------------------------
    # "gemini" (Google Generative Language API) or "openai_compat" (any
    # OpenAI-style /chat/completions endpoint: OpenAI, Groq, OpenRouter, ...).
    llm_provider: str = "gemini"
    llm_api_key: str = ""
    # Deliberately no default: model IDs get retired. Set it in .env.
    llm_model: str = ""
    # Optional override. Gemini default: https://generativelanguage.googleapis.com/v1beta
    # openai_compat default: https://api.openai.com/v1
    llm_base_url: str = ""
    llm_timeout_s: float = 60.0
    llm_temperature: float = 0.8
    # Extra attempts per reaction when the model returns invalid JSON / bad evidence.
    reaction_max_retries: int = 2

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_api_key and self.llm_model)


@lru_cache
def get_settings() -> Settings:
    return Settings()

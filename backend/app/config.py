"""Factora backend configuration.

Environment-only configuration with safe defaults: the app must boot with no
credentials at all and report observability as disabled rather than failing
(neatHack N0 foundation requirement).
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = "development"
    service_name: str = "factora"
    service_version: str = "0.1.0"

    # --- neatlogs (agent observability; key comes from the environment only) ---
    # If absent, the app runs with observability disabled - never an error.
    neatlogs_api_key: str | None = None
    neatlogs_workflow_name: str = "factora-agents"

    # --- LLM (agents, N3) -------------------------------------------------
    # Primary provider is OpenRouter's OpenAI-compatible endpoint. Both the key
    # and the model id come from the environment; the default model id is the
    # provider's free-model alias, never a specific paid model. With no key the
    # agents fall back to a deterministic, clearly-labelled non-LLM model so
    # tests and demos never need the internet or a credit card.
    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    factora_llm_model: str = "openrouter/free"

    # Demo-only failure injection (off by default; never random in production).
    demo_fail_first_work_order: bool = False

    # Hard ceilings on the autonomous loop - keeps free-model usage tiny.
    agent_max_model_calls: int = 6
    agent_max_tool_calls: int = 12

    @field_validator(
        "neatlogs_api_key", "openrouter_api_key", mode="after"
    )
    @classmethod
    def _blank_string_is_none(cls, value: str | None) -> str | None:
        """Treat an empty env var as unset, so `NEATLOGS_API_KEY=` means 'no key'."""
        return value or None

    @field_validator("demo_fail_first_work_order", mode="before")
    @classmethod
    def _blank_flag_is_false(cls, value: object) -> object:
        """`FACTORA_DEMO_FAIL_FIRST_WORK_ORDER=` means 'no injection'."""
        return False if value == "" else value


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor; tests clear via get_settings.cache_clear()."""
    return Settings()

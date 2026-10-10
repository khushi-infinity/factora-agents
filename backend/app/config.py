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

    @field_validator("neatlogs_api_key", mode="after")
    @classmethod
    def _blank_string_is_none(cls, value: str | None) -> str | None:
        """Treat an empty env var as unset, so `NEATLOGS_API_KEY=` means 'no key'."""
        return value or None


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor; tests clear via get_settings.cache_clear()."""
    return Settings()

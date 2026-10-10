"""Unit tests for configuration."""

from __future__ import annotations

from app.config import Settings


def test_defaults_boot_credential_free() -> None:
    """No env vars -> app still configures, with observability unset."""
    settings = Settings()

    assert settings.service_name == "factora"
    assert settings.neatlogs_api_key is None
    assert settings.neatlogs_workflow_name == "factora-agents"


def test_blank_optionals_are_treated_as_unset(monkeypatch) -> None:
    """`NEATLOGS_API_KEY=` in a .env must mean 'no key', not an empty credential."""
    monkeypatch.setenv("NEATLOGS_API_KEY", "")
    settings = Settings()

    assert settings.neatlogs_api_key is None

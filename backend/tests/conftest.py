"""Shared pytest fixtures: credential-free and offline by construction."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app
from app.observability import get_observability, reset_observability


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Pin the environment so suite results never depend on a real .env/config."""
    # neatlogs key must never leak in from a developer shell or a real .env.
    monkeypatch.setenv("NEATLOGS_API_KEY", "")
    # Same for the LLM: the suite runs the deterministic offline model, never
    # OpenRouter, so results stay reproducible and network-free.
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.setenv("FACTORA_DEMO_FAIL_FIRST_WORK_ORDER", "")
    monkeypatch.setenv("APP_ENV", "test")

    get_settings.cache_clear()
    reset_observability()
    yield
    get_settings.cache_clear()
    reset_observability()


@pytest.fixture
def client() -> Iterator[TestClient]:
    """A fresh application instance per test (lifespan runs init/shutdown)."""
    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture
def observability():
    """The live Observability singleton for assertions."""
    return get_observability()

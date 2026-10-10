"""Contract tests for the N0 API surface."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_health_is_ok_without_any_credentials(client: TestClient) -> None:
    """A clean clone must serve health, with observability *disabled*, not failing."""
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "factora"
    assert body["environment"] == "test"
    assert body["observability"]["provider"] == "neatlogs"
    assert body["observability"]["status"] == "disabled"
    assert "NEATLOGS_API_KEY not set" in body["observability"]["detail"]


def test_health_payload_shape_is_stable(client: TestClient) -> None:
    body = client.get("/api/health").json()

    for key in (
        "status",
        "service",
        "version",
        "environment",
        "time_utc",
        "uptime_s",
        "observability",
    ):
        assert key in body, f"missing key in health payload: {key}"
    assert isinstance(body["uptime_s"], (int, float))


def test_liveness_touches_no_dependency(client: TestClient) -> None:
    body = client.get("/api/health/live").json()

    assert body["status"] == "ok"
    assert body["service"] == "factora"
    assert "observability" not in body  # liveness must stay dependency-free


def test_openapi_exposes_health_routes(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]

    assert "/api/health" in paths
    assert "/api/health/live" in paths


def test_cors_allows_the_vite_dev_origin(client: TestClient) -> None:
    response = client.get("/api/health/live", headers={"Origin": "http://localhost:5173"})

    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_does_not_echo_an_unknown_origin(client: TestClient) -> None:
    response = client.get("/api/health/live", headers={"Origin": "https://evil.example"})

    assert response.headers.get("access-control-allow-origin") is None


@pytest.mark.parametrize(
    "secret",
    ["sk-test-super-secret-key", "neatlogs-key-value"],
)
def test_health_never_exposes_the_neatlogs_key(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    secret: str,
) -> None:
    """A configured neatlogs key must never appear in any response (docs rule 5)."""
    monkeypatch.setenv("NEATLOGS_API_KEY", secret)

    from app.config import get_settings

    get_settings.cache_clear()

    response = client.get("/api/health")

    assert response.status_code == 200
    assert secret not in response.text

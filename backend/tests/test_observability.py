"""Unit tests for the isolated neatlogs observability foundation."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.config import Settings
from app.observability import Observability, reset_observability


def _settings_with_key() -> Settings:
    return Settings(app_env="test", neatlogs_api_key="test-key-123")


def test_disabled_without_key() -> None:
    obs = Observability()
    settings = Settings(app_env="test", neatlogs_api_key=None)

    status = obs.init(settings)

    assert status == "disabled"
    assert obs.status == "disabled"
    assert obs.initialized is False
    assert obs.detail is not None and "NEATLOGS_API_KEY not set" in obs.detail


def test_init_succeeds_with_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Credentials present -> init is attempted; span() returns the real decorator."""
    reset_observability()
    calls: dict[str, object] = {}

    fake_module = SimpleNamespace(
        init=lambda **kw: calls.update(kw) or None,
        span=lambda **kw: (lambda fn: fn),
        flush=lambda: None,
        shutdown=lambda: None,
    )

    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "neatlogs":
            return fake_module
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    obs = Observability()
    status = obs.init(_settings_with_key())

    assert status == "active"
    assert obs.initialized is True
    assert calls["api_key"] == "test-key-123"
    assert calls["workflow_name"] == Settings().neatlogs_workflow_name

    def sample() -> str:
        return "ran"

    assert obs.span("AGENT", name="x")(sample)() == "ran"


def test_init_failure_degrades_to_error_never_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_observability()
    import builtins

    def broken_init(**_kw):
        raise RuntimeError("network unavailable")

    fake_module = SimpleNamespace(
        init=broken_init,
        span=lambda **kw: (lambda fn: fn),
        flush=lambda: None,
        shutdown=lambda: None,
    )
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "neatlogs":
            return fake_module
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    obs = Observability()
    status = obs.init(_settings_with_key())

    assert status == "error"
    assert obs.status == "error"
    assert obs.initialized is False
    assert "network unavailable" in (obs.detail or "")


def test_span_is_passthrough_when_disabled() -> None:
    obs = Observability()  # never initialized

    def sample() -> str:
        return "ran"

    assert obs.span("TOOL", name="t")(sample)() == "ran"


def test_shutdown_is_safe_when_never_initialized() -> None:
    obs = Observability()
    obs.shutdown()  # must not raise

    assert obs.status == "disabled"


def test_shutdown_calls_flush_and_shutdown_when_active(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_observability()
    done: list[str] = []
    fake_module = SimpleNamespace(
        init=lambda **kw: None,
        span=lambda **kw: (lambda fn: fn),
        flush=lambda: done.append("flush"),
        shutdown=lambda: done.append("shutdown"),
    )
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "neatlogs":
            return fake_module
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    obs = Observability()
    obs.init(_settings_with_key())
    obs.shutdown()

    assert done == ["flush", "shutdown"]
    assert obs.status == "disabled"
    assert obs.initialized is False


def test_app_lifespan_initializes_and_shuts_down(client) -> None:
    """TestClient startup runs lifespan: with no key the singleton stays disabled."""
    from app.observability import get_observability

    obs = get_observability()
    assert obs.status == "disabled"
    assert obs.initialized is False

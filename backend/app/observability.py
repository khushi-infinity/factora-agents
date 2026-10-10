"""neatlogs observability foundation (isolated, credential-safe).

Verified against the official Python SDK docs (docs.neatlogs.com/sdk/python,
fetched 2026-10-10):

  * install:              pip install -U neatlogs
  * local doctor check:   python -m neatlogs doctor --local --json
  * authenticated probe:  python -m neatlogs doctor --probe --json (needs key)
  * init:                 neatlogs.init(api_key=..., workflow_name=...)
  * custom spans:         @neatlogs.span(kind="AGENT"/"TOOL"/"WORKFLOW", ...)
  * shutdown:             neatlogs.flush() + neatlogs.shutdown() (FastAPI lifespan)

Design rules (neatHack N0):

  * credentials come from the environment only (NEATLOGS_API_KEY), never from code;
  * a missing key means observability is DISABLED, not that the app fails;
  * this module never fabricates a successful upload: init() is attempted only
    when a key exists, and failures surface as status "error" with the message;
  * agent/tool span helpers live here so the later agent milestones have one
    instrumentation point. No fake agent calls exist yet (N0 scope).
"""

from __future__ import annotations

import logging
from typing import Any

from .config import Settings, get_settings

logger = logging.getLogger(__name__)

# States the rest of the app (and the EVIDENCE docs) may rely on.
OBSERVABILITY_STATUS = ("disabled", "active", "error")


class Observability:
    """One place that owns neatlogs init state for the whole process."""

    def __init__(self) -> None:
        self._initialized = False
        self._status: str = "disabled"
        self._detail: str | None = None

    @property
    def status(self) -> str:
        return self._status

    @property
    def detail(self) -> str | None:
        return self._detail

    @property
    def initialized(self) -> bool:
        return self._initialized

    def init(self, settings: Settings | None = None) -> str:
        """Initialize neatlogs if, and only if, an API key is present.

        Returns the status string. Never raises.
        """
        settings = settings or get_settings()

        if not settings.neatlogs_api_key:
            self._status = "disabled"
            self._detail = "NEATLOGS_API_KEY not set - observability disabled (app runs normally)"
            return self._status

        try:
            import neatlogs

            neatlogs.init(
                api_key=settings.neatlogs_api_key,
                workflow_name=settings.neatlogs_workflow_name,
            )
            self._initialized = True
            self._status = "active"
            self._detail = f"neatlogs initialized (workflow={settings.neatlogs_workflow_name})"
        except Exception as exc:  # noqa: BLE001 - an observability outage must never take the app down
            self._status = "error"
            self._detail = f"{type(exc).__name__}: {exc}"
            logger.warning("neatlogs init failed; continuing without it: %s", exc)
        return self._status

    def shutdown(self) -> None:
        """Flush + shutdown on server stop (FastAPI lifespan), per the SDK docs."""
        if not self._initialized:
            return
        try:
            import neatlogs

            neatlogs.flush()
            neatlogs.shutdown()
        except Exception as exc:  # noqa: BLE001
            logger.warning("neatlogs shutdown failed: %s", exc)
        finally:
            self._initialized = False
            self._status = "disabled"
            self._detail = "neatlogs shut down"

    def span(self, kind: str, **kwargs: Any):
        """Return the real neatlogs decorator when active; passthrough when not.

        Reads live state at call time so tests can toggle instrumentation.
        """
        if not self.initialized:
            return _passthrough_decorator
        import neatlogs

        return neatlogs.span(kind=kind, **kwargs)


def _passthrough_decorator(func):
    return func


_observability = Observability()


def get_observability() -> Observability:
    return _observability


def reset_observability() -> None:
    """Test helper: force a fresh state (used by pytest fixtures)."""
    global _observability
    _observability = Observability()

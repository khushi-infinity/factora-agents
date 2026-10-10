"""Health routes - the N0 API surface.

/api/health/live  - no dependencies touched (liveness)
/api/health       - application + observability status, honestly reported
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

from fastapi import APIRouter

from ..config import get_settings
from ..observability import get_observability

router = APIRouter(tags=["health"])

_STARTED_MONOTONIC = time.monotonic()


def _now() -> datetime:
    return datetime.now(UTC)


def _uptime_s() -> float:
    return round(time.monotonic() - _STARTED_MONOTONIC, 3)


@router.get("/health/live")
def liveness() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.service_name,
        "version": settings.service_version,
        "time_utc": _now().isoformat(),
        "uptime_s": _uptime_s(),
    }


@router.get("/health")
def health() -> dict:
    """Readiness: reports the app state plus observability status honestly.

    A missing neatlogs key is *disabled*, not an error. A failed neatlogs init
    is reported as degraded, but the app itself stays healthy - the N0 contract
    is that observability failure never fails the product.
    """
    settings = get_settings()
    obs = get_observability()

    app_status = "ok" if obs.status in {"active", "disabled"} else "degraded"

    return {
        "status": app_status,
        "service": settings.service_name,
        "version": settings.service_version,
        "environment": settings.app_env,
        "time_utc": _now().isoformat(),
        "uptime_s": _uptime_s(),
        "observability": {
            "provider": "neatlogs",
            "status": obs.status,
            "detail": obs.detail,
        },
    }

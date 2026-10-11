"""Factora FastAPI application factory (N0 scaffold).

Run in development:
    cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

The app boots with an empty environment: no LLM keys, no neatlogs key, no
network. neatlogs is initialized at startup when NEATLOGS_API_KEY is present
and flushed/shutdown cleanly on server stop (FastAPI lifespan, per the SDK
docs for long-running servers).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.agents import router as agents_router
from .api.factory import router as factory_router
from .api.health import router as health_router
from .config import get_settings
from .observability import get_observability


def create_app() -> FastAPI:
    settings = get_settings()
    observability = get_observability()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        observability.init(settings)
        yield
        observability.shutdown()

    app = FastAPI(
        title="Factora API",
        version=settings.service_version,
        description=(
            "Backend for Factora - an autonomous factory operating system built "
            "around a digital twin and cooperating AI agents (neatHack 2026). "
            "N0 scaffold: health endpoints only."
        ),
        docs_url="/docs",
        redoc_url=None,
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["*"],
    )

    app.include_router(health_router, prefix="/api")
    app.include_router(factory_router, prefix="/api")
    app.include_router(agents_router, prefix="/api")

    return app


app = create_app()

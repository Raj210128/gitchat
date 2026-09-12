"""
GitHub Repository Chat Assistant – FastAPI entry point.
"""
from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.qdrant_client import get_qdrant_client

log = structlog.get_logger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    log.info("startup", env=settings.ENV, version=settings.API_VERSION)

    # Verify Qdrant is reachable
    try:
        client = get_qdrant_client()
        client.get_collections()
        log.info("qdrant.connected", url=settings.QDRANT_URL)
    except Exception as exc:  # noqa: BLE001
        log.warning("qdrant.unreachable", error=str(exc))

    yield

    log.info("shutdown")


# ── App factory ────────────────────────────────────────────────────────────────
def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.API_VERSION,
        description=(
            "Production-grade RAG assistant for GitHub repositories. "
            "AST-based chunking · Hybrid retrieval · SSE streaming."
        ),
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── API routes ────────────────────────────────────────────────────────────
    app.include_router(api_router, prefix=settings.API_PREFIX)

    # ── Health check (outside versioned prefix for load-balancer probes) ──────
    @app.get("/health", tags=["Health"], summary="Liveness probe")
    async def health() -> dict:
        return {
            "status": "ok",
            "version": settings.API_VERSION,
            "env": settings.ENV,
        }

    return app


app = create_app()

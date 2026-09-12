"""
Ingestion API endpoints.

POST /api/v1/ingest        – Start an ingestion job (returns job_id)
GET  /api/v1/ingest/{job_id} – Poll job status
"""
from __future__ import annotations

import asyncio
from typing import Annotated

import redis.asyncio as aioredis
import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import settings
from app.models.schemas import IngestRequest, IngestStatusResponse, IngestStatus
from app.services.ingest_service import get_job_status, run_ingest

log = structlog.get_logger(__name__)
router = APIRouter()


# ── Redis dependency ──────────────────────────────────────────────────────────
async def get_redis() -> aioredis.Redis:
    client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()


# ── Background task wrapper ──────────────────────────────────────────────────
async def _run_ingest_with_own_redis(
    job_id: str, repo_url: str, branch: str, force_reindex: bool
) -> None:
    """
    Wrapper that creates its own Redis connection for the background task.
    The request-scoped connection from Depends(get_redis) gets closed when
    the HTTP response is sent, so background tasks must use their own.
    """
    bg_redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        await run_ingest(
            job_id=job_id,
            repo_url=repo_url,
            branch=branch,
            force_reindex=force_reindex,
            redis=bg_redis,
        )
    finally:
        await bg_redis.aclose()


# ── Endpoints ─────────────────────────────────────────────────────────────────
@router.post(
    "",
    response_model=IngestStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start repository ingestion",
    description=(
        "Clone and index a GitHub repository. "
        "Returns a `job_id` to poll for status."
    ),
)
async def start_ingest(
    body: IngestRequest,
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
) -> IngestStatusResponse:
    log.info(
        "ingest.request",
        repo_url=str(body.repo_url),
        branch=body.branch,
        force=body.force_reindex,
    )
    # Fire-and-forget — uses its own Redis connection so it survives after response
    job_id = str(__import__("uuid").uuid4())
    asyncio.create_task(
        _run_ingest_with_own_redis(
            job_id=job_id,
            repo_url=str(body.repo_url),
            branch=body.branch,
            force_reindex=body.force_reindex,
        )
    )
    return IngestStatusResponse(
        job_id=job_id,
        status=IngestStatus.PENDING,
        repo_url=str(body.repo_url),
        branch=body.branch,
    )


@router.get(
    "/{job_id}",
    response_model=IngestStatusResponse,
    summary="Poll ingestion job status",
)
async def get_ingest_status(
    job_id: str,
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
) -> IngestStatusResponse:
    state = await get_job_status(redis, job_id)
    if state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found.",
        )
    return IngestStatusResponse(**state)

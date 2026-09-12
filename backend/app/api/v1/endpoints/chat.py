"""
Chat API endpoints.

POST /api/v1/chat         – Synchronous RAG answer
GET  /api/v1/chat/stream  – Server-Sent Events streaming answer
"""
from __future__ import annotations

import json
import time
from typing import Annotated, AsyncIterator

import redis.asyncio as aioredis
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sse_starlette.sse import EventSourceResponse

from app.core.config import settings
from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    SSEEvent,
    SSEEventType,
    SourceReference,
)
from app.rag.chain import generate_answer, stream_answer
from app.rag.retriever import retrieve, store_semantic_cache

log = structlog.get_logger(__name__)
router = APIRouter()


# ── Redis dependency ──────────────────────────────────────────────────────────
async def get_redis() -> aioredis.Redis:
    client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()


# ── Shared retrieval helper ───────────────────────────────────────────────────
async def _do_retrieve(
    question: str,
    repo_id: str,
    top_k: int,
    redis: aioredis.Redis,
):
    """Returns (sources, cache_hit, cached_answer)."""
    return await retrieve(question, repo_id, top_k, redis)


# ─────────────────────────────────────────────────────────────────────────────
# POST /chat  (synchronous)
# ─────────────────────────────────────────────────────────────────────────────
@router.post(
    "",
    response_model=ChatResponse,
    summary="Ask a question about a repository (synchronous)",
)
async def chat(
    body: ChatRequest,
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
) -> ChatResponse:
    t0 = time.monotonic()
    sources, cache_hit, cached_answer = await _do_retrieve(
        body.question, body.repo_id, body.top_k, redis
    )

    if cache_hit and cached_answer:
        return ChatResponse(
            answer=cached_answer,
            sources=[],
            cached=True,
            latency_ms=int((time.monotonic() - t0) * 1000),
            repo_id=body.repo_id,
        )

    if not sources:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No relevant code chunks found. Make sure the repository has been ingested.",
        )

    answer = await generate_answer(body.question, sources)

    # Store in semantic cache for future queries
    from app.services.embed_service import embed_query
    q_emb = await embed_query(body.question)
    await store_semantic_cache(q_emb, answer, body.repo_id, redis)

    return ChatResponse(
        answer=answer,
        sources=sources,
        cached=False,
        latency_ms=int((time.monotonic() - t0) * 1000),
        repo_id=body.repo_id,
    )


# ─────────────────────────────────────────────────────────────────────────────
# GET /chat/stream  (Server-Sent Events)
# ─────────────────────────────────────────────────────────────────────────────
@router.get(
    "/stream",
    summary="Stream an answer about a repository via SSE",
    response_class=EventSourceResponse,
)
async def chat_stream(
    repo_id: str = Query(..., description="Repository ID returned by /ingest"),
    question: str = Query(..., min_length=3, max_length=2000),
    top_k: int = Query(default=8, ge=1, le=25),
    redis: aioredis.Redis = Depends(get_redis),
) -> EventSourceResponse:

    async def _event_generator() -> AsyncIterator[dict]:
        sources, cache_hit, cached_answer = await _do_retrieve(
            question, repo_id, top_k, redis
        )

        # ── Cache hit: stream the cached answer token-by-token ────────────────
        if cache_hit and cached_answer:
            yield {
                "event": SSEEventType.SOURCES,
                "data": json.dumps([]),   # No fresh sources for cache hit
            }
            for word in cached_answer.split(" "):
                yield {
                    "event": SSEEventType.TOKEN,
                    "data": word + " ",
                }
            yield {"event": SSEEventType.DONE, "data": ""}
            return

        # ── No chunks found ───────────────────────────────────────────────────
        if not sources:
            yield {
                "event": SSEEventType.ERROR,
                "data": "No relevant code chunks found. Ingest the repository first.",
            }
            return

        # ── Send sources payload first ────────────────────────────────────────
        yield {
            "event": SSEEventType.SOURCES,
            "data": json.dumps([s.model_dump() for s in sources]),
        }

        # ── Stream LLM tokens ─────────────────────────────────────────────────
        full_answer_parts: list[str] = []
        async for token in stream_answer(question, sources):
            full_answer_parts.append(token)
            yield {
                "event": SSEEventType.TOKEN,
                "data": token,
            }

        # ── Cache completed answer ────────────────────────────────────────────
        full_answer = "".join(full_answer_parts)
        from app.services.embed_service import embed_query
        q_emb = await embed_query(question)
        await store_semantic_cache(q_emb, full_answer, repo_id, redis)

        yield {"event": SSEEventType.DONE, "data": ""}

    return EventSourceResponse(_event_generator())

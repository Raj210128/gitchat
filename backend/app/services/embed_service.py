"""
Embedding service: batched async OpenAI text-embedding calls with retries.
"""
from __future__ import annotations

import asyncio
from typing import List

import structlog
from openai import AsyncOpenAI
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings

log = structlog.get_logger(__name__)

# Module-level async client (one instance per process)
_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


# ── Retry decorator ───────────────────────────────────────────────────────────
@retry(
    reraise=True,
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    retry=retry_if_exception_type(Exception),
)
async def _embed_batch(texts: List[str]) -> List[List[float]]:
    """Call OpenAI Embeddings API for a single batch of texts."""
    response = await _get_client().embeddings.create(
        model=settings.OPENAI_EMBEDDING_MODEL,
        input=texts,
        dimensions=settings.EMBEDDING_DIMENSION,
    )
    return [item.embedding for item in sorted(response.data, key=lambda x: x.index)]


# ── Public API ────────────────────────────────────────────────────────────────
async def embed_texts(
    texts: List[str],
    batch_size: int = 128,
    concurrency: int = 4,
) -> List[List[float]]:
    """
    Embed *texts* using batched concurrent OpenAI calls.
    Returns a flat list of embeddings in the same order as *texts*.
    """
    if not texts:
        return []

    # Chunk into batches
    batches = [texts[i: i + batch_size] for i in range(0, len(texts), batch_size)]

    # Use a semaphore to limit concurrent API calls
    sem = asyncio.Semaphore(concurrency)

    async def _bounded(batch: List[str]) -> List[List[float]]:
        async with sem:
            return await _embed_batch(batch)

    results = await asyncio.gather(*[_bounded(b) for b in batches])

    # Flatten
    embeddings: List[List[float]] = []
    for batch_result in results:
        embeddings.extend(batch_result)

    log.info(
        "embed_service.done",
        total=len(texts),
        batches=len(batches),
    )
    return embeddings


async def embed_query(query: str) -> List[float]:
    """Embed a single query string (used by retriever + semantic cache)."""
    embeddings = await embed_texts([query])
    return embeddings[0]

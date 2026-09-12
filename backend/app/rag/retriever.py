"""
Hybrid retrieval: Dense (Qdrant) + Sparse (BM25) fused via Reciprocal Rank Fusion.
Also handles Redis semantic cache lookup.
"""
from __future__ import annotations

import json
import math
from typing import List, Optional, Tuple

import numpy as np
import structlog
from rank_bm25 import BM25Okapi
from qdrant_client.http.models import Filter, FieldCondition, MatchValue, SearchParams

from app.core.config import settings
from app.db.qdrant_client import get_qdrant_client
from app.models.schemas import ChunkMetadata, NodeType, SourceReference
from app.services.embed_service import embed_query

log = structlog.get_logger(__name__)

# ── Redis cache key helpers ───────────────────────────────────────────────────
_CACHE_PREFIX = "semantic_cache"
_BM25_PREFIX = "bm25_corpus"


# ─────────────────────────────────────────────────────────────────────────────
# Semantic Cache
# ─────────────────────────────────────────────────────────────────────────────
async def check_semantic_cache(
    query_embedding: List[float],
    repo_id: str,
    redis,
) -> Optional[str]:
    """
    Search Redis for a semantically cached response.
    Returns the cached answer string if similarity > threshold, else None.
    """
    cache_key = f"{_CACHE_PREFIX}:{repo_id}"
    try:
        raw = await redis.get(cache_key)
        if not raw:
            return None
        entries: list = json.loads(raw)
        q_vec = np.array(query_embedding)
        for entry in entries:
            cached_vec = np.array(entry["embedding"])
            # Cosine similarity
            sim = float(
                np.dot(q_vec, cached_vec)
                / (np.linalg.norm(q_vec) * np.linalg.norm(cached_vec) + 1e-9)
            )
            if sim >= settings.SEMANTIC_CACHE_THRESHOLD:
                log.info("cache.hit", repo_id=repo_id, similarity=round(sim, 4))
                return entry["answer"]
    except Exception as exc:  # noqa: BLE001
        log.warning("cache.error", error=str(exc))
    return None


async def store_semantic_cache(
    query_embedding: List[float],
    answer: str,
    repo_id: str,
    redis,
) -> None:
    """Store a query embedding + answer pair in Redis semantic cache."""
    cache_key = f"{_CACHE_PREFIX}:{repo_id}"
    try:
        raw = await redis.get(cache_key)
        entries: list = json.loads(raw) if raw else []
        entries.append({"embedding": query_embedding, "answer": answer})
        # Keep only the last 1000 entries per repo to avoid unbounded growth
        entries = entries[-1000:]
        await redis.setex(
            cache_key,
            settings.CACHE_TTL_SECONDS,
            json.dumps(entries),
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("cache.store_error", error=str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# Dense Retriever (Qdrant)
# ─────────────────────────────────────────────────────────────────────────────
async def dense_search(
    query_embedding: List[float],
    repo_id: str,
    top_k: int,
) -> List[Tuple[ChunkMetadata, float]]:
    """Vector similarity search in Qdrant filtered by repo_id."""
    client = get_qdrant_client()
    results = client.search(
        collection_name=settings.QDRANT_COLLECTION_NAME,
        query_vector=query_embedding,
        query_filter=Filter(
            must=[FieldCondition(key="repo_id", match=MatchValue(value=repo_id))]
        ),
        limit=top_k,
        score_threshold=settings.SCORE_THRESHOLD,
        search_params=SearchParams(hnsw_ef=128, exact=False),
        with_payload=True,
    )
    out: list[Tuple[ChunkMetadata, float]] = []
    for hit in results:
        try:
            metadata = ChunkMetadata(**hit.payload)
            out.append((metadata, hit.score))
        except Exception as exc:  # noqa: BLE001
            log.warning("dense.parse_error", error=str(exc))
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Sparse Retriever (BM25)
# ─────────────────────────────────────────────────────────────────────────────
async def _load_bm25_corpus(repo_id: str, redis) -> Tuple[BM25Okapi | None, List[ChunkMetadata]]:
    """
    Load a serialised BM25 corpus from Redis.
    If absent, scroll all Qdrant chunks for this repo and build it.
    """
    corpus_key = f"{_BM25_PREFIX}:{repo_id}"
    try:
        raw = await redis.get(corpus_key)
        if raw:
            data = json.loads(raw)
            corpus: List[List[str]] = data["corpus"]
            payloads: List[ChunkMetadata] = [ChunkMetadata(**p) for p in data["payloads"]]
            return BM25Okapi(corpus), payloads
    except Exception as exc:  # noqa: BLE001
        log.warning("bm25.cache_miss", repo_id=repo_id, error=str(exc))

    # Build corpus by scrolling Qdrant
    client = get_qdrant_client()
    all_chunks: list[ChunkMetadata] = []
    offset = None
    while True:
        records, offset = client.scroll(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            scroll_filter=Filter(
                must=[FieldCondition(key="repo_id", match=MatchValue(value=repo_id))]
            ),
            limit=256,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        for r in records:
            try:
                all_chunks.append(ChunkMetadata(**r.payload))
            except Exception:  # noqa: BLE001
                pass
        if offset is None:
            break

    if not all_chunks:
        return None, []

    tokenised = [
        (c.import_context + " " + c.code_snippet).lower().split()
        for c in all_chunks
    ]
    bm25 = BM25Okapi(tokenised)

    # Persist to Redis
    try:
        cache_data = {
            "corpus": tokenised,
            "payloads": [c.model_dump() for c in all_chunks],
        }
        await redis.setex(corpus_key, settings.CACHE_TTL_SECONDS, json.dumps(cache_data))
    except Exception as exc:  # noqa: BLE001
        log.warning("bm25.cache_save_error", error=str(exc))

    log.info("bm25.corpus_built", repo_id=repo_id, docs=len(all_chunks))
    return bm25, all_chunks


async def sparse_search(
    query: str,
    repo_id: str,
    top_k: int,
    redis,
) -> List[Tuple[ChunkMetadata, float]]:
    """BM25 keyword retrieval from the in-memory/Redis corpus."""
    bm25, all_chunks = await _load_bm25_corpus(repo_id, redis)
    if bm25 is None:
        return []

    tokens = query.lower().split()
    scores = bm25.get_scores(tokens)

    # Pair and sort
    paired = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
    results: list[Tuple[ChunkMetadata, float]] = []
    for idx, score in paired[:top_k]:
        if score > 0:
            results.append((all_chunks[idx], float(score)))
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Reciprocal Rank Fusion
# ─────────────────────────────────────────────────────────────────────────────
_RRF_K = 60  # Standard RRF constant


def _rrf_fuse(
    dense_results: List[Tuple[ChunkMetadata, float]],
    sparse_results: List[Tuple[ChunkMetadata, float]],
    top_k: int,
    dense_weight: float,
    sparse_weight: float,
) -> List[Tuple[ChunkMetadata, float]]:
    """Merge dense + sparse lists using Reciprocal Rank Fusion."""
    scores: dict[str, float] = {}
    chunks: dict[str, ChunkMetadata] = {}

    for rank, (chunk, _) in enumerate(dense_results):
        rrf = dense_weight * (1.0 / (_RRF_K + rank + 1))
        scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + rrf
        chunks[chunk.chunk_id] = chunk

    for rank, (chunk, _) in enumerate(sparse_results):
        rrf = sparse_weight * (1.0 / (_RRF_K + rank + 1))
        scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + rrf
        chunks[chunk.chunk_id] = chunk

    sorted_ids = sorted(scores, key=lambda cid: scores[cid], reverse=True)
    max_score = scores[sorted_ids[0]] if sorted_ids else 1.0

    return [
        (chunks[cid], scores[cid] / max_score)   # normalise 0-1
        for cid in sorted_ids[:top_k]
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Public interface
# ─────────────────────────────────────────────────────────────────────────────
async def retrieve(
    query: str,
    repo_id: str,
    top_k: int,
    redis,
) -> Tuple[List[SourceReference], bool, Optional[str]]:
    """
    Full retrieval pipeline:
      1. Embed query
      2. Check semantic cache (return immediately on hit)
      3. Dense + Sparse search
      4. RRF fusion
      5. Return SourceReferences + cache_hit flag + query_embedding (for later caching)
    """
    query_embedding = await embed_query(query)

    # ── Semantic cache ────────────────────────────────────────────────────────
    cached_answer = await check_semantic_cache(query_embedding, repo_id, redis)
    if cached_answer is not None:
        return [], True, cached_answer

    # ── Dual retrieval ────────────────────────────────────────────────────────
    dense_res, sparse_res = await _parallel_search(query, query_embedding, repo_id, top_k, redis)

    # ── Fuse ─────────────────────────────────────────────────────────────────
    fused = _rrf_fuse(
        dense_res,
        sparse_res,
        top_k=top_k,
        dense_weight=settings.DENSE_WEIGHT,
        sparse_weight=settings.SPARSE_WEIGHT,
    )

    sources = [
        SourceReference(
            chunk_id=chunk.chunk_id,
            file_path=chunk.file_path,
            start_line=chunk.start_line,
            end_line=chunk.end_line,
            node_type=chunk.node_type,
            node_name=chunk.node_name,
            language=chunk.language,
            score=round(score, 4),
            snippet=chunk.code_snippet[:400],  # trim for response payload
        )
        for chunk, score in fused
    ]

    log.info(
        "retriever.done",
        query=query[:60],
        dense=len(dense_res),
        sparse=len(sparse_res),
        fused=len(sources),
    )
    return sources, False, None


async def _parallel_search(query, query_embedding, repo_id, top_k, redis):
    import asyncio
    dense_task = asyncio.create_task(dense_search(query_embedding, repo_id, top_k))
    sparse_task = asyncio.create_task(sparse_search(query, repo_id, top_k, redis))
    return await asyncio.gather(dense_task, sparse_task)

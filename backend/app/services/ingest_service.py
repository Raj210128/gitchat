"""
Ingest orchestration service.

Pipeline:
  1. Clone GitHub repository
  2. Walk files → AST-chunk each file
  3. Embed all chunks (batched)
  4. Upsert vectors + payloads into Qdrant
  5. Update job status in Redis throughout
"""
from __future__ import annotations

import json
import uuid
from typing import List

import structlog
from qdrant_client.http.models import PointStruct

from app.core.config import settings
from app.db.qdrant_client import ensure_collection, get_qdrant_client
from app.models.schemas import ChunkMetadata, IngestStatus
from app.parser.ast_chunker import chunk_file
from app.services.embed_service import embed_texts
from app.services.github_service import (
    cleanup_clone,
    clone_repository,
    iter_source_files,
)

log = structlog.get_logger(__name__)

# Redis key helpers
_JOB_KEY = "ingest:job:{job_id}"
_JOB_TTL = 86_400  # 24 h


async def _update_status(redis, job_id: str, **fields) -> None:
    key = _JOB_KEY.format(job_id=job_id)
    data = await redis.get(key) or "{}"
    state = json.loads(data)
    state["job_id"] = job_id          # always persist the job_id in the state
    state.update(fields)
    await redis.setex(key, _JOB_TTL, json.dumps(state))


async def get_job_status(redis, job_id: str) -> dict | None:
    key = _JOB_KEY.format(job_id=job_id)
    data = await redis.get(key)
    return json.loads(data) if data else None


# ── UPSERT helper ─────────────────────────────────────────────────────────────
async def _upsert_chunks(
    chunks: List[ChunkMetadata],
    embeddings: List[List[float]],
    collection_name: str,
) -> None:
    client = get_qdrant_client()
    points = [
        PointStruct(
            id=chunk.chunk_id,
            vector=embedding,
            payload=chunk.model_dump(),
        )
        for chunk, embedding in zip(chunks, embeddings)
    ]
    # Upsert in batches of 256 to stay within Qdrant limits
    batch_size = 256
    for i in range(0, len(points), batch_size):
        client.upsert(
            collection_name=collection_name,
            points=points[i: i + batch_size],
        )


# ── Main pipeline ─────────────────────────────────────────────────────────────
async def run_ingest(
    job_id: str,
    repo_url: str,
    branch: str,
    force_reindex: bool,
    redis,
) -> str:
    """
    Start the ingestion pipeline for *repo_url*.
    Runs the full pipeline synchronously inside this coroutine
    (designed to be dispatched via asyncio.create_task).
    Returns the *job_id*.
    """
    local_path: str | None = None
    collection_name = settings.QDRANT_COLLECTION_NAME

    try:
        # ── Init job state ────────────────────────────────────────────────────
        await _update_status(
            redis, job_id,
            status=IngestStatus.PENDING,
            repo_url=str(repo_url),
            branch=branch,
            files_processed=0,
            chunks_indexed=0,
            error=None,
        )

        # ── Ensure Qdrant collection ──────────────────────────────────────────
        ensure_collection(collection_name, force_reindex=force_reindex)

        # ── Clone ─────────────────────────────────────────────────────────────
        await _update_status(redis, job_id, status=IngestStatus.RUNNING)
        local_path, repo_id = clone_repository(str(repo_url), branch)

        # ── Walk + chunk + embed + upsert ─────────────────────────────────────
        all_chunks: List[ChunkMetadata] = []
        files_processed = 0

        for file_path, content, language in iter_source_files(local_path):
            file_chunks = chunk_file(content, file_path, repo_id)
            all_chunks.extend(file_chunks)
            files_processed += 1

            # Flush every 500 chunks to limit memory pressure
            if len(all_chunks) >= 500:
                texts = [
                    f"{c.import_context}\n\n{c.code_snippet}".strip()
                    for c in all_chunks
                ]
                embeddings = await embed_texts(texts)
                await _upsert_chunks(all_chunks, embeddings, collection_name)
                await _update_status(
                    redis, job_id,
                    files_processed=files_processed,
                    chunks_indexed=(
                        (await get_job_status(redis, job_id) or {}).get("chunks_indexed", 0)
                        + len(all_chunks)
                    ),
                )
                log.info(
                    "ingest.flush",
                    job_id=job_id,
                    files=files_processed,
                    chunks=len(all_chunks),
                )
                all_chunks = []

        # ── Flush remainder ───────────────────────────────────────────────────
        if all_chunks:
            texts = [
                f"{c.import_context}\n\n{c.code_snippet}".strip()
                for c in all_chunks
            ]
            embeddings = await embed_texts(texts)
            await _upsert_chunks(all_chunks, embeddings, collection_name)

        final_status = await get_job_status(redis, job_id) or {}
        total_chunks = final_status.get("chunks_indexed", 0) + len(all_chunks)

        await _update_status(
            redis, job_id,
            status=IngestStatus.COMPLETED,
            files_processed=files_processed,
            chunks_indexed=total_chunks,
        )
        log.info(
            "ingest.completed",
            job_id=job_id,
            repo_url=repo_url,
            files=files_processed,
            chunks=total_chunks,
        )

    except Exception as exc:  # noqa: BLE001
        log.error("ingest.failed", job_id=job_id, error=str(exc), exc_info=True)
        await _update_status(
            redis, job_id,
            status=IngestStatus.FAILED,
            error=str(exc),
        )
    finally:
        if local_path:
            cleanup_clone(local_path)

    return job_id

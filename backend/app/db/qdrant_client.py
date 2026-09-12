"""
Qdrant client singleton + collection management helpers.
"""
from __future__ import annotations

import structlog
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.http.models import (
    Distance,
    VectorParams,
    OptimizersConfigDiff,
)

from app.core.config import settings

log = structlog.get_logger(__name__)

_client: QdrantClient | None = None


def get_qdrant_client() -> QdrantClient:
    """Return the process-level Qdrant singleton."""
    global _client
    if _client is None:
        kwargs: dict = {"url": settings.QDRANT_URL}
        if settings.QDRANT_API_KEY:
            kwargs["api_key"] = settings.QDRANT_API_KEY
        _client = QdrantClient(**kwargs)
        log.info("qdrant.client_created", url=settings.QDRANT_URL)
    return _client


def ensure_collection(
    collection_name: str,
    force_reindex: bool = False,
) -> None:
    """
    Create the Qdrant collection if it doesn't already exist.
    If *force_reindex* is True, drop and recreate the collection.
    """
    client = get_qdrant_client()

    if force_reindex:
        try:
            client.delete_collection(collection_name)
            log.info("qdrant.collection_dropped", name=collection_name)
        except Exception:  # noqa: BLE001
            pass  # May not exist yet

    try:
        client.get_collection(collection_name)
        log.info("qdrant.collection_exists", name=collection_name)
        return
    except (UnexpectedResponse, Exception):
        pass  # Doesn't exist – create below

    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(
            size=settings.EMBEDDING_DIMENSION,
            distance=Distance.COSINE,
        ),
        optimizers_config=OptimizersConfigDiff(
            indexing_threshold=10_000,  # Build HNSW index after 10k vectors
        ),
    )
    log.info(
        "qdrant.collection_created",
        name=collection_name,
        dim=settings.EMBEDDING_DIMENSION,
    )

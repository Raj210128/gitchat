"""
API v1 top-level router – mounts all endpoint sub-routers.
"""
from fastapi import APIRouter

from app.api.v1.endpoints.ingest import router as ingest_router
from app.api.v1.endpoints.chat import router as chat_router

api_router = APIRouter()

api_router.include_router(ingest_router, prefix="/ingest", tags=["Ingestion"])
api_router.include_router(chat_router, prefix="/chat", tags=["Chat"])

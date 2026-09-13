"""
Pydantic v2 schemas for all request/response contracts.
"""
from __future__ import annotations

from enum import Enum
from typing import List, Optional
from uuid import uuid4

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator


# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────
class IngestStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class NodeType(str, Enum):
    FUNCTION = "function"
    CLASS = "class"
    INTERFACE = "interface"
    METHOD = "method"
    MODULE = "module"       # fallback / file-level chunk
    UNKNOWN = "unknown"


# ─────────────────────────────────────────────────────────────────────────────
# Repo Ingestion
# ─────────────────────────────────────────────────────────────────────────────
class IngestRequest(BaseModel):
    """Request body for POST /ingest."""
    repo_url: AnyHttpUrl = Field(
        ...,
        examples=["https://github.com/tiangolo/fastapi"],
        description="HTTPS URL of the GitHub repository to index.",
    )
    branch: str = Field(
        default="main",
        max_length=128,
        description="Branch or tag to clone.",
    )
    force_reindex: bool = Field(
        default=False,
        description="Drop existing vectors for this repo and re-index from scratch.",
    )

    @field_validator("repo_url", mode="after")
    @classmethod
    def _must_be_github(cls, v: AnyHttpUrl) -> AnyHttpUrl:
        if "github.com" not in str(v):
            raise ValueError("Only GitHub URLs are supported at this time.")
        return v


class IngestStatusResponse(BaseModel):
    """Response for GET /ingest/{job_id}."""
    job_id: str
    status: IngestStatus
    repo_url: str
    branch: str
    files_processed: int = 0
    chunks_indexed: int = 0
    error: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Vector Chunk Metadata (stored as Qdrant payload)
# ─────────────────────────────────────────────────────────────────────────────
class ChunkMetadata(BaseModel):
    """Metadata payload stored alongside each vector in Qdrant."""
    model_config = ConfigDict(extra="ignore")  # tolerate unknown fields from Qdrant payload

    chunk_id: str = Field(default_factory=lambda: str(uuid4()))
    repo_id: str = Field(..., description="Unique identifier for the repository.")
    file_path: str = Field(..., description="Relative path from repo root.")
    language: str = Field(..., description="Detected programming language.")
    node_type: NodeType = NodeType.UNKNOWN
    node_name: Optional[str] = Field(
        default=None, description="Name of the function/class/interface."
    )
    start_line: int = Field(..., ge=1)
    end_line: int = Field(..., ge=1)
    code_snippet: str = Field(..., description="Raw source code of the chunk.")
    import_context: str = Field(
        default="",
        description="File-level import statements prepended for context.",
    )

    @field_validator("end_line")
    @classmethod
    def _end_after_start(cls, v: int, info) -> int:
        if "start_line" in info.data and v < info.data["start_line"]:
            raise ValueError("end_line must be >= start_line")
        return v


# ─────────────────────────────────────────────────────────────────────────────
# Chat
# ─────────────────────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    """Request body for POST /chat."""
    repo_id: str = Field(..., description="Repository identifier (returned by /ingest).")
    question: str = Field(..., min_length=3, max_length=2000)
    top_k: int = Field(default=8, ge=1, le=25)
    stream: bool = Field(
        default=False,
        description="If true, use GET /chat/stream instead.",
    )


class SourceReference(BaseModel):
    """A single retrieved chunk attributed to the answer."""
    chunk_id: str
    file_path: str
    start_line: int
    end_line: int
    node_type: NodeType
    node_name: Optional[str]
    language: str
    score: float = Field(..., ge=0.0, le=1.0, description="Retrieval relevance score.")
    snippet: str = Field(..., description="Short excerpt of the chunk.")


class ChatResponse(BaseModel):
    """Response for POST /chat (non-streaming)."""
    answer: str
    sources: List[SourceReference] = []
    cached: bool = False
    latency_ms: int = Field(..., description="End-to-end latency in milliseconds.")
    repo_id: str


# ─────────────────────────────────────────────────────────────────────────────
# SSE Streaming Events
# ─────────────────────────────────────────────────────────────────────────────
class SSEEventType(str, Enum):
    SOURCES = "sources"     # first event – list of SourceReference
    TOKEN = "token"         # one token from the LLM stream
    DONE = "done"           # stream complete
    ERROR = "error"         # error occurred


class SSEEvent(BaseModel):
    """Shape of every SSE data payload sent to the frontend."""
    event: SSEEventType
    data: str = ""          # JSON-encoded or plain token text


# ─────────────────────────────────────────────────────────────────────────────
# Generic
# ─────────────────────────────────────────────────────────────────────────────
class ErrorResponse(BaseModel):
    detail: str
    code: Optional[str] = None

"""
Application settings – pydantic-settings v2.
All configuration is read from environment variables / .env file.
Import `settings` (the singleton) anywhere in the application.
"""
from __future__ import annotations

from functools import lru_cache
from typing import List, Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── General ──────────────────────────────────────────────────────────────
    PROJECT_NAME: str = "GitHub Chat Assistant"
    API_VERSION: str = "0.1.0"
    API_PREFIX: str = "/api/v1"
    ENV: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = True

    # ── CORS ─────────────────────────────────────────────────────────────────
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _parse_cors(cls, v: str | list) -> list:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",")]
        return v

    # ── OpenAI ───────────────────────────────────────────────────────────────
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSION: int = 1536
    LLM_TEMPERATURE: float = 0.2
    LLM_MAX_TOKENS: int = 2048

    # ── GitHub ───────────────────────────────────────────────────────────────
    GITHUB_TOKEN: str = ""
    GITHUB_CLONE_DEPTH: int = 1

    # ── Qdrant ───────────────────────────────────────────────────────────────
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str = ""
    QDRANT_COLLECTION_NAME: str = "github_code_chunks"

    # ── Redis ─────────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_TTL_SECONDS: int = 3600
    SEMANTIC_CACHE_THRESHOLD: float = 0.92

    # ── Chunking ─────────────────────────────────────────────────────────────
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 64
    MAX_CHUNKS_PER_FILE: int = 200

    # ── Retrieval ────────────────────────────────────────────────────────────
    TOP_K: int = 8
    DENSE_WEIGHT: float = 0.6
    SPARSE_WEIGHT: float = 0.4
    SCORE_THRESHOLD: float = 0.35

    # ── Storage ───────────────────────────────────────────────────────────────
    REPO_CLONE_DIR: str = "/tmp/repo_clones"

    # ── Validation ────────────────────────────────────────────────────────────
    @model_validator(mode="after")
    def _require_key_in_prod(self) -> "Settings":
        if self.ENV == "production" and not self.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY must be set in production")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()

"""Pydantic request/response models for the public API."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class IngestRequest(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    content: str = Field(min_length=1)
    source: str | None = Field(default=None, max_length=1024)
    metadata: dict[str, Any] = Field(default_factory=dict)


class IngestResponse(BaseModel):
    document_id: uuid.UUID
    num_chunks: int


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=200)
    rerank_top_k: int | None = Field(default=None, ge=1, le=50)
    filters: dict[str, Any] | None = None


class SearchHitOut(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    content: str
    score: float
    recall_score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    query: str
    results: list[SearchHitOut]


class ChunkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    chunk_index: int
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentOut(BaseModel):
    id: uuid.UUID
    title: str
    source: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    chunks: list[ChunkOut] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    db_ok: bool
    embedder_ready: bool
    reranker_ready: bool


class ErrorResponse(BaseModel):
    detail: str

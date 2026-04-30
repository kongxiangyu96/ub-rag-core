"""Vector store contracts (storage + similarity search)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(slots=True)
class ChunkRecord:
    """A chunk to be persisted."""

    document_id: uuid.UUID
    chunk_index: int
    content: str
    embedding: list[float]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ChunkHit:
    """A chunk returned by similarity search, with score and origin."""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    content: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class VectorStore(Protocol):
    """Async vector store contract."""

    async def upsert_chunks(self, chunks: list[ChunkRecord]) -> list[uuid.UUID]: ...

    async def similarity_search(
        self,
        query_vector: list[float],
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[ChunkHit]: ...

    async def delete_by_document(self, document_id: uuid.UUID) -> int: ...


__all__ = ["ChunkRecord", "ChunkHit", "VectorStore"]

"""pgvector-backed VectorStore implementation."""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.document import Chunk
from src.services.vector_store.base import ChunkHit, ChunkRecord, VectorStore


class PgVectorStore(VectorStore):
    """Persists chunks in PostgreSQL and runs cosine similarity search via pgvector."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_chunks(self, chunks: list[ChunkRecord]) -> list[uuid.UUID]:
        if not chunks:
            return []

        rows = [
            Chunk(
                id=uuid.uuid4(),
                document_id=c.document_id,
                chunk_index=c.chunk_index,
                content=c.content,
                chunk_metadata=c.metadata or {},
                embedding=c.embedding,
            )
            for c in chunks
        ]
        self._session.add_all(rows)
        await self._session.flush()
        return [row.id for row in rows]

    async def similarity_search(
        self,
        query_vector: list[float],
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[ChunkHit]:
        if top_k <= 0:
            return []

        params: dict[str, Any] = {
            "q_vec": _vec_literal(query_vector),
            "k": top_k,
        }
        where_clause = ""
        if filters:
            where_clause = "WHERE metadata @> CAST(:filters AS jsonb)"
            params["filters"] = json.dumps(filters)

        sql = (
            "SELECT id, document_id, content, metadata, "
            "1 - (embedding <=> CAST(:q_vec AS vector)) AS score "
            "FROM chunks "
            f"{where_clause} "
            "ORDER BY embedding <=> CAST(:q_vec AS vector) "
            "LIMIT :k"
        )

        result = await self._session.execute(text(sql), params)
        return [
            ChunkHit(
                chunk_id=row.id,
                document_id=row.document_id,
                content=row.content,
                score=float(row.score),
                metadata=dict(row.metadata or {}),
            )
            for row in result
        ]

    async def delete_by_document(self, document_id: uuid.UUID) -> int:
        result = await self._session.execute(
            delete(Chunk).where(Chunk.document_id == document_id)
        )
        return result.rowcount or 0

    async def fetch_chunks_for_document(
        self, document_id: uuid.UUID
    ) -> list[Chunk]:
        result = await self._session.execute(
            select(Chunk)
            .where(Chunk.document_id == document_id)
            .order_by(Chunk.chunk_index)
        )
        return list(result.scalars().all())


def _vec_literal(vec: list[float]) -> str:
    """Format a Python float list as a pgvector text literal: '[0.1,0.2,...]'."""
    return "[" + ",".join(f"{float(x):.8f}" for x in vec) + "]"


__all__ = ["PgVectorStore"]

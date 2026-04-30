"""Ingestion orchestration: markdown -> chunks -> embeddings -> vector store."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any

from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.document import Document
from src.services.chunking import ChunkingService
from src.services.embedding.base import Embedder
from src.services.vector_store.base import ChunkRecord
from src.services.vector_store.pgvector_store import PgVectorStore

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class IngestionResult:
    document_id: uuid.UUID
    num_chunks: int


class IngestionService:
    """Orchestrates: chunk -> embed -> persist."""

    def __init__(
        self,
        chunking: ChunkingService,
        embedder: Embedder,
    ) -> None:
        self._chunking = chunking
        self._embedder = embedder

    async def ingest_markdown(
        self,
        session: AsyncSession,
        *,
        title: str,
        content: str,
        source: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> IngestionResult:
        if not content or not content.strip():
            raise ValueError("content must not be empty")

        meta = dict(metadata or {})
        chunks = await run_in_threadpool(
            self._chunking.chunk_markdown, content, meta
        )
        if not chunks:
            raise ValueError("chunker produced 0 chunks; check input or chunk_size")

        texts = [c.content for c in chunks]
        embeddings = await run_in_threadpool(self._embedder.embed_documents, texts)
        if len(embeddings) != len(chunks):
            raise RuntimeError(
                f"embedding count mismatch: {len(embeddings)} != {len(chunks)}"
            )

        document = Document(
            id=uuid.uuid4(),
            title=title,
            source=source,
            content=content,
            doc_metadata=meta,
        )
        session.add(document)
        await session.flush()

        store = PgVectorStore(session)
        records = [
            ChunkRecord(
                document_id=document.id,
                chunk_index=chunk.index,
                content=chunk.content,
                metadata=chunk.metadata,
                embedding=emb,
            )
            for chunk, emb in zip(chunks, embeddings, strict=True)
        ]
        await store.upsert_chunks(records)
        await session.commit()

        logger.info(
            "ingested document_id=%s title=%r num_chunks=%d",
            document.id,
            title,
            len(records),
        )
        return IngestionResult(document_id=document.id, num_chunks=len(records))


__all__ = ["IngestionService", "IngestionResult"]

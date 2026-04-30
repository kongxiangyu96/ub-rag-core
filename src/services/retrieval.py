"""Retrieval orchestration: query -> embed -> recall -> rerank -> top_k."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.services.embedding.base import Embedder
from src.services.reranker.base import Reranker
from src.services.vector_store.pgvector_store import PgVectorStore

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SearchHit:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    content: str
    score: float
    recall_score: float
    metadata: dict[str, Any] = field(default_factory=dict)


class RetrievalService:
    """Orchestrates: embed query -> pgvector ANN -> reranker -> top-k."""

    def __init__(
        self,
        embedder: Embedder,
        reranker: Reranker,
    ) -> None:
        self._embedder = embedder
        self._reranker = reranker

    async def search(
        self,
        session: AsyncSession,
        *,
        query: str,
        top_k: int | None = None,
        rerank_top_k: int | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchHit]:
        if not query or not query.strip():
            return []

        recall_k = top_k or settings.default_top_k
        final_k = rerank_top_k or settings.default_rerank_top_k
        if final_k > recall_k:
            recall_k = final_k

        query_vec = await run_in_threadpool(self._embedder.embed_query, query)

        store = PgVectorStore(session)
        candidates = await store.similarity_search(
            query_vector=query_vec,
            top_k=recall_k,
            filters=filters,
        )
        if not candidates:
            return []

        rerank_scores = await run_in_threadpool(
            self._reranker.score, query, [c.content for c in candidates]
        )

        scored: list[SearchHit] = [
            SearchHit(
                chunk_id=c.chunk_id,
                document_id=c.document_id,
                content=c.content,
                score=float(rs),
                recall_score=c.score,
                metadata=c.metadata,
            )
            for c, rs in zip(candidates, rerank_scores, strict=True)
        ]
        scored.sort(key=lambda h: h.score, reverse=True)

        logger.info(
            "search query=%r recall=%d rerank_top=%d",
            query[:80],
            len(candidates),
            final_k,
        )
        return scored[:final_k]


__all__ = ["RetrievalService", "SearchHit"]

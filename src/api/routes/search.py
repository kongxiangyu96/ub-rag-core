"""Search endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_retrieval_service, get_session
from src.api.schemas import SearchHitOut, SearchRequest, SearchResponse
from src.services.retrieval import RetrievalService

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResponse)
async def search(
    payload: SearchRequest,
    session: AsyncSession = Depends(get_session),
    retrieval: RetrievalService = Depends(get_retrieval_service),
) -> SearchResponse:
    hits = await retrieval.search(
        session,
        query=payload.query,
        top_k=payload.top_k,
        rerank_top_k=payload.rerank_top_k,
        filters=payload.filters,
    )
    return SearchResponse(
        query=payload.query,
        results=[
            SearchHitOut(
                chunk_id=h.chunk_id,
                document_id=h.document_id,
                content=h.content,
                score=h.score,
                recall_score=h.recall_score,
                metadata=h.metadata,
            )
            for h in hits
        ],
    )

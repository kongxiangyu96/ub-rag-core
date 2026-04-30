"""FastAPI dependencies that pull singletons off ``app.state``."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status

from src.core.db import get_session
from src.services.chunking import ChunkingService
from src.services.embedding.base import Embedder
from src.services.ingestion import IngestionService
from src.services.reranker.base import Reranker
from src.services.retrieval import RetrievalService


def get_chunking_service(request: Request) -> ChunkingService:
    svc = getattr(request.app.state, "chunking", None)
    if svc is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="chunking service not ready",
        )
    return svc


def get_embedder(request: Request) -> Embedder:
    embedder = getattr(request.app.state, "embedder", None)
    if embedder is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="embedder not ready",
        )
    return embedder


def get_reranker(request: Request) -> Reranker:
    reranker = getattr(request.app.state, "reranker", None)
    if reranker is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="reranker not ready",
        )
    return reranker


def get_ingestion_service(
    chunking: ChunkingService = Depends(get_chunking_service),
    embedder: Embedder = Depends(get_embedder),
) -> IngestionService:
    return IngestionService(chunking=chunking, embedder=embedder)


def get_retrieval_service(
    embedder: Embedder = Depends(get_embedder),
    reranker: Reranker = Depends(get_reranker),
) -> RetrievalService:
    return RetrievalService(embedder=embedder, reranker=reranker)


__all__ = [
    "get_session",
    "get_chunking_service",
    "get_embedder",
    "get_reranker",
    "get_ingestion_service",
    "get_retrieval_service",
]

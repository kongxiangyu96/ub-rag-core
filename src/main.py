"""FastAPI application entry point."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import ORJSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_session
from src.api.routes.documents import router as documents_router
from src.api.routes.search import router as search_router
from src.api.schemas import HealthResponse
from src.config import settings
from src.core.db import engine
from src.services.chunking import ChunkingService
from src.services.embedding.bge import BGEEmbedder
from src.services.reranker.bge import BGEReranker

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("starting %s (env=%s)", settings.app_name, settings.app_env)

    app.state.chunking = ChunkingService()
    logger.info("chunking service ready")

    logger.info("loading embedder...")
    app.state.embedder = await run_in_threadpool(BGEEmbedder)
    logger.info("embedder ready (dim=%d)", app.state.embedder.dim)

    logger.info("loading reranker...")
    app.state.reranker = await run_in_threadpool(BGEReranker)
    logger.info("reranker ready")

    try:
        yield
    finally:
        logger.info("shutting down...")
        await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
)

API_V1_PREFIX = "/api/v1"
app.include_router(documents_router, prefix=API_V1_PREFIX)
app.include_router(search_router, prefix=API_V1_PREFIX)


@app.get("/health", response_model=HealthResponse, tags=["meta"])
async def health(
    session: AsyncSession = Depends(get_session),
) -> HealthResponse:
    db_ok = False
    try:
        await session.execute(text("SELECT 1"))
        db_ok = True
    except Exception as e:
        logger.warning("db health check failed: %s", e)

    return HealthResponse(
        status="ok" if db_ok else "degraded",
        db_ok=db_ok,
        embedder_ready=getattr(app.state, "embedder", None) is not None,
        reranker_ready=getattr(app.state, "reranker", None) is not None,
    )


@app.get("/", tags=["meta"])
async def root() -> dict[str, str]:
    return {"app": settings.app_name, "version": "0.1.0", "docs": "/docs"}

"""Document ingestion + read/delete endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.dependencies import get_ingestion_service, get_session
from src.api.schemas import (
    ChunkOut,
    DocumentOut,
    IngestRequest,
    IngestResponse,
)
from src.models.document import Document
from src.services.ingestion import IngestionService

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "",
    response_model=IngestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def ingest_document(
    payload: IngestRequest,
    session: AsyncSession = Depends(get_session),
    ingestion: IngestionService = Depends(get_ingestion_service),
) -> IngestResponse:
    try:
        result = await ingestion.ingest_markdown(
            session,
            title=payload.title,
            content=payload.content,
            source=payload.source,
            metadata=payload.metadata,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return IngestResponse(
        document_id=result.document_id, num_chunks=result.num_chunks
    )


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> DocumentOut:
    stmt = (
        select(Document)
        .where(Document.id == document_id)
        .options(selectinload(Document.chunks))
    )
    doc = (await session.execute(stmt)).scalar_one_or_none()
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="document not found")

    return DocumentOut(
        id=doc.id,
        title=doc.title,
        source=doc.source,
        metadata=doc.doc_metadata,
        created_at=doc.created_at,
        chunks=[
            ChunkOut(
                id=c.id,
                chunk_index=c.chunk_index,
                content=c.content,
                metadata=c.chunk_metadata,
            )
            for c in sorted(doc.chunks, key=lambda c: c.chunk_index)
        ],
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    doc = await session.get(Document, document_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="document not found")
    await session.delete(doc)
    await session.commit()

"""Facade for chunking — keep this surface stable so the implementation can swap.

Future: this facade can be extracted into a standalone microservice; callers
should depend on this class (or the underlying ``Chunker`` Protocol) only.
"""

from __future__ import annotations

from typing import Any

from src.config import settings
from src.services.chunking.base import Chunk, Chunker
from src.services.chunking.markdown import MarkdownChunker


class ChunkingService:
    """Top-level chunking entrypoint used by the rest of the app."""

    def __init__(
        self,
        markdown_chunker: Chunker | None = None,
    ) -> None:
        self._markdown_chunker = markdown_chunker or MarkdownChunker(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )

    def chunk_markdown(
        self,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> list[Chunk]:
        """Chunk a Markdown document into ordered ``Chunk`` items."""
        return self._markdown_chunker.split(content, metadata=metadata)


__all__ = ["ChunkingService"]

"""Markdown-aware chunker: header-based split + recursive char split."""

from __future__ import annotations

from typing import Any

from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

from src.services.chunking.base import Chunk, Chunker

_DEFAULT_HEADERS: list[tuple[str, str]] = [
    ("#", "h1"),
    ("##", "h2"),
    ("###", "h3"),
    ("####", "h4"),
]


class MarkdownChunker(Chunker):
    """Two-stage Markdown splitter.

    Stage 1: split by Markdown headers, capture header trail in metadata.
    Stage 2: recursively split long sections into ``chunk_size`` pieces with overlap.
    """

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
        headers_to_split_on: list[tuple[str, str]] | None = None,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if chunk_overlap < 0 or chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be in [0, chunk_size)")

        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._headers = headers_to_split_on or _DEFAULT_HEADERS
        self._header_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=self._headers,
            strip_headers=False,
        )
        self._char_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", "。", "！", "？", ".", "!", "?", " ", ""],
        )

    def split(
        self,
        text: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> list[Chunk]:
        if not text or not text.strip():
            return []

        base_meta: dict[str, Any] = dict(metadata or {})

        sections = self._header_splitter.split_text(text)

        chunks: list[Chunk] = []
        idx = 0
        for section in sections:
            section_text = section.page_content
            section_meta = {**base_meta, **(section.metadata or {})}
            if not section_text.strip():
                continue

            if len(section_text) <= self._chunk_size:
                chunks.append(Chunk(content=section_text, index=idx, metadata=section_meta))
                idx += 1
                continue

            for piece in self._char_splitter.split_text(section_text):
                if not piece.strip():
                    continue
                chunks.append(Chunk(content=piece, index=idx, metadata=dict(section_meta)))
                idx += 1

        return chunks


__all__ = ["MarkdownChunker"]

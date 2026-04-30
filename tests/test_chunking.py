"""Unit tests for the chunking service."""

from __future__ import annotations

import pytest

from src.services.chunking.markdown import MarkdownChunker
from src.services.chunking.service import ChunkingService


def test_empty_input_returns_no_chunks() -> None:
    chunker = MarkdownChunker(chunk_size=128, chunk_overlap=16)
    assert chunker.split("") == []
    assert chunker.split("   \n\n  \t  ") == []


def test_short_markdown_yields_single_chunk() -> None:
    chunker = MarkdownChunker(chunk_size=512, chunk_overlap=64)
    text = "# Title\n\nThis is a short paragraph."

    chunks = chunker.split(text, metadata={"source": "test"})

    assert len(chunks) == 1
    assert "short paragraph" in chunks[0].content
    assert chunks[0].index == 0
    assert chunks[0].metadata.get("source") == "test"
    assert chunks[0].metadata.get("h1") == "Title"


def test_headers_create_separate_chunks() -> None:
    chunker = MarkdownChunker(chunk_size=512, chunk_overlap=64)
    text = (
        "# A\n\nalpha section.\n\n"
        "# B\n\nbeta section.\n\n"
        "## B.1\n\nbeta sub-section."
    )

    chunks = chunker.split(text)

    assert len(chunks) >= 3
    contents = " || ".join(c.content for c in chunks)
    assert "alpha section" in contents
    assert "beta section" in contents
    assert "beta sub-section" in contents

    headers = [c.metadata.get("h1") for c in chunks]
    assert "A" in headers
    assert "B" in headers


def test_long_section_is_recursively_split() -> None:
    chunker = MarkdownChunker(chunk_size=80, chunk_overlap=10)
    long_paragraph = ("Sentence one. " * 30).strip()
    text = f"# Header\n\n{long_paragraph}"

    chunks = chunker.split(text)

    assert len(chunks) >= 2
    for c in chunks:
        assert len(c.content) <= 80 + 20

    indices = [c.index for c in chunks]
    assert indices == sorted(indices)
    assert indices[0] == 0
    for i, idx in enumerate(indices):
        assert idx == i


def test_chunking_service_facade_uses_markdown_chunker() -> None:
    svc = ChunkingService()
    chunks = svc.chunk_markdown(
        "# Hello\n\nWorld.",
        metadata={"k": "v"},
    )
    assert chunks
    assert chunks[0].metadata.get("k") == "v"


def test_invalid_chunker_args() -> None:
    with pytest.raises(ValueError):
        MarkdownChunker(chunk_size=0)
    with pytest.raises(ValueError):
        MarkdownChunker(chunk_size=100, chunk_overlap=100)
    with pytest.raises(ValueError):
        MarkdownChunker(chunk_size=100, chunk_overlap=-1)

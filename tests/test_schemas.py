"""Schema validation tests (pure Pydantic, no I/O)."""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from src.api.schemas import (
    IngestRequest,
    SearchHitOut,
    SearchRequest,
    SearchResponse,
)


def test_ingest_request_valid() -> None:
    req = IngestRequest(
        title="hello",
        content="# Hello\n\nworld",
        source="unit-test",
        metadata={"tag": "demo"},
    )
    assert req.title == "hello"
    assert req.metadata == {"tag": "demo"}


def test_ingest_request_rejects_empty_content() -> None:
    with pytest.raises(ValidationError):
        IngestRequest(title="hello", content="")


def test_search_request_defaults() -> None:
    req = SearchRequest(query="什么是 RAG？")
    assert req.top_k is None
    assert req.rerank_top_k is None
    assert req.filters is None


def test_search_request_bounds() -> None:
    with pytest.raises(ValidationError):
        SearchRequest(query="q", top_k=0)
    with pytest.raises(ValidationError):
        SearchRequest(query="q", rerank_top_k=0)


def test_search_response_round_trip() -> None:
    hit = SearchHitOut(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        content="hello",
        score=0.9,
        recall_score=0.7,
        metadata={"src": "x"},
    )
    resp = SearchResponse(query="q", results=[hit])
    dumped = resp.model_dump()
    assert dumped["query"] == "q"
    assert len(dumped["results"]) == 1
    assert dumped["results"][0]["score"] == pytest.approx(0.9)

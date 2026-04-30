"""Embedder contract."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Embedder(Protocol):
    """Dense embedder contract.

    All vectors returned should be unit-normalized so that dot-product equals
    cosine similarity (matching the pgvector ``vector_cosine_ops`` index).
    """

    @property
    def dim(self) -> int:
        """Dimension of the produced vectors."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of documents."""

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query."""


__all__ = ["Embedder"]

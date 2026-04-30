"""Reranker contract."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Reranker(Protocol):
    """Cross-encoder reranker contract.

    Higher score means more relevant.
    """

    def score(self, query: str, documents: list[str]) -> list[float]:
        """Return one relevance score per document, aligned with the input order."""


__all__ = ["Reranker"]

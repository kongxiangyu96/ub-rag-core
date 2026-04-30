"""Chunking service contract: stable interface independent of implementation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(slots=True)
class Chunk:
    """A single chunk produced by a chunker."""

    content: str
    index: int
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class Chunker(Protocol):
    """Pluggable chunker contract.

    Implementations must be pure (no IO), deterministic for the same input,
    and safe to call from any thread.
    """

    def split(
        self,
        text: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> list[Chunk]:
        """Split ``text`` into ordered chunks. ``metadata`` is merged into each chunk."""


__all__ = ["Chunk", "Chunker"]

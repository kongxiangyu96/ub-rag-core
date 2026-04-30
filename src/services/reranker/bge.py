"""BGE cross-encoder reranker via FlagEmbedding."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from src.config import settings
from src.services.reranker.base import Reranker

logger = logging.getLogger(__name__)


class BGEReranker(Reranker):
    """BGE reranker (e.g. ``BAAI/bge-reranker-v2-m3``)."""

    def __init__(
        self,
        model_name: str | None = None,
        cache_dir: str | os.PathLike[str] | None = None,
        use_fp16: bool | None = None,
        device: str | None = None,
        max_length: int = 512,
        batch_size: int = 32,
    ) -> None:
        from FlagEmbedding import FlagReranker

        self._model_name = model_name or settings.reranker_model_name
        self._cache_dir = Path(cache_dir or settings.model_cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._use_fp16 = settings.use_fp16 if use_fp16 is None else use_fp16
        self._device = device or settings.device
        self._max_length = max_length
        self._batch_size = batch_size

        if settings.hf_endpoint:
            os.environ.setdefault("HF_ENDPOINT", settings.hf_endpoint)

        logger.info(
            "Loading BGE reranker model=%s device=%s fp16=%s cache_dir=%s",
            self._model_name,
            self._device,
            self._use_fp16,
            self._cache_dir,
        )
        self._model = FlagReranker(
            self._model_name,
            use_fp16=self._use_fp16,
            cache_dir=str(self._cache_dir),
            devices=self._device,
        )

    def score(self, query: str, documents: list[str]) -> list[float]:
        if not documents:
            return []
        pairs = [[query, doc] for doc in documents]
        raw = self._model.compute_score(
            pairs,
            batch_size=self._batch_size,
            max_length=self._max_length,
            normalize=True,
        )
        if isinstance(raw, (int, float)):
            return [float(raw)]
        return [float(s) for s in raw]


__all__ = ["BGEReranker"]

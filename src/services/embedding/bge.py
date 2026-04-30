"""BGE-M3 dense embedder via FlagEmbedding."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import numpy as np

from src.config import settings
from src.services.embedding.base import Embedder

logger = logging.getLogger(__name__)


class BGEEmbedder(Embedder):
    """Dense BGE-M3 embedder. Outputs are L2-normalized for cosine similarity."""

    def __init__(
        self,
        model_name: str | None = None,
        cache_dir: str | os.PathLike[str] | None = None,
        use_fp16: bool | None = None,
        device: str | None = None,
        max_length: int = 512,
        batch_size: int = 32,
    ) -> None:
        from FlagEmbedding import BGEM3FlagModel

        self._model_name = model_name or settings.embedding_model_name
        self._cache_dir = Path(cache_dir or settings.model_cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._use_fp16 = settings.use_fp16 if use_fp16 is None else use_fp16
        self._device = device or settings.device
        self._max_length = max_length
        self._batch_size = batch_size
        self._dim = settings.embedding_dim

        if settings.hf_endpoint:
            os.environ.setdefault("HF_ENDPOINT", settings.hf_endpoint)

        logger.info(
            "Loading BGE embedder model=%s device=%s fp16=%s cache_dir=%s",
            self._model_name,
            self._device,
            self._use_fp16,
            self._cache_dir,
        )
        self._model = BGEM3FlagModel(
            self._model_name,
            use_fp16=self._use_fp16,
            cache_dir=str(self._cache_dir),
            devices=self._device,
        )

    @property
    def dim(self) -> int:
        return self._dim

    def _encode(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        out = self._model.encode(
            texts,
            batch_size=self._batch_size,
            max_length=self._max_length,
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False,
        )
        dense = np.asarray(out["dense_vecs"], dtype=np.float32)
        norms = np.linalg.norm(dense, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1.0, norms)
        normalized = dense / norms
        return normalized.tolist()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._encode(texts)

    def embed_query(self, text: str) -> list[float]:
        result = self._encode([text])
        return result[0] if result else [0.0] * self._dim


__all__ = ["BGEEmbedder"]

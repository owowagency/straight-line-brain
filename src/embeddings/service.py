from __future__ import annotations

import asyncio
import logging
from typing import ClassVar

from src.config import get_settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Singleton embedding service using sentence-transformers.

    Lazily loads the model on first embed call and offloads
    the synchronous encode() to a thread to avoid blocking the event loop.
    """

    _instance: ClassVar[EmbeddingService | None] = None
    _model = None

    @classmethod
    def get_instance(cls) -> EmbeddingService:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_model(self) -> None:
        from sentence_transformers import SentenceTransformer

        settings = get_settings()
        logger.info("Loading embedding model: %s", settings.embedding_model)
        self._model = SentenceTransformer(settings.embedding_model)
        logger.info("Embedding model loaded successfully")

    def _embed_sync(self, text: str) -> list[float]:
        if self._model is None:
            self._load_model()
        return self._model.encode(text, normalize_embeddings=True).tolist()

    def _embed_batch_sync(self, texts: list[str]) -> list[list[float]]:
        if self._model is None:
            self._load_model()
        return self._model.encode(texts, normalize_embeddings=True).tolist()

    async def embed_text(self, text: str) -> list[float]:
        return await asyncio.to_thread(self._embed_sync, text)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return await asyncio.to_thread(self._embed_batch_sync, texts)


def get_embedding_service() -> EmbeddingService:
    return EmbeddingService.get_instance()

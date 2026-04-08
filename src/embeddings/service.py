from __future__ import annotations

import asyncio
import logging
from typing import ClassVar

from src.config import get_settings

logger = logging.getLogger(__name__)

# Default retrieval instruction for multilingual-e5-large-instruct.
# The model performs significantly better when queries carry a task prefix.
_DEFAULT_QUERY_INSTRUCTION = (
    "Gegeven een zoekvraag, vind relevante kennisartikelen die de vraag beantwoorden"
)


class EmbeddingService:
    """Singleton embedding service using sentence-transformers.

    Lazily loads the model on first embed call and offloads
    the synchronous encode() to a thread to avoid blocking the event loop.

    Two embedding modes:
    - **document** (embed_text / embed_batch): raw text, used when *storing*
      entries and chunks.  No instruction prefix.
    - **query** (embed_query): adds an ``Instruct: …\\nQuery: …`` wrapper so
      the instruct-tuned model knows to optimise for retrieval.
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

    # ------------------------------------------------------------------
    # Document embedding (storage) — no instruction prefix
    # ------------------------------------------------------------------

    def _embed_sync(self, text: str) -> list[float]:
        if self._model is None:
            self._load_model()
        return self._model.encode(text, normalize_embeddings=True).tolist()

    def _embed_batch_sync(self, texts: list[str]) -> list[list[float]]:
        if self._model is None:
            self._load_model()
        return self._model.encode(texts, normalize_embeddings=True).tolist()

    async def embed_text(self, text: str) -> list[float]:
        """Embed a single document text (for storage)."""
        return await asyncio.to_thread(self._embed_sync, text)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of document texts (for storage)."""
        return await asyncio.to_thread(self._embed_batch_sync, texts)

    # ------------------------------------------------------------------
    # Query embedding (retrieval) — with instruction prefix
    # ------------------------------------------------------------------

    @staticmethod
    def _format_query(text: str, instruction: str | None = None) -> str:
        """Wrap a query with the Instruct/Query format expected by e5-instruct."""
        inst = instruction or _DEFAULT_QUERY_INSTRUCTION
        return f"Instruct: {inst}\nQuery: {text}"

    def _embed_query_sync(
        self, text: str, instruction: str | None = None
    ) -> list[float]:
        if self._model is None:
            self._load_model()
        formatted = self._format_query(text, instruction)
        return self._model.encode(formatted, normalize_embeddings=True).tolist()

    async def embed_query(
        self, text: str, instruction: str | None = None
    ) -> list[float]:
        """Embed a search query with an instruction prefix for better retrieval.

        The instruct-tuned model uses the instruction to understand *what kind*
        of documents should be retrieved, yielding higher-quality results than
        embedding the raw query alone.
        """
        return await asyncio.to_thread(self._embed_query_sync, text, instruction)


def get_embedding_service() -> EmbeddingService:
    return EmbeddingService.get_instance()

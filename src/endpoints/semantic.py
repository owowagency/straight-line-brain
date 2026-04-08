import time

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import KnowledgeChunk, KnowledgeEntry
from src.db.session import get_session
from src.embeddings.service import EmbeddingService, get_embedding_service
from src.schemas.retrieval import (
    SemanticChunkResult,
    SemanticSearchRequest,
    SemanticSearchResponse,
)
from src.services.query_logger import log_query

router = APIRouter()

# Minimum similarity score — chunks below this are noise
_MIN_SCORE = 0.3
# Over-fetch multiplier for deduplication headroom
_OVERFETCH = 3


@router.post("/search", response_model=SemanticSearchResponse)
async def search_semantic(
    body: SemanticSearchRequest,
    session: AsyncSession = Depends(get_session),
    embedder: EmbeddingService = Depends(get_embedding_service),
):
    """Vector similarity search on knowledge chunks using pgvector.

    Uses instruction-aware query embedding for better retrieval accuracy,
    then deduplicates results so each knowledge entry appears at most once
    (keeping only the highest-scoring chunk per entry).
    """
    t0 = time.perf_counter()

    # Embed the query with instruction prefix for better retrieval
    query_embedding = await embedder.embed_query(body.query)

    # Over-fetch to leave room after deduplication
    fetch_limit = body.top_k * _OVERFETCH

    # Build pgvector cosine distance query
    distance = KnowledgeChunk.embedding.cosine_distance(query_embedding)
    query = (
        select(
            KnowledgeChunk,
            KnowledgeEntry.title.label("entry_title"),
            KnowledgeEntry.type.label("entry_type"),
            distance.label("distance"),
        )
        .join(KnowledgeEntry, KnowledgeChunk.entry_id == KnowledgeEntry.id)
        .where(KnowledgeEntry.is_active.is_(True))
        .where(KnowledgeEntry.review_status == "approved")
        .where(KnowledgeChunk.embedding.is_not(None))
        .order_by(distance)
        .limit(fetch_limit)
    )

    # Optional filters
    if body.entry_type:
        query = query.where(KnowledgeEntry.type == body.entry_type)
    if body.metadata_filter:
        query = query.where(KnowledgeChunk.metadata_.contains(body.metadata_filter))

    result = await session.execute(query)
    rows = result.all()

    # ------------------------------------------------------------------
    # Reranking: deduplicate by entry, apply score threshold
    # ------------------------------------------------------------------
    seen_entries: set[str] = set()
    results: list[SemanticChunkResult] = []

    for row in rows:
        score = round(1.0 - row.distance, 4)

        # Drop low-relevance noise
        if score < _MIN_SCORE:
            continue

        # Keep only the best chunk per knowledge entry
        entry_id_str = str(row.KnowledgeChunk.entry_id)
        if entry_id_str in seen_entries:
            continue
        seen_entries.add(entry_id_str)

        results.append(
            SemanticChunkResult(
                chunk_id=row.KnowledgeChunk.id,
                entry_id=row.KnowledgeChunk.entry_id,
                entry_title=row.entry_title,
                entry_type=row.entry_type,
                content=row.KnowledgeChunk.content,
                score=score,
                metadata=row.KnowledgeChunk.metadata_,
            )
        )

        if len(results) >= body.top_k:
            break

    ms = int((time.perf_counter() - t0) * 1000)
    await log_query(session, "semantic/search", body.query, response_time_ms=ms)
    await session.commit()

    return SemanticSearchResponse(
        query=body.query,
        results=results,
        total=len(results),
    )

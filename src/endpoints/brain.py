import time

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import KnowledgeChunk, KnowledgeEntry
from src.db.session import get_session
from src.embeddings.service import EmbeddingService, get_embedding_service
from src.schemas.retrieval import (
    BrainQueryRequest,
    BrainQueryResponse,
    SemanticChunkResult,
)
from src.services.query_logger import log_query

router = APIRouter()

# Keyword patterns for the stub query planner
_ICP_KEYWORDS = {"icp", "doelgroep", "klantprofiel", "segment"}
_TOV_KEYWORDS = {"tone of voice", "schrijfstijl", "communicatie", "toon"}
_COMPANY_KEYWORDS = {"bedrijf", "company", "propositie", "kernwaarden", "missie", "uppr"}
_SEGMENT_NAMES = {"vve", "woningcorporatie", "schilder", "vastgoed"}


def _classify_query(query: str) -> tuple[str, str]:
    """Simple keyword-based query classification (stub for Phase 4 Query Planner)."""
    q = query.lower()

    # Check for ICP / segment mentions
    if any(kw in q for kw in _ICP_KEYWORDS) or any(seg in q for seg in _SEGMENT_NAMES):
        return "narrow_icp", "Query mentions ICP or segment keywords"

    # Check for tone of voice
    if any(kw in q for kw in _TOV_KEYWORDS):
        return "narrow_tov", "Query mentions tone of voice keywords"

    # Check for company info
    if any(kw in q for kw in _COMPANY_KEYWORDS):
        return "narrow_company", "Query mentions company/propositie keywords"

    # Default: semantic search
    return "semantic_fallback", "No keyword match — using semantic search"


@router.post("/query", response_model=BrainQueryResponse)
async def query_brain(
    body: BrainQueryRequest,
    session: AsyncSession = Depends(get_session),
    embedder: EmbeddingService = Depends(get_embedding_service),
):
    """Free-form brain query with stub query planner and semantic fallback."""
    t0 = time.perf_counter()
    strategy, reason = _classify_query(body.query)
    results: list[SemanticChunkResult] = []

    if strategy == "narrow_icp":
        results = await _narrow_knowledge_search(session, "icp", body.query)
    elif strategy == "narrow_tov":
        results = await _narrow_knowledge_search(session, "tone_of_voice", body.query)
    elif strategy == "narrow_company":
        results = await _narrow_knowledge_search(
            session, ["bedrijfsprofiel", "propositie"], body.query
        )

    # If narrow search found nothing, or strategy is semantic_fallback
    if not results:
        strategy = "semantic_fallback" if strategy != "semantic_fallback" else strategy
        results = await _semantic_search(session, embedder, body.query)

    ms = int((time.perf_counter() - t0) * 1000)
    planner_meta = {"strategy": strategy, "reason": reason, "response_time_ms": ms}

    await log_query(
        session,
        "brain/query",
        body.query,
        agent_id=body.agent_id,
        planner_result=planner_meta,
        response_time_ms=ms,
    )
    await session.commit()

    return BrainQueryResponse(
        query=body.query,
        strategy=strategy,
        results=results,
        planner_metadata=planner_meta,
    )


async def _narrow_knowledge_search(
    session: AsyncSession,
    entry_types: str | list[str],
    query: str,
) -> list[SemanticChunkResult]:
    """Direct DB lookup for specific knowledge types."""
    if isinstance(entry_types, str):
        entry_types = [entry_types]

    q = (
        select(KnowledgeEntry)
        .where(KnowledgeEntry.type.in_(entry_types), KnowledgeEntry.is_active.is_(True))
        .options(selectinload(KnowledgeEntry.chunks))
    )
    result = await session.execute(q)
    entries = result.scalars().all()

    results = []
    for entry in entries:
        for chunk in sorted(entry.chunks, key=lambda c: c.chunk_index):
            results.append(
                SemanticChunkResult(
                    chunk_id=chunk.id,
                    entry_id=entry.id,
                    entry_title=entry.title,
                    entry_type=entry.type,
                    content=chunk.content,
                    score=1.0,  # direct match
                    metadata=chunk.metadata_,
                )
            )
    return results


async def _semantic_search(
    session: AsyncSession,
    embedder: EmbeddingService,
    query: str,
    top_k: int = 5,
) -> list[SemanticChunkResult]:
    """Vector similarity search fallback."""
    query_embedding = await embedder.embed_text(query)
    distance = KnowledgeChunk.embedding.cosine_distance(query_embedding)

    q = (
        select(
            KnowledgeChunk,
            KnowledgeEntry.title.label("entry_title"),
            KnowledgeEntry.type.label("entry_type"),
            distance.label("distance"),
        )
        .join(KnowledgeEntry, KnowledgeChunk.entry_id == KnowledgeEntry.id)
        .where(KnowledgeEntry.is_active.is_(True))
        .where(KnowledgeChunk.embedding.is_not(None))
        .order_by(distance)
        .limit(top_k)
    )
    result = await session.execute(q)
    rows = result.all()

    return [
        SemanticChunkResult(
            chunk_id=row.KnowledgeChunk.id,
            entry_id=row.KnowledgeChunk.entry_id,
            entry_title=row.entry_title,
            entry_type=row.entry_type,
            content=row.KnowledgeChunk.content,
            score=round(1.0 - row.distance, 4),
            metadata=row.KnowledgeChunk.metadata_,
        )
        for row in rows
    ]

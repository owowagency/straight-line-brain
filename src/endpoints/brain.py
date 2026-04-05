import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import KnowledgeEntry
from src.db.session import get_session
from src.embeddings.service import EmbeddingService, get_embedding_service
from src.query_planner.planner import QueryPlanner
from src.schemas.retrieval import BrainQueryRequest, BrainQueryResponse
from src.services.query_logger import log_query

router = APIRouter()
planner = QueryPlanner()


@router.post("/query", response_model=BrainQueryResponse)
async def query_brain(
    body: BrainQueryRequest,
    session: AsyncSession = Depends(get_session),
    embedder: EmbeddingService = Depends(get_embedding_service),
):
    """Free-form brain query routed through the Query Planner."""
    t0 = time.perf_counter()

    # 1. Plan: classify the query
    plan = await planner.plan(body.query)

    # 2. Execute: run the appropriate queries
    execution = await planner.execute(plan, body.query, session, embedder)

    ms = int((time.perf_counter() - t0) * 1000)

    planner_meta = {
        "intent": plan.intent,
        "confidence": plan.confidence,
        "reason": plan.reason,
        "merge_strategy": plan.merge_strategy,
        "narrow_type": plan.narrow_type,
        "narrow_params": plan.narrow_params,
        "strategy_used": execution["strategy"],
        "response_time_ms": ms,
        "merged_data": execution.get("merged"),
    }

    await log_query(
        session,
        "brain/query",
        body.query,
        agent_id=body.agent_id,
        planner_result=planner_meta,
        response_time_ms=ms,
    )

    # 3. File answer as knowledge entry if requested
    filed_id = None
    if body.file_answer and execution["results"]:
        filed_id = await _file_answer(
            session, embedder, body.query, execution, planner_meta
        )

    await session.commit()

    return BrainQueryResponse(
        query=body.query,
        strategy=execution["strategy"],
        results=execution["results"],
        planner_metadata=planner_meta,
        filed_as=filed_id,
    )


async def _file_answer(
    session: AsyncSession,
    embedder: EmbeddingService,
    query: str,
    execution: dict,
    planner_meta: dict,
) -> str | None:
    """File a brain query answer as a new 'inzicht' knowledge entry."""
    results = execution["results"]
    if not results:
        return None

    # Build answer content from results
    lines = [f"# Inzicht: {query}", ""]
    for r in results[:5]:
        lines.append(f"**{r.entry_title}** ({r.entry_type})")
        lines.append(r.content)
        lines.append("")

    content = "\n".join(lines)
    embedding = await embedder.embed_text(f"{query}\n\n{content}")

    entry = KnowledgeEntry(
        type="inzicht",
        title=f"Inzicht: {query[:100]}",
        content=content,
        created_by=planner_meta.get("agent_id", "brain_query"),
        metadata_={
            "source_query": query,
            "strategy_used": execution["strategy"],
            "filed_at": datetime.now(timezone.utc).isoformat(),
            "auto_generated": True,
        },
        embedding=embedding,
    )
    session.add(entry)
    await session.flush()
    return str(entry.id)
